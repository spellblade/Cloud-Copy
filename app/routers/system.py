# System HTTP routes: data/temp paths and clearing leftover transfer files.

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
from app.models import MessageResponse
from app.services.transfer_service import transfer_service

router = APIRouter(prefix="/api/system", tags=["system"])


class PathsResponse(BaseModel):
    # Where credentials and transfer temp files live on this machine.

    data_dir: str
    temp_dir: str
    credentials_path: str
    temp_exists: bool
    temp_bytes: int
    active_transfers: bool


class ClearTempResponse(BaseModel):
    # Result of wiping ``temp/``: counts, bytes, and per-entry errors.

    ok: bool = True
    message: str = ""
    path: str
    removed_entries: int = 0
    bytes_freed: int = 0
    errors: list[str] = []


def _dir_size(path) -> int:
    # Best-effort recursive size in bytes; missing files are skipped.
    total = 0
    try:
        if not path.exists():
            return 0
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


@router.get("/paths", response_model=PathsResponse)
async def get_paths() -> PathsResponse:
    # Paths shown in the jobs header (temp folder size, data dir).
    data = settings.resolved_data_dir()
    temp = settings.resolved_temp_dir()
    return PathsResponse(
        data_dir=str(data),
        temp_dir=str(temp),
        credentials_path=str(settings.credentials_path()),
        temp_exists=temp.exists(),
        temp_bytes=_dir_size(temp),
        active_transfers=transfer_service.has_active_transfers(),
    )


@router.post("/clear-temp", response_model=ClearTempResponse)
async def clear_temp(
    force: bool = Query(default=False, description="Clear even if transfers are active"),
) -> ClearTempResponse:
    # Delete leftover relay files. 409 if a job is active unless ``force``.
    try:
        result = transfer_service.clear_temp_dir(force=force)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    msg = (
        f"Cleared {result['removed_entries']} item(s), "
        f"~{result['bytes_freed']} bytes from temp"
    )
    if result["errors"]:
        msg += f" ({len(result['errors'])} errors)"
    return ClearTempResponse(
        ok=not result["errors"],
        message=msg,
        path=result["path"],
        removed_entries=result["removed_entries"],
        bytes_freed=result["bytes_freed"],
        errors=result["errors"],
    )
