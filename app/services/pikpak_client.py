# PikPak adapter: unofficial API login, listings, and FORM/S3 uploads with name repair.

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from app.models import FileNode
from app.services.credential_store import credential_store

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]


def split_filename(name: str) -> tuple[str, str]:
    # Split 'file.v0.7.pdf' → ('file.v0.7', '.pdf'); no extension → (name, '').
    p = Path(name)
    if p.suffix:
        return p.stem, p.suffix
    return name, ""


def next_available_name(desired: str, taken: set[str]) -> str:
    """
    If desired is free, return it. Else PikPak-style: stem(1).ext, stem(2).ext, …
    Example: 'Misumi Walkthrough v0.7.pdf' → 'Misumi Walkthrough v0.7(1).pdf'
    """
    if desired not in taken:
        return desired
    stem, ext = split_filename(desired)
    n = 1
    while True:
        candidate = f"{stem}({n}){ext}"
        if candidate not in taken:
            return candidate
        n += 1
        if n > 10_000:
            raise RuntimeError(f"Could not find free name for {desired!r}")


def calc_gcid(path: Path) -> str:
    # PikPak gcid: SHA1 of successive SHA1 block digests (same as rclone).
    size = path.stat().st_size

    def block_size(total: int) -> int:
        # Chunk size used by PikPak gcid (grows with file size, capped at 2 MiB).
        psize = 0x40000
        while total / psize > 0x200 and psize < 0x200000:
            psize <<= 1
        return psize

    read_size = block_size(size)
    total_hash = hashlib.sha1()
    with path.open("rb") as f:
        while True:
            chunk = f.read(read_size)
            if not chunk:
                break
            total_hash.update(hashlib.sha1(chunk).digest())
    return total_hash.hexdigest()


class PikPakAdapter:
    # Adapter around pikpakapi plus resumable upload support.

    def __init__(self) -> None:
        self._client: Any = None
        self._username: str | None = None

    @property
    def username(self) -> str | None:
        # Account used for the current PikPak session, if any.
        return self._username

    def is_authenticated(self) -> bool:
        # True when pikpakapi holds a live access token.
        return self._client is not None and bool(getattr(self._client, "access_token", None))

    async def login(self, username: str, password: str, persist: bool = True) -> None:
        # Password login, refresh the token, optionally persist credentials + encoded_token.
        from pikpakapi import PikPakApi

        client = PikPakApi(
            username=username,
            password=password,
            httpx_client_args={"timeout": 120.0},
        )
        try:
            await client.login()
            await client.refresh_access_token()
        except Exception as exc:  # noqa: BLE001
            self._client = None
            self._username = None
            raise RuntimeError(f"PikPak login failed: {exc}") from exc

        self._client = client
        self._username = username
        if persist:
            credential_store.set(
                "pikpak",
                {
                    "username": username,
                    "password": password,
                    "encoded_token": client.encoded_token,
                    "device_id": client.device_id,
                },
            )

    async def restore_session(self) -> bool:
        # Restore from encoded_token, else password re-login. Returns False if nothing saved.
        saved = credential_store.get("pikpak")
        if not saved:
            return False
        from pikpakapi import PikPakApi

        try:
            if saved.get("encoded_token"):
                client = PikPakApi(
                    encoded_token=saved["encoded_token"],
                    device_id=saved.get("device_id"),
                    httpx_client_args={"timeout": 120.0},
                )
                if saved.get("username"):
                    client.username = saved["username"]
                await client.refresh_access_token()
                self._client = client
                self._username = saved.get("username")
                credential_store.set(
                    "pikpak",
                    {
                        "username": self._username,
                        "password": saved.get("password"),
                        "encoded_token": client.encoded_token,
                        "device_id": client.device_id,
                    },
                )
                return True
            if saved.get("username") and saved.get("password"):
                await self.login(saved["username"], saved["password"], persist=True)
                return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("PikPak session restore failed: %s", exc)
            # fall back to password login if available
            if saved.get("username") and saved.get("password"):
                try:
                    await self.login(saved["username"], saved["password"], persist=True)
                    return True
                except Exception as exc2:  # noqa: BLE001
                    logger.warning("PikPak password re-login failed: %s", exc2)
        return False

    async def logout(self) -> None:
        # Close the HTTP client, drop the session, and delete saved PikPak credentials.
        if self._client and hasattr(self._client, "httpx_client"):
            try:
                await self._client.httpx_client.aclose()
            except Exception:  # noqa: BLE001
                pass
        self._client = None
        self._username = None
        credential_store.delete("pikpak")

    def _require(self) -> Any:
        # Return the pikpakapi client or raise if not logged in.
        if self._client is None:
            raise RuntimeError("Not logged in to PikPak")
        return self._client

    def _file_to_node(self, item: dict[str, Any]) -> FileNode:
        # Map a PikPak file/folder dict onto our ``FileNode``.
        kind = item.get("kind") or ""
        is_dir = "folder" in kind
        size = int(item.get("size") or 0)
        return FileNode(
            id=item.get("id") or "",
            name=item.get("name") or "",
            is_dir=is_dir,
            size=size,
            modified_at=item.get("modified_time") or item.get("created_time"),
            parent_id=item.get("parent_id") or None,
        )

    async def list_folder(self, folder_id: str | None = None) -> list[FileNode]:
        # Paginated listing of ``folder_id`` (root if omitted); folders first, then name.
        client = self._require()
        parent = folder_id or None
        items: list[FileNode] = []
        page_token: str | None = None
        while True:
            data = await client.file_list(
                size=100,
                parent_id=parent,
                next_page_token=page_token,
            )
            for f in data.get("files") or []:
                items.append(self._file_to_node(f))
            page_token = data.get("next_page_token") or None
            if not page_token:
                break
        items.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        return items

    async def get_node(self, file_id: str) -> FileNode:
        # Fetch one file/folder by id (used when transfer meta lacks a name).
        client = self._require()
        info = await client.offline_file_info(file_id)
        return self._file_to_node(info)

    async def mkdir(self, parent_id: str | None, name: str) -> FileNode:
        # Create folder, or reuse an existing folder with the same name.
        parent = parent_id or None
        existing = await self.list_folder(parent)
        for item in existing:
            if item.is_dir and item.name == name:
                return item

        client = self._require()
        result = await client.create_folder(name=name, parent_id=parent)
        file_info = result.get("file") or result
        node = self._file_to_node(file_info)
        if node.id and node.name != name:
            return await self._ensure_final_name(node.id, name, parent)
        return node

    async def _names_in_folder(self, parent_id: str | None) -> set[str]:
        # Set of existing names in a folder — used to avoid overwrites and pick ``(1)``.
        items = await self.list_folder(parent_id or None)
        return {item.name for item in items}

    async def _ensure_final_name(
        self,
        file_id: str,
        target_name: str,
        parent_id: str | None,
    ) -> FileNode:
        # If PikPak assigned a different name, rename to target_name when possible.
        client = self._require()
        try:
            info = await client.offline_file_info(file_id)
            node = self._file_to_node(info)
        except Exception:  # noqa: BLE001
            node = FileNode(id=file_id, name=target_name, is_dir=False, parent_id=parent_id)

        if node.name == target_name:
            return node

        # Try exact target first (handles spurious (1) when name is free)
        try:
            renamed = await client.file_rename(file_id, target_name)
            if isinstance(renamed, dict) and renamed.get("name"):
                return self._file_to_node(renamed)
            fresh = await client.offline_file_info(file_id)
            return self._file_to_node(fresh)
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "PikPak rename to %r failed (%s); picking next free name",
                target_name,
                type(exc).__name__,
            )

        # Target may be taken — pick next free and rename
        taken = await self._names_in_folder(parent_id)
        # Current object's old name is still "taken" under its current id; exclude it
        taken.discard(node.name)
        free = next_available_name(target_name, taken)
        if free == node.name:
            return node
        try:
            renamed = await client.file_rename(file_id, free)
            if isinstance(renamed, dict) and renamed.get("name"):
                return self._file_to_node(renamed)
            fresh = await client.offline_file_info(file_id)
            return self._file_to_node(fresh)
        except Exception as exc:  # noqa: BLE001
            logger.warning("PikPak could not set final name %r: %s", free, exc)
            return node

    async def download_to_path(
        self,
        file_id: str,
        dest_dir: Path,
        on_progress: ProgressCallback | None = None,
    ) -> Path:
        # Stream a PikPak file to ``dest_dir`` via the web content link.
        client = self._require()
        info = await client.get_download_url(file_id)
        name = info.get("name") or file_id
        size = int(info.get("size") or 0)
        url = info.get("web_content_link")
        if not url:
            links = info.get("links") or {}
            stream = links.get("application/octet-stream") or {}
            url = stream.get("url")
        if not url:
            medias = info.get("medias") or []
            if medias and medias[0].get("link"):
                url = medias[0]["link"].get("url")
        if not url:
            raise RuntimeError(f"No download URL for PikPak file {file_id}")

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / name
        headers = client.get_headers()
        # download URL may not want Authorization in some cases; keep User-Agent
        dl_headers = {"User-Agent": headers.get("User-Agent", "cloud-copy")}

        async with httpx.AsyncClient(timeout=None, follow_redirects=True) as http:
            async with http.stream("GET", url, headers=dl_headers) as resp:
                resp.raise_for_status()
                done = 0
                with dest.open("wb") as out:
                    async for chunk in resp.aiter_bytes(1024 * 256):
                        out.write(chunk)
                        done += len(chunk)
                        if on_progress:
                            on_progress(done, size or done)
        return dest

    async def upload_from_path(
        self,
        local_path: Path,
        parent_id: str | None,
        name: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> FileNode:
        """ Upload a local file to PikPak.

        Naming:
        - If desired name is free → keep it (rename back if API adds spurious (1)).
        - If taken → use name(1).ext, name(2).ext, … (never overwrite).

        Prefer FORM for smaller files; S3 for larger with FORM fallback.
        """
        desired_name = name or local_path.name
        size = local_path.stat().st_size
        gcid = await asyncio.to_thread(calc_gcid, local_path)
        parent = parent_id or ""

        taken = await self._names_in_folder(parent or None)
        target_name = next_available_name(desired_name, taken)
        if target_name != desired_name:
            logger.info(
                "PikPak name %r taken; uploading as %r",
                desired_name,
                target_name,
            )

        # FORM is more reliable for modest sizes; S3 for large (with fallback)
        form_cutoff = 200 * 1024 * 1024  # 200 MiB
        prefer_form = size < form_cutoff

        if prefer_form:
            try:
                return await self._upload_with_type(
                    local_path,
                    target_name,
                    parent,
                    gcid,
                    size,
                    upload_type="UPLOAD_TYPE_FORM",
                    on_progress=on_progress,
                )
            except Exception as form_exc:  # noqa: BLE001
                logger.warning(
                    "PikPak FORM upload failed (%s); trying resumable S3",
                    type(form_exc).__name__,
                )

        try:
            return await self._upload_with_type(
                local_path,
                target_name,
                parent,
                gcid,
                size,
                upload_type="UPLOAD_TYPE_RESUMABLE",
                on_progress=on_progress,
            )
        except Exception as s3_exc:  # noqa: BLE001
            msg = str(s3_exc)
            if "AccessDenied" not in msg and "access denied" not in msg.lower():
                raise
            if prefer_form:
                raise RuntimeError(
                    f"PikPak storage rejected upload (AccessDenied) and FORM also failed: {s3_exc}"
                ) from s3_exc
            logger.warning("PikPak S3 AccessDenied; falling back to FORM upload")
            return await self._upload_with_type(
                local_path,
                target_name,
                parent,
                gcid,
                size,
                upload_type="UPLOAD_TYPE_FORM",
                on_progress=on_progress,
            )

    async def _upload_with_type(
        self,
        local_path: Path,
        dest_name: str,
        parent_id: str,
        gcid: str,
        size: int,
        upload_type: str,
        on_progress: ProgressCallback | None = None,
    ) -> FileNode:
        # Create the PikPak file ticket, upload FORM or S3, then repair the final name.
        client = self._require()
        body: dict[str, Any] = {
            "kind": "drive#file",
            "name": dest_name,
            "parent_id": parent_id,
            "size": str(size),
            "hash": gcid.upper(),
            "upload_type": upload_type,
            "folder_type": "NORMAL",
        }
        if upload_type == "UPLOAD_TYPE_RESUMABLE":
            body["resumable"] = {"provider": "PROVIDER_ALIYUN"}

        url = f"https://{client.PIKPAK_API_HOST}/drive/v1/files"
        result = await client._request_post(url, body)
        file_info = result.get("file") or {}
        file_id = file_info.get("id")
        task = result.get("task") or {}
        task_id = task.get("id")
        phase = file_info.get("phase") or ""

        # Instant upload (dedup by gcid) or empty file
        if phase == "PHASE_TYPE_COMPLETE" or size == 0:
            if on_progress:
                on_progress(size, size)
            if file_id:
                return await self._ensure_final_name(file_id, dest_name, parent_id or None)
            return self._file_to_node(file_info)

        try:
            if upload_type == "UPLOAD_TYPE_FORM" or result.get("form"):
                form = result.get("form")
                if not form:
                    raise RuntimeError("PikPak FORM ticket missing form payload")
                logger.info("PikPak upload via FORM (size=%s name=%r)", size, dest_name)
                await self._upload_form(local_path, form, on_progress)
            else:
                resumable = result.get("resumable") or {}
                params = resumable.get("params") or {}
                if not params:
                    params = {
                        k: resumable[k]
                        for k in (
                            "access_key_id",
                            "access_key_secret",
                            "security_token",
                            "bucket",
                            "endpoint",
                            "key",
                        )
                        if k in resumable
                    }
                if not params.get("access_key_id") and not params.get("bucket"):
                    raise RuntimeError(
                        "PikPak resumable ticket missing OSS params "
                        f"(keys={list((resumable or result).keys())})"
                    )
                logger.info(
                    "PikPak upload via S3 (bucket=%s endpoint_set=%s name=%r)",
                    bool(params.get("bucket")),
                    bool(params.get("endpoint")),
                    dest_name,
                )
                await self._upload_s3(local_path, params, on_progress)
        except Exception:
            await self._cancel_incomplete_upload(file_id, task_id)
            raise

        if task_id:
            await self._wait_task(task_id)

        if file_id:
            return await self._ensure_final_name(file_id, dest_name, parent_id or None)
        return self._file_to_node(file_info)

    async def _cancel_incomplete_upload(
        self,
        file_id: str | None,
        task_id: str | None,
    ) -> None:
        # Best-effort delete of a half-created file/task after an upload failure.
        client = self._require()
        try:
            if file_id:
                await client.delete_forever([file_id])
        except Exception as exc:  # noqa: BLE001
            logger.debug("cancel incomplete file: %s", exc)
        try:
            if task_id:
                await client.delete_tasks([task_id], delete_files=False)
        except Exception as exc:  # noqa: BLE001
            logger.debug("cancel incomplete task: %s", exc)

    async def _upload_s3(
        self,
        local_path: Path,
        params: dict[str, Any],
        on_progress: ProgressCallback | None,
    ) -> None:
        # Upload via Aliyun-compatible S3 PutObject (rclone-style, no extra checksums).

        def _put() -> None:
            import boto3
            from botocore.config import Config
            from botocore.exceptions import ClientError

            access_key = params.get("access_key_id") or params.get("accessKeyId")
            secret = params.get("access_key_secret") or params.get("accessKeySecret")
            token = params.get("security_token") or params.get("securityToken")
            bucket = params.get("bucket")
            key = params.get("key")
            endpoint = params.get("endpoint") or "https://mypikpak.com/"
            if not str(endpoint).startswith("http"):
                endpoint = f"https://{endpoint}"
            # boto prefers no trailing path noise
            endpoint = str(endpoint).rstrip("/") + "/"

            if not all([access_key, secret, bucket, key]):
                raise RuntimeError("Incomplete PikPak OSS credentials in upload ticket")

            size = local_path.stat().st_size
            # Disable optional checksums — PikPak STS policy rejects extra amz headers
            # (same idea as rclone's RequestChecksumCalculationWhenRequired)
            cfg = Config(
                signature_version="s3v4",
                s3={
                    "addressing_style": "path",
                    "payload_signing_enabled": True,
                },
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
                retries={"max_attempts": 3, "mode": "standard"},
            )
            session = boto3.session.Session()
            s3 = session.client(
                "s3",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret,
                aws_session_token=token,
                endpoint_url=endpoint,
                region_name="pikpak",
                config=cfg,
            )

            try:
                with local_path.open("rb") as f:
                    s3.put_object(
                        Bucket=bucket,
                        Key=key,
                        Body=f,
                        ContentLength=size,
                        ContentType="application/octet-stream",
                    )
            except ClientError as exc:
                code = (exc.response or {}).get("Error", {}).get("Code", "")
                if code in ("AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch"):
                    raise RuntimeError(
                        f"AccessDenied when calling PutObject: {exc}"
                    ) from exc
                raise
            if on_progress:
                on_progress(size, size)

        await asyncio.to_thread(_put)

    async def _upload_form(
        self,
        local_path: Path,
        form: dict[str, Any],
        on_progress: ProgressCallback | None,
    ) -> None:
        # OSS policy-based multipart POST (UPLOAD_TYPE_FORM).
        method = (form.get("method") or "POST").upper()
        url = form.get("url") or form.get("URL")
        if not url:
            raise RuntimeError("PikPak form upload missing URL")

        multi = form.get("multi_parts") or form.get("multiParts") or {}
        # Field order matters for some OSS gateways: policy fields first, file last
        field_order = [
            "OSSAccessKeyId",
            "key",
            "policy",
            "Signature",
            "callback",
            "x:user_data",
        ]
        data: dict[str, str] = {}
        for key in field_order:
            if key in multi and multi[key] is not None:
                data[key] = str(multi[key])
        # Any remaining string fields
        for key, val in multi.items():
            if key in data or key == "file":
                continue
            if isinstance(val, str | int | float):
                data[str(key)] = str(val)

        size = local_path.stat().st_size
        # httpx multipart: pass data fields + file
        async with httpx.AsyncClient(timeout=None, follow_redirects=True) as http:
            with local_path.open("rb") as f:
                files = {
                    "file": (local_path.name, f, "application/octet-stream"),
                }
                resp = await http.request(method, url, data=data, files=files)
                if resp.status_code >= 400:
                    body_snip = (resp.text or "")[:300]
                    raise RuntimeError(
                        f"PikPak FORM upload failed HTTP {resp.status_code}: {body_snip}"
                    )
        if on_progress:
            on_progress(size, size)

    async def _wait_task(self, task_id: str, timeout: float = 300.0) -> None:
        # Poll the PikPak task until complete, error, or timeout (file may still finalize).
        client = self._require()
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                url = f"https://{client.PIKPAK_API_HOST}/drive/v1/tasks/{task_id}"
                info = await client._request_get(url)
                phase = info.get("phase") or ""
                if phase == "PHASE_TYPE_COMPLETE":
                    return
                if phase == "PHASE_TYPE_ERROR":
                    raise RuntimeError(f"PikPak upload task failed: {info}")
            except RuntimeError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.debug("wait task: %s", exc)
            await asyncio.sleep(1.0)
        # soft timeout — file may still finalize
        logger.warning("PikPak task %s wait timed out", task_id)


pikpak_adapter = PikPakAdapter()
