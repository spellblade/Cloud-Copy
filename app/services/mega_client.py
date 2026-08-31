# MEGA adapter: mega.py wrapped for asyncio, with MFA login and Windows-safe download.

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.models import FileNode
from app.services.credential_store import credential_store
from app.services.totp_util import get_fresh_totp_code, normalize_totp_secret

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]


def _map_mega_error(err: Any, *, context: str = "MEGA request") -> str:
    # Translate mega RequestError / numeric codes into user-facing messages.
    text = str(err)
    low = text.lower()
    if "eoverquota" in low or "over quota" in low or "overquota" in low:
        return (
            "MEGA transfer quota exceeded (common on free accounts when downloading). "
            "Wait for the quota window to reset, or upgrade MEGA. This is not a bug in Cloud Copy."
        )

    code: Any = err
    if hasattr(err, "args") and err.args:
        code = err.args[0]
    try:
        code_int = int(code)
    except (TypeError, ValueError):
        if "mfa" in low or "2fa" in low or "-26" in text:
            return (
                "MEGA requires a 2FA code. Enter the 6-digit code from your "
                "authenticator app and try again."
            )
        return f"{context} failed: {err}"

    # Common MEGA API error codes (see mega.js error table)
    if code_int == -17:  # EOVERQUOTA
        return (
            "MEGA transfer quota exceeded (common on free accounts when downloading). "
            "Wait for the quota window to reset, or upgrade MEGA. This is not a bug in Cloud Copy."
        )
    if code_int == -26:
        return (
            "MEGA requires a 2FA code. Enter the 6-digit code from your "
            "authenticator app and try again."
        )
    if code_int in (-9, -15, -16):
        return "MEGA login failed: invalid email or password."
    if code_int == -8:
        return "MEGA login failed: invalid or expired 2FA code. Try a fresh code."
    return f"{context} failed (error {code_int})."


def _map_mega_login_error(err: Any) -> str:
    # Same mapping as ``_map_mega_error``, labeled as a login failure.
    return _map_mega_error(err, context="MEGA login")


class MegaAdapter:
    # Adapter around mega.py (sync API wrapped for asyncio).

    def __init__(self) -> None:
        self._m: Any = None
        self._username: str | None = None
        self._totp_secret: str | None = None
        self._files_cache: dict[str, Any] = {}

    @property
    def username(self) -> str | None:
        # Email used for the current MEGA session, if any.
        return self._username

    @property
    def totp_configured(self) -> bool:
        # True when a TOTP secret is in memory (the secret itself is never returned).
        return bool(self._totp_secret)

    def is_authenticated(self) -> bool:
        # True after a successful login (mega.py client is held in ``_m``).
        return self._m is not None

    def _resolve_totp_secret(
        self,
        totp_secret: str | None = None,
        use_saved: bool = True,
    ) -> str | None:
        # Prefer request secret, then in-memory, then store, then env.
        candidates: list[str | None] = [totp_secret]
        if use_saved:
            candidates.append(self._totp_secret)
            saved = credential_store.get("mega") or {}
            candidates.append(saved.get("totp_secret"))
        candidates.append(os.environ.get("MEGA_TOTP_SECRET"))
        for raw in candidates:
            if raw and str(raw).strip():
                return normalize_totp_secret(str(raw))
        return None

    def _resolve_mfa_code(
        self,
        mfa_code: str | None = None,
        totp_secret: str | None = None,
    ) -> str | None:
        """Resolve the MFA code for login.
        
        Args:
            mfa_code: The MFA code provided by the user.
            totp_secret: The TOTP secret for generating a fresh code.

        Returns:
            The resolved MFA code, or None if not available.
        
        1) Explicit one-shot mfa_code
        2) Fresh code from TOTP secret (request / saved / env)
        """
        manual = (mfa_code or "").strip()
        if manual:
            return manual
        secret = self._resolve_totp_secret(totp_secret=totp_secret, use_saved=True)
        if not secret:
            return None
        # Generate at the last moment (may sleep briefly near window end)
        return get_fresh_totp_code(secret)

    async def login(
        self,
        username: str,
        password: str,
        mfa_code: str | None = None,
        totp_secret: str | None = None,
        persist: bool = True,
    ) -> None:
        """Log in (optionally minting a fresh TOTP) and optionally persist credentials.
        
        Resolve secret for persistence even if user only uses env this time
        """
        secret_to_store = None
        if totp_secret and totp_secret.strip():
            secret_to_store = normalize_totp_secret(totp_secret)
        elif self._resolve_totp_secret(totp_secret=None, use_saved=True):
            # keep existing saved/env secret when re-login without re-pasting
            secret_to_store = self._resolve_totp_secret(use_saved=True)

        def _login() -> Any:
            code = self._resolve_mfa_code(mfa_code=mfa_code, totp_secret=totp_secret)
            return self._login_with_mfa(username, password, code)

        try:
            self._m = await asyncio.to_thread(_login)
        except Exception as exc:  # noqa: BLE001
            self._m = None
            self._username = None
            raise RuntimeError(str(exc)) from exc

        self._username = username
        if secret_to_store:
            self._totp_secret = secret_to_store
        if persist:
            payload: dict[str, Any] = {
                "username": username,
                "password": password,
            }
            # Preserve previous totp_secret if this login didn't supply a new one
            existing = credential_store.get("mega") or {}
            final_secret = secret_to_store or existing.get("totp_secret")
            if final_secret:
                payload["totp_secret"] = normalize_totp_secret(str(final_secret))
                self._totp_secret = payload["totp_secret"]
            credential_store.set("mega", payload)
        await self._refresh_files_cache()

    @staticmethod
    def _login_with_mfa(email: str, password: str, mfa_code: str | None) -> Any:
        """Login via mega.py internals, with optional MEGA MFA (2FA) code.
        
        mega.py's public login() never sends ``mfa``. MEGA expects:
        ``{ a: 'us', user, uh, mfa?: '<6-digit>' }`` when 2FA is enabled.
        """
        import hashlib

        from mega import Mega
        from mega.crypto import (
            a32_to_str,
            base64_to_a32,
            base64_url_encode,
            prepare_key,
            str_to_a32,
            stringhash,
        )
        from mega.errors import RequestError

        mega = Mega()
        email_l = email.lower().strip()
        logger.info("Logging in MEGA user (mfa_provided=%s)...", bool(mfa_code))

        get_user_salt_resp = mega._api_request({"a": "us0", "user": email_l})
        try:
            user_salt = base64_to_a32(get_user_salt_resp["s"])
        except (KeyError, TypeError):
            # v1 account
            password_aes = prepare_key(str_to_a32(password))
            user_hash = stringhash(email_l, password_aes)
        else:
            # v2 account
            pbkdf2_key = hashlib.pbkdf2_hmac(
                hash_name="sha512",
                password=password.encode(),
                salt=a32_to_str(user_salt),
                iterations=100000,
                dklen=32,
            )
            password_aes = str_to_a32(pbkdf2_key[:16])
            user_hash = base64_url_encode(pbkdf2_key[-16:])

        request: dict[str, Any] = {"a": "us", "user": email_l, "uh": user_hash}
        if mfa_code:
            request["mfa"] = mfa_code

        try:
            resp = mega._api_request(request)
        except RequestError as exc:
            raise RuntimeError(_map_mega_login_error(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"MEGA login failed: {exc}") from exc

        if isinstance(resp, int):
            # MEGA returns numeric API codes; this is a login failure, not a Python type error.
            raise RuntimeError(_map_mega_login_error(resp))  # noqa: TRY004

        try:
            mega._login_process(resp, password_aes)
            trash = mega.get_node_by_type(4)
            if trash:
                mega._trash_folder_node_id = trash[0]
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"MEGA login failed: {exc}") from exc

        logger.info("MEGA login complete")
        return mega

    async def restore_session(self) -> bool:
        # Re-login from ``credentials.json`` on app start. Returns False if nothing saved.
        saved = credential_store.get("mega")
        if not saved or not saved.get("username") or not saved.get("password"):
            return False
        if saved.get("totp_secret"):
            self._totp_secret = normalize_totp_secret(str(saved["totp_secret"]))
        try:
            # Generates a fresh TOTP from saved secret / env when needed
            await self.login(
                saved["username"],
                saved["password"],
                totp_secret=saved.get("totp_secret"),
                persist=False,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "MEGA session restore failed: %s",
                exc,
            )
            return False

    async def logout(self) -> None:
        # Drop the session and delete saved MEGA credentials.
        self._m = None
        self._username = None
        self._totp_secret = None
        self._files_cache = {}
        credential_store.delete("mega")

    def _require(self) -> Any:
        # Return the mega.py client or raise if not logged in.
        if self._m is None:
            raise RuntimeError("Not logged in to MEGA")
        return self._m

    async def _refresh_files_cache(self) -> None:
        # Reload MEGA's full node map on a worker thread (sync mega.py call).
        m = self._require()

        def _get() -> dict[str, Any]:
            return m.get_files() or {}

        self._files_cache = await asyncio.to_thread(_get)

    def _root_id(self) -> str:
        # Cloud-drive root handle (type 2), used when listing with no parent.
        m = self._require()
        if hasattr(m, "root_id") and m.root_id:
            return m.root_id
        node = m.get_node_by_type(2)
        if not node:
            raise RuntimeError("Could not resolve MEGA root")
        return node[0]

    def _node_to_file(self, handle: str, node: dict[str, Any]) -> FileNode:
        # Map a mega.py node dict onto our ``FileNode`` (type 1 = folder).
        attrs = node.get("a") or {}
        name = attrs.get("n") or handle
        is_dir = int(node.get("t", 0)) == 1
        size = int(node.get("s") or 0)
        # ts may be present on some nodes
        modified = None
        if node.get("ts"):
            modified = str(node.get("ts"))
        return FileNode(
            id=handle,
            name=name,
            is_dir=is_dir,
            size=size,
            modified_at=modified,
            parent_id=node.get("p"),
        )

    async def list_folder(self, folder_id: str | None = None) -> list[FileNode]:
        # Children of ``folder_id`` (root if omitted); folders first, then name.
        await self._refresh_files_cache()
        parent = folder_id or self._root_id()
        items: list[FileNode] = []
        for handle, node in self._files_cache.items():
            if not node.get("a"):
                continue
            if node.get("p") != parent:
                continue
            # skip special nodes
            if int(node.get("t", 0)) in (2, 3, 4):
                continue
            items.append(self._node_to_file(handle, node))
        items.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        return items

    def _get_node_pair(self, file_id: str) -> tuple[str, dict[str, Any]]:
        # Look up a handle in the cache; refresh once if missing.
        node = self._files_cache.get(file_id)
        if not node:
            # try refresh sync
            m = self._require()
            self._files_cache = m.get_files() or {}
            node = self._files_cache.get(file_id)
        if not node:
            raise FileNotFoundError(f"MEGA file not found: {file_id}")
        return file_id, node

    async def get_node(self, file_id: str) -> FileNode:
        # Refresh cache and return one node (used when transfer meta lacks a name).
        await self._refresh_files_cache()
        handle, node = self._get_node_pair(file_id)
        return self._node_to_file(handle, node)

    async def mkdir(self, parent_id: str | None, name: str) -> FileNode:
        """Create a folder under ``parent_id``, or return one that already exists there.

        mega.py ``create_folder`` looks up names from the cloud-drive root, so a
        nested dest can reuse the wrong folder. We list the parent ourselves and
        call ``_mkdir`` only when the name is free in that folder.
        """
        dest = parent_id or self._root_id()
        for item in await self.list_folder(dest):
            if item.is_dir and item.name == name:
                return item

        m = self._require()

        def _mkdir() -> str:
            created = m._mkdir(name=name, parent_node_id=dest)
            files = created.get("f") if isinstance(created, dict) else None
            if not files:
                raise RuntimeError(f"MEGA mkdir returned no node for {name!r}")
            return files[0]["h"]

        folder_id = await asyncio.to_thread(_mkdir)
        await self._refresh_files_cache()
        return await self.get_node(folder_id)

    async def download_to_path(
        self,
        file_id: str,
        dest_dir: Path,
        on_progress: ProgressCallback | None = None,
    ) -> Path:
        """ Download a MEGA file to dest_dir with a Windows-safe write path.
        mega.py's download() uses NamedTemporaryFile + shutil.move while the
        handle is still open, which raises WinError 32 on Windows. We stream
        decrypt into our own partial file, close it, then rename.
        """
        m = self._require()
        await self._refresh_files_cache()
        pair = self._get_node_pair(file_id)
        node = pair[1]
        name = (node.get("a") or {}).get("n") or file_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        def _download() -> Path:
            try:
                return self._download_file_windows_safe(
                    m, node, dest_dir, name, on_progress
                )
            except Exception as exc:  # noqa: BLE001
                # Surface MEGA quota etc. clearly
                raise RuntimeError(_map_mega_error(exc, context="MEGA download")) from exc

        return await asyncio.to_thread(_download)

    @staticmethod
    def _download_file_windows_safe(
        mega: Any,
        file_node: dict[str, Any],
        dest_dir: Path,
        file_name: str,
        on_progress: ProgressCallback | None = None,
    ) -> Path:
        # Stream-decrypt MEGA chunks into ``.partial``, close, then rename to the final name.
        import requests
        from Crypto.Cipher import AES
        from Crypto.Util import Counter
        from mega.crypto import a32_to_str, get_chunks, str_to_a32
        from mega.errors import RequestError

        # Processed node from get_files() already has k, iv, meta_mac, h
        file_data = mega._api_request({"a": "g", "g": 1, "n": file_node["h"]})
        if isinstance(file_data, int) or "g" not in file_data:
            raise RuntimeError(
                "MEGA file not accessible (download link missing). "
                "Try again later or re-login."
            )

        file_url = file_data["g"]
        file_size = int(file_data.get("s") or file_node.get("s") or 0)
        k = file_node["k"]
        iv = file_node["iv"]
        meta_mac = file_node["meta_mac"]

        final_path = dest_dir / file_name
        partial_path = dest_dir / f".{file_name}.partial"
        if partial_path.exists():
            try:
                partial_path.unlink()
            except OSError:
                pass

        k_str = a32_to_str(k)
        counter = Counter.new(
            128, initial_value=((iv[0] << 32) + iv[1]) << 64
        )
        aes = AES.new(k_str, AES.MODE_CTR, counter=counter)

        mac_str = b"\0" * 16
        mac_encryptor = AES.new(k_str, AES.MODE_CBC, mac_str)
        iv_str = a32_to_str([iv[0], iv[1], iv[0], iv[1]])

        written = 0
        try:
            with requests.get(file_url, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                raw = resp.raw
                with partial_path.open("wb") as out:
                    for _chunk_start, chunk_size in get_chunks(file_size):
                        chunk = raw.read(chunk_size)
                        if not chunk:
                            break
                        chunk = aes.decrypt(chunk)
                        out.write(chunk)
                        written += len(chunk)

                        encryptor = AES.new(k_str, AES.MODE_CBC, iv_str)
                        i = 0
                        for i in range(0, len(chunk) - 16, 16):
                            block = chunk[i : i + 16]
                            encryptor.encrypt(block)

                        if file_size > 16:
                            i += 16
                        else:
                            i = 0

                        block = chunk[i : i + 16]
                        if len(block) % 16:
                            block += b"\0" * (16 - (len(block) % 16))
                        mac_str = mac_encryptor.encrypt(encryptor.encrypt(block))

                        if on_progress and file_size:
                            on_progress(written, file_size)

            file_mac = str_to_a32(mac_str)
            if (file_mac[0] ^ file_mac[1], file_mac[2] ^ file_mac[3]) != meta_mac:
                raise ValueError("MEGA download integrity check failed (MAC mismatch)")

            # Handle closed above; safe to rename on Windows
            if final_path.exists():
                final_path.unlink()
            partial_path.replace(final_path)
        except Exception:
            try:
                if partial_path.exists():
                    partial_path.unlink()
            except OSError:
                pass
            raise
        finally:
            # Drop any lingering megapy_* leftovers are not used here
            pass

        if on_progress and file_size:
            on_progress(file_size, file_size)
        return final_path

    async def upload_from_path(
        self,
        local_path: Path,
        parent_id: str | None,
        name: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> FileNode:
        # Upload a local file into ``parent_id`` via mega.py (sync, on a thread).
        m = self._require()
        dest = parent_id or self._root_id()
        dest_name = name or local_path.name
        size = local_path.stat().st_size

        def _upload() -> Any:
            return m.upload(str(local_path), dest=dest, dest_filename=dest_name)

        await asyncio.to_thread(_upload)
        if on_progress and size:
            on_progress(size, size)
        await self._refresh_files_cache()
        # Find uploaded file by name under parent
        for handle, node in self._files_cache.items():
            attrs = node.get("a") or {}
            if node.get("p") == dest and attrs.get("n") == dest_name and int(node.get("t", 0)) == 0:
                return self._node_to_file(handle, node)
        # Fallback synthetic node
        return FileNode(id="", name=dest_name, is_dir=False, size=size, parent_id=dest)


mega_adapter = MegaAdapter()
