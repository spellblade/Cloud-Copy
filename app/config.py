# Runtime settings from environment / ``.env`` (host, port, data and temp dirs).

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App bind address and on-disk paths; unset dirs default under ``~/.cloud-copy``.

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000
    app_name: str = "Cloud Copy"
    # Persist sessions under user home by default
    data_dir: Path | None = None
    temp_dir: Path | None = None

    def resolved_data_dir(self) -> Path:
        # Config data dir, or ``~/.cloud-copy``; creates the directory if missing.
        if self.data_dir:
            path = Path(self.data_dir)
        else:
            path = Path.home() / ".cloud-copy"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolved_temp_dir(self) -> Path:
        # Staging dir for local-relay downloads; defaults to ``<data>/temp``.
        if self.temp_dir:
            path = Path(self.temp_dir)
        else:
            path = self.resolved_data_dir() / "temp"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def credentials_path(self) -> Path:
        # JSON file used by ``CredentialStore`` for session restore.
        return self.resolved_data_dir() / "credentials.json"


settings = Settings()
