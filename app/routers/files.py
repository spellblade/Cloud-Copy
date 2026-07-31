from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models import FileListResponse, Provider
from app.services.mega_client import mega_adapter
from app.services.pikpak_client import pikpak_adapter

router = APIRouter(prefix="/api/files", tags=["files"])


def _adapter(provider: Provider):
    if provider == "mega":
        return mega_adapter
    return pikpak_adapter


@router.get("/{provider}", response_model=FileListResponse)
async def list_files(
    provider: Provider,
    parent: Optional[str] = Query(default=None, description="Folder id; omit for root"),
) -> FileListResponse:
    adapter = _adapter(provider)
    if not adapter.is_authenticated():
        raise HTTPException(status_code=401, detail=f"Not logged in to {provider}")
    try:
        items = await adapter.list_folder(parent or None)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileListResponse(provider=provider, parent_id=parent, items=items)
