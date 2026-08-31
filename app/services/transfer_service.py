"""Serial transfer queue: download each item to local temp, then upload to the other cloud."""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.config import settings
from app.models import Direction, TransferJob, TransferStage, TransferStatus
from app.services.mega_client import mega_adapter
from app.services.pikpak_client import pikpak_adapter

logger = logging.getLogger(__name__)

Listener = Callable[[TransferJob], Any]


def _rmtree_retry(path: Path, attempts: int = 5, delay: float = 0.25) -> None:
    """Remove a directory tree; retry on Windows file-lock races."""
    if not path.exists():
        return
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            shutil.rmtree(path)
            return
        except OSError as exc:
            last_exc = exc
            time.sleep(delay * (i + 1))
    # Final best-effort: ignore residual lock errors so the job can finish
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not fully clean temp dir %s: %s", path, exc)
    if last_exc:
        logger.warning("Could not fully clean temp dir %s: %s", path, last_exc)


class TransferService:
    """In-memory job store plus one asyncio worker that runs jobs one at a time."""

    def __init__(self) -> None:
        self.jobs: dict[str, TransferJob] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._cancel_flags: dict[str, asyncio.Event] = {}
        self._listeners: list[Listener] = []
        self._worker_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    def add_listener(self, listener: Listener) -> None:
        """Register a callback (HTTP WS broadcast) invoked on every job update."""
        self._listeners.append(listener)

    def remove_listener(self, listener: Listener) -> None:
        """Unregister a listener if present."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def _notify(self, job: TransferJob) -> None:
        """Touch the job timestamp and fan out to listeners (sync or async)."""
        job.touch()
        for listener in list(self._listeners):
            try:
                result = listener(job)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:  # noqa: BLE001
                logger.debug("listener error: %s", exc)

    def ensure_worker(self) -> None:
        """Start the background worker if it is not already running."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def create_job(
        self,
        direction: Direction,
        source_ids: list[str],
        dest_parent_id: str | None,
        source_meta: dict[str, dict] | None = None,
    ) -> TransferJob:
        """Create a queued job, start the worker, and push the id onto the queue."""
        job = TransferJob(
            id=str(uuid.uuid4()),
            direction=direction,
            source_ids=list(source_ids),
            dest_parent_id=dest_parent_id or None,
            source_meta=source_meta or {},
            status=TransferStatus.queued,
        )
        self.jobs[job.id] = job
        self._cancel_flags[job.id] = asyncio.Event()
        self.ensure_worker()
        await self._queue.put(job.id)
        await self._notify(job)
        return job

    def list_jobs(self) -> list[TransferJob]:
        """All jobs, newest first."""
        return sorted(self.jobs.values(), key=lambda j: j.created_at, reverse=True)

    def get_job(self, job_id: str) -> TransferJob | None:
        """Look up one job, or None."""
        return self.jobs.get(job_id)

    async def cancel(self, job_id: str) -> TransferJob:
        """Mark queued jobs cancelled immediately; running jobs stop after the current step."""
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        if job.status not in (
            TransferStatus.queued,
            TransferStatus.running,
        ):
            return job

        flag = self._cancel_flags.get(job_id)
        if flag:
            flag.set()

        # Immediate UI feedback. If a download/upload is mid-flight in a worker
        # thread it cannot be hard-killed; we stop before the next step.
        if job.status == TransferStatus.queued:
            job.status = TransferStatus.cancelled
            job.message = "Cancelled"
            job.error = None
        else:
            job.status = TransferStatus.cancelled
            job.message = (
                "Cancel requested — stopping after the current download/upload step"
            )
        await self._notify(job)
        return job

    async def retry(self, job_id: str) -> TransferJob:
        """Re-queue a failed/cancelled job from the beginning (does not skip dest files)."""
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        if job.status not in (TransferStatus.failed, TransferStatus.cancelled):
            raise RuntimeError("Only failed or cancelled jobs can be retried")
        job.status = TransferStatus.queued
        job.progress = 0.0
        job.bytes_done = 0
        job.bytes_total = 0
        job.error = None
        job.message = "Re-queued"
        job.current_file = None
        job.stage = TransferStage.queued
        self._cancel_flags[job_id] = asyncio.Event()
        self.ensure_worker()
        await self._queue.put(job.id)
        await self._notify(job)
        return job

    def _cancelled(self, job_id: str) -> bool:
        """True once cancel() has been requested for this job."""
        flag = self._cancel_flags.get(job_id)
        return bool(flag and flag.is_set())

    async def _worker_loop(self) -> None:
        """Serial consumer: one job at a time from the asyncio queue."""
        while True:
            job_id = await self._queue.get()
            job = self.jobs.get(job_id)
            if not job:
                self._queue.task_done()
                continue
            if job.status == TransferStatus.cancelled or self._cancelled(job_id):
                job.status = TransferStatus.cancelled
                await self._notify(job)
                self._queue.task_done()
                continue
            try:
                await self._run_job(job)
            except Exception as exc:
                logger.exception("Job %s failed", job_id)
                _mark_failed(job, exc)
                await self._notify(job)
            finally:
                self._queue.task_done()

    async def _run_job(self, job: TransferJob) -> None:
        """Relay each selected item (file or folder) through a per-job temp directory."""
        if self._cancelled(job.id):
            job.status = TransferStatus.cancelled
            job.message = "Cancelled"
            await self._notify(job)
            return

        job.status = TransferStatus.running
        job.message = "Starting"
        await self._notify(job)

        if job.direction == "mega_to_pikpak":
            src, dst = mega_adapter, pikpak_adapter
        else:
            src, dst = pikpak_adapter, mega_adapter

        if not src.is_authenticated() or not dst.is_authenticated():
            job.stage = TransferStage.auth
            raise RuntimeError("Both MEGA and PikPak must be connected")

        temp_root = settings.resolved_temp_dir() / job.id
        temp_root.mkdir(parents=True, exist_ok=True)

        try:
            total_items = len(job.source_ids)
            for index, source_id in enumerate(job.source_ids):
                if self._cancelled(job.id):
                    job.status = TransferStatus.cancelled
                    job.message = "Cancelled"
                    await self._notify(job)
                    return

                meta = job.source_meta.get(source_id) or {}
                name = meta.get("name")
                is_dir: bool | None = (
                    bool(meta["is_dir"]) if "is_dir" in meta else None
                )

                # Look up name / is_dir when the UI omitted them (folder vs file).
                if name is None or is_dir is None:
                    job.stage = TransferStage.listing
                    node = await src.get_node(source_id)
                    if name is None:
                        name = node.name
                    if is_dir is None:
                        is_dir = node.is_dir

                job.current_file = name
                job.message = f"Transferring {name}"
                job.progress = (index / max(total_items, 1)) * 100
                await self._notify(job)

                if is_dir:
                    await self._transfer_folder(
                        job, src, dst, source_id, name, job.dest_parent_id, temp_root
                    )
                else:
                    await self._transfer_file(
                        job, src, dst, source_id, name, job.dest_parent_id, temp_root
                    )

                # Stop immediately after the step that noticed cancel
                if self._cancelled(job.id):
                    job.status = TransferStatus.cancelled
                    job.message = "Cancelled"
                    await self._notify(job)
                    return

                job.progress = ((index + 1) / max(total_items, 1)) * 100
                await self._notify(job)

            if self._cancelled(job.id):
                job.status = TransferStatus.cancelled
                job.message = "Cancelled"
            else:
                job.status = TransferStatus.completed
                job.progress = 100.0
                job.message = "Completed"
            await self._notify(job)
        finally:
            _rmtree_retry(temp_root)

    async def _transfer_folder(
        self,
        job: TransferJob,
        src: Any,
        dst: Any,
        folder_id: str,
        folder_name: str,
        dest_parent_id: str | None,
        temp_root: Path,
    ) -> None:
        """Create the dest folder, list source children, and recurse files/subfolders."""
        if self._cancelled(job.id):
            return
        job.stage = TransferStage.mkdir
        new_folder = await dst.mkdir(dest_parent_id, folder_name)
        new_parent = new_folder.id or dest_parent_id
        job.stage = TransferStage.listing
        children = await src.list_folder(folder_id)
        for child in children:
            if self._cancelled(job.id):
                return
            job.current_file = f"{folder_name}/{child.name}"
            await self._notify(job)
            if child.is_dir:
                await self._transfer_folder(
                    job, src, dst, child.id, child.name, new_parent, temp_root
                )
            else:
                await self._transfer_file(
                    job, src, dst, child.id, child.name, new_parent, temp_root
                )

    async def _transfer_file(
        self,
        job: TransferJob,
        src: Any,
        dst: Any,
        file_id: str,
        file_name: str,
        dest_parent_id: str | None,
        temp_root: Path,
    ) -> None:
        """Download one file to a unique temp subdir, then upload; always delete the subdir."""
        if self._cancelled(job.id):
            return

        work = temp_root / uuid.uuid4().hex
        work.mkdir(parents=True, exist_ok=True)

        def on_dl(done: int, total: int) -> None:
            job.bytes_done = done
            job.bytes_total = total or job.bytes_total
            if total:
                # partial progress within current file doesn't move overall much
                job.message = f"Downloading {file_name} ({_fmt(done)}/{_fmt(total)})"

        def on_ul(done: int, total: int) -> None:
            job.bytes_done = done
            job.bytes_total = total or job.bytes_total
            if total:
                job.message = f"Uploading {file_name} ({_fmt(done)}/{_fmt(total)})"

        try:
            if self._cancelled(job.id):
                return
            job.stage = TransferStage.download
            local = await src.download_to_path(file_id, work, on_progress=on_dl)
            if self._cancelled(job.id):
                job.message = "Cancelled after download"
                await self._notify(job)
                return
            # Ensure path is a real closed file before upload
            if not local.exists():
                raise RuntimeError(f"Download produced no file for {file_name}")
            await self._notify(job)
            job.stage = TransferStage.upload
            await dst.upload_from_path(
                local,
                dest_parent_id,
                name=file_name,
                on_progress=on_ul,
            )
            if self._cancelled(job.id):
                job.message = "Cancelled"
                await self._notify(job)
                return
            await self._notify(job)
        finally:
            _rmtree_retry(work)

    def has_active_transfers(self) -> bool:
        """True if any job is queued or running (blocks temp clear unless forced)."""
        return any(
            j.status in (TransferStatus.queued, TransferStatus.running)
            for j in self.jobs.values()
        )

    def clear_temp_dir(self, force: bool = False) -> dict[str, Any]:
        """Delete contents of the app temp directory. Refuses if jobs are active unless force."""
        if self.has_active_transfers() and not force:
            raise RuntimeError(
                "Cannot clear temp while transfers are queued or running. "
                "Cancel them first, or pass force=true."
            )
        temp = settings.resolved_temp_dir()
        freed = 0
        removed = 0
        errors: list[str] = []
        if not temp.exists():
            return {
                "path": str(temp),
                "removed_entries": 0,
                "bytes_freed": 0,
                "errors": [],
            }
        for child in list(temp.iterdir()):
            try:
                if child.is_file():
                    size = child.stat().st_size
                    child.unlink(missing_ok=True)
                    freed += size
                    removed += 1
                else:
                    # sum size best-effort
                    for p in child.rglob("*"):
                        if p.is_file():
                            try:
                                freed += p.stat().st_size
                            except OSError:
                                pass
                    _rmtree_retry(child)
                    removed += 1
            except OSError as exc:
                errors.append(f"{child.name}: {exc}")
        return {
            "path": str(temp),
            "removed_entries": removed,
            "bytes_freed": freed,
            "errors": errors,
        }


def _mark_failed(job: TransferJob, exc: BaseException) -> None:
    """Set failed status and a message that includes the stage that broke (issue #13)."""
    job.status = TransferStatus.failed
    job.error = str(exc)
    label = job.stage_label()
    job.message = f"Failed · {label}" if label else "Failed"


def _fmt(n: int) -> str:
    """Human-readable byte count for job messages (e.g. ``47.6 KB``)."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} PB"


transfer_service = TransferService()
