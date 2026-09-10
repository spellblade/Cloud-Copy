# Local JSON store for MEGA/PikPak credentials used to restore sessions.

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

from app.config import settings


def _chmod(path: Path, mode: int) -> None:
    # Restrict POSIX modes. On Windows this only toggles the read-only bit; skip.
    if os.name == "nt":
        return
    try:
        os.chmod(path, mode)
    except OSError:
        pass


class CredentialStore:
    # Simple JSON credential store under the user data directory.

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.credentials_path()
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _chmod(self.path.parent, 0o700)
        if self.path.exists():
            _chmod(self.path, 0o600)

    def _read(self) -> dict[str, Any]:
        # Load the JSON file; missing or corrupt files count as empty.
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        # Atomic replace; POSIX file mode 0600 from create. Caller holds ``_lock``.
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = json.dumps(data, indent=2)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(tmp, flags, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                fd = -1
                handle.write(payload)
        except Exception:
            if fd >= 0:
                os.close(fd)
            raise
        _chmod(tmp, 0o600)
        os.replace(tmp, self.path)
        _chmod(self.path, 0o600)

    def get(self, provider: str) -> Optional[dict[str, Any]]:
        # Return the saved payload for ``mega`` or ``pikpak``, or None.
        with self._lock:
            return self._read().get(provider)

    def set(self, provider: str, payload: dict[str, Any]) -> None:
        # Replace the saved payload for one provider (passwords/tokens included).
        with self._lock:
            data = self._read()
            data[provider] = payload
            self._write(data)

    def delete(self, provider: str) -> None:
        # Remove one provider's entry on logout.
        with self._lock:
            data = self._read()
            data.pop(provider, None)
            self._write(data)


credential_store = CredentialStore()
