# Local JSON store for MEGA/PikPak credentials used to restore sessions.

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Optional

from app.config import settings


class CredentialStore:
    # Simple JSON credential store under the user data directory.

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.credentials_path()
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, Any]:
        # Load the JSON file; missing or corrupt files count as empty.
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        # Overwrite the file; caller holds ``_lock``.
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

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
