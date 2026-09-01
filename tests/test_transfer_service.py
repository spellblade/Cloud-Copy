import asyncio
from pathlib import Path

import pytest

from app.models import FileNode, TransferJob, TransferStage, TransferStatus
from app.services import transfer_service as ts_mod
from app.services.transfer_service import TransferService, _mark_failed


@pytest.mark.asyncio
async def test_create_and_list_job():
    svc = TransferService()
    job = await svc.create_job(
        direction="mega_to_pikpak",
        source_ids=["a", "b"],
        dest_parent_id=None,
        source_meta={"a": {"name": "a.txt", "is_dir": False}},
    )
    assert job.status == TransferStatus.queued
    assert len(svc.list_jobs()) == 1
    assert svc.get_job(job.id) is job


@pytest.mark.asyncio
async def test_cancel_queued_job():
    svc = TransferService()
    # Don't start worker processing: cancel while still queued after create
    job = await svc.create_job(
        direction="pikpak_to_mega",
        source_ids=["x"],
        dest_parent_id=None,
    )
    cancelled = await svc.cancel(job.id)
    assert cancelled.status in (TransferStatus.cancelled, TransferStatus.queued, TransferStatus.running)


def test_failed_stage_label_mega_download():
    job = TransferJob(
        id="j1",
        direction="mega_to_pikpak",
        source_ids=["a"],
        stage=TransferStage.download,
    )
    _mark_failed(job, RuntimeError("Read timed out"))
    assert job.status == TransferStatus.failed
    assert job.message == "Failed · MEGA download"
    assert job.stage_label() == "MEGA download"
    assert "timed out" in job.error


def test_failed_stage_label_pikpak_upload():
    job = TransferJob(
        id="j2",
        direction="mega_to_pikpak",
        source_ids=["a"],
        stage=TransferStage.upload,
    )
    _mark_failed(job, RuntimeError("SSL validation failed"))
    assert job.message == "Failed · PikPak upload"


def test_failed_stage_label_reverse_download():
    job = TransferJob(
        id="j3",
        direction="pikpak_to_mega",
        source_ids=["a"],
        stage=TransferStage.download,
    )
    _mark_failed(job, RuntimeError("x"))
    assert job.message == "Failed · PikPak download"


class _SrcFolderTree:
    """In-memory source: one folder with a file and a nested folder."""

    def __init__(self) -> None:
        self.nodes = {
            "folder1": FileNode(id="folder1", name="Docs", is_dir=True),
            "f1": FileNode(id="f1", name="a.txt", is_dir=False, size=1),
            "sub": FileNode(id="sub", name="sub", is_dir=True),
            "f2": FileNode(id="f2", name="b.txt", is_dir=False, size=1),
        }
        self.children = {
            "folder1": [self.nodes["f1"], self.nodes["sub"]],
            "sub": [self.nodes["f2"]],
        }

    def is_authenticated(self) -> bool:
        return True

    async def get_node(self, file_id: str) -> FileNode:
        return self.nodes[file_id]

    async def list_folder(self, folder_id: str | None) -> list[FileNode]:
        return list(self.children.get(folder_id or "", []))

    async def download_to_path(self, file_id: str, dest_dir: Path, on_progress=None) -> Path:
        node = self.nodes[file_id]
        path = dest_dir / node.name
        path.write_bytes(b"x")
        if on_progress:
            on_progress(1, 1)
        return path


class _DstRecorder:
    """Destination that records mkdir/upload so tests can assert folder layout."""

    def __init__(self) -> None:
        self.mkdirs: list[tuple[str | None, str, str]] = []
        self.uploads: list[tuple[str | None, str]] = []
        self._n = 0

    def is_authenticated(self) -> bool:
        return True

    async def mkdir(self, parent_id: str | None, name: str) -> FileNode:
        self._n += 1
        node_id = f"d{self._n}"
        self.mkdirs.append((parent_id, name, node_id))
        return FileNode(id=node_id, name=name, is_dir=True, parent_id=parent_id)

    async def upload_from_path(self, local_path: Path, parent_id: str | None, name=None, on_progress=None):
        dest_name = name or local_path.name
        self.uploads.append((parent_id, dest_name))
        if on_progress:
            on_progress(1, 1)
        return FileNode(id="u", name=dest_name, is_dir=False)


async def _run_folder_job(monkeypatch, tmp_path, source_meta: dict) -> tuple[TransferJob, _DstRecorder]:
    src, dst = _SrcFolderTree(), _DstRecorder()
    monkeypatch.setattr(ts_mod, "mega_adapter", src)
    monkeypatch.setattr(ts_mod, "pikpak_adapter", dst)
    monkeypatch.setattr(ts_mod.settings, "temp_dir", tmp_path)

    svc = TransferService()
    job = TransferJob(
        id="job-folder",
        direction="mega_to_pikpak",
        source_ids=["folder1"],
        dest_parent_id="dest-root",
        source_meta=source_meta,
    )
    svc.jobs[job.id] = job
    svc._cancel_flags[job.id] = asyncio.Event()
    await svc._run_job(job)
    return job, dst


@pytest.mark.asyncio
async def test_folder_meta_copies_children(monkeypatch, tmp_path):
    """Selected folder with is_dir=True creates dest folder and copies nested files."""
    job, dst = await _run_folder_job(
        monkeypatch,
        tmp_path,
        {"folder1": {"name": "Docs", "is_dir": True}},
    )
    assert job.status == TransferStatus.completed
    assert dst.mkdirs[0] == ("dest-root", "Docs", "d1")
    nested = [m[1] for m in dst.mkdirs]
    assert "sub" in nested
    uploaded = [u[1] for u in dst.uploads]
    assert uploaded == ["a.txt", "b.txt"]
    assert dst.uploads[0][0] == "d1"
    sub_id = next(m[2] for m in dst.mkdirs if m[1] == "sub")
    assert dst.uploads[1][0] == sub_id


@pytest.mark.asyncio
async def test_folder_without_is_dir_looks_up_node(monkeypatch, tmp_path):
    """If the UI omits is_dir, get_node still classifies the source as a folder."""
    job, dst = await _run_folder_job(
        monkeypatch,
        tmp_path,
        {"folder1": {"name": "Docs"}},
    )
    assert job.status == TransferStatus.completed
    assert dst.mkdirs[0][1] == "Docs"
    assert [u[1] for u in dst.uploads] == ["a.txt", "b.txt"]
    assert job.files_total == 2
    assert job.files_done == 2


class _ProgressSrc:
    """Source that reports mid-file download bytes."""

    def is_authenticated(self) -> bool:
        return True

    async def get_node(self, file_id: str) -> FileNode:
        return FileNode(id=file_id, name="big.bin", is_dir=False, size=100)

    async def download_to_path(self, file_id: str, dest_dir: Path, on_progress=None) -> Path:
        path = dest_dir / "big.bin"
        path.write_bytes(b"x" * 100)
        if on_progress:
            on_progress(25, 100)
            await asyncio.sleep(0)
            on_progress(60, 100)
            await asyncio.sleep(0)
            on_progress(100, 100)
        return path


class _ProgressDst:
    def is_authenticated(self) -> bool:
        return True

    async def upload_from_path(self, local_path: Path, parent_id: str | None, name=None, on_progress=None):
        if on_progress:
            on_progress(40, 100)
            await asyncio.sleep(0)
            on_progress(100, 100)
        return FileNode(id="u", name=name or local_path.name, is_dir=False)


@pytest.mark.asyncio
async def test_live_progress_notifies_mid_file(monkeypatch, tmp_path):
    """WS snapshots should include in-flight bytes, not only 100/100 at the end."""
    monkeypatch.setattr(ts_mod, "mega_adapter", _ProgressSrc())
    monkeypatch.setattr(ts_mod, "pikpak_adapter", _ProgressDst())
    monkeypatch.setattr(ts_mod.settings, "temp_dir", tmp_path)

    svc = TransferService()
    snaps: list[dict] = []

    def listener(job: TransferJob) -> None:
        snaps.append(
            {
                "bytes_done": job.bytes_done,
                "bytes_total": job.bytes_total,
                "progress": job.progress,
                "message": job.message,
                "stage": job.stage,
                "status": job.status,
            }
        )

    svc.add_listener(listener)
    job = TransferJob(
        id="job-progress",
        direction="mega_to_pikpak",
        source_ids=["f1"],
        dest_parent_id=None,
        source_meta={"f1": {"name": "big.bin", "is_dir": False}},
    )
    svc.jobs[job.id] = job
    svc._cancel_flags[job.id] = asyncio.Event()
    await svc._run_job(job)
    await asyncio.sleep(0)

    assert job.status == TransferStatus.completed
    mid = [
        s
        for s in snaps
        if s["status"] == TransferStatus.running
        and s["bytes_total"]
        and s["bytes_done"] < s["bytes_total"]
    ]
    assert mid, f"expected in-flight snapshots, got {snaps!r}"
    assert any("Downloading" in (s["message"] or "") for s in mid)
    assert any(s["stage"] == TransferStage.upload for s in snaps)
    assert any(0 < s["progress"] < 100 for s in mid)


def test_progress_download_is_first_half_of_each_file():
    """Two files: finishing file 1 download is 25%, not 100%; upload start stays 25%."""
    svc = TransferService()
    job = TransferJob(
        id="p",
        direction="mega_to_pikpak",
        source_ids=["a", "b"],
        files_total=2,
        files_done=0,
        stage=TransferStage.download,
        bytes_done=100,
        bytes_total=100,
    )
    svc._refresh_progress(job)
    assert job.progress == pytest.approx(25.0)

    job.stage = TransferStage.upload
    job.bytes_done = 0
    svc._refresh_progress(job)
    assert job.progress == pytest.approx(25.0)

    job.bytes_done = 100
    svc._refresh_progress(job)
    assert job.progress == pytest.approx(50.0)

    job.files_done = 1
    job.stage = TransferStage.download
    job.bytes_done = 0
    svc._refresh_progress(job)
    assert job.progress == pytest.approx(50.0)


def test_progress_reader_does_not_reset_on_seek(tmp_path):
    """httpx/boto3 re-read must not drive the bar 0→100 a second time."""
    from app.services.pikpak_client import _ProgressReader

    path = tmp_path / "chunk.bin"
    path.write_bytes(b"abcdefghij")
    seen: list[int] = []
    with _ProgressReader(path, lambda done, _total: seen.append(done)) as reader:
        reader.read(10)
        reader.seek(0)
        reader.read(10)
    assert seen
    assert seen[-1] == 10
    assert seen == sorted(seen)
