# File-listing HTTP routes for MEGA and PikPak panes (list, mkdir, trash-delete).

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models import FileCreateRequest, FileListResponse, FileNode, MessageResponse, Provider
from app.services.mega_client import mega_adapter
from app.services.pikpak_client import pikpak_adapter

router = APIRouter(prefix="/api/files", tags=["files"])


def _adapter(provider: Provider):
    # Return the MEGA or PikPak adapter singleton for this request.
    if provider == "mega":
        return mega_adapter
    return pikpak_adapter


def _require_adapter(provider: Provider):
    # Same as ``_adapter`` but 401 when that cloud is not logged in.
    adapter = _adapter(provider)
    if not adapter.is_authenticated():
        raise HTTPException(status_code=401, detail=f"Not logged in to {provider}")
    return adapter


def _folder_name(name: str) -> str:
    # Strip; reject empty names and path separators.
    cleaned = (name or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Folder name is required")
    if "/" in cleaned or "\\" in cleaned:
        raise HTTPException(status_code=400, detail="Folder name cannot contain /")
    return cleaned


@router.get("/{provider}", response_model=FileListResponse)
async def list_files(
    provider: Provider,
    parent: Optional[str] = Query(default=None, description="Folder id; omit for root"),
) -> FileListResponse:
    # List children of ``parent`` (omit for root). Requires a live login.
    adapter = _require_adapter(provider)
    try:
        items = await adapter.list_folder(parent or None)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileListResponse(provider=provider, parent_id=parent, items=items)


@router.post("/{provider}", response_model=FileNode)
async def create_folder(provider: Provider, body: FileCreateRequest) -> FileNode:
    # New folder in ``parent_id`` (omit/null = root). 409 if that name already exists.
    adapter = _require_adapter(provider)
    name = _folder_name(body.name)
    parent = body.parent_id or None
    try:
        existing = await adapter.list_folder(parent)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if any(item.is_dir and item.name == name for item in existing):
        raise HTTPException(status_code=409, detail=f"Folder {name!r} already exists")
    try:
        return await adapter.mkdir(parent, name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{provider}/{item_id}", response_model=MessageResponse)
async def delete_folder(provider: Provider, item_id: str) -> MessageResponse:
    # Move a folder (and its contents) to MEGA/PikPak trash. Files are rejected.
    adapter = _require_adapter(provider)
    try:
        node = await adapter.get_node(item_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not node.is_dir:
        raise HTTPException(status_code=400, detail="Only folders can be deleted from the pane")
    try:
        await adapter.delete_folder(item_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageResponse(ok=True, message=f"Moved {node.name!r} to trash")
