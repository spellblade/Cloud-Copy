from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000
    app_name: str = "Cloud Copy"
    # Persist sessions under user home by default
    data_dir: Path | None = None
    temp_dir: Path | None = None

    def resolved_data_dir(self) -> Path:
        if self.data_dir:
            path = Path(self.data_dir)
        else:
            path = Path.home() / ".cloud-copy"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolved_temp_dir(self) -> Path:
        if self.temp_dir:
            path = Path(self.temp_dir)
        else:
            path = self.resolved_data_dir() / "temp"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def credentials_path(self) -> Path:
        return self.resolved_data_dir() / "credentials.json"


settings = Settings()
