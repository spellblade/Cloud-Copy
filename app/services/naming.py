# Shared name checks: local download paths and dest folder mkdir.

from __future__ import annotations

from pathlib import Path


def safe_local_name(name: str) -> str:
    """Last path component only. Reject empty, ``.``, and ``..``."""
    normalized = (name or "").replace("\\", "/")
    base = Path(normalized).name
    if not base or base in {".", ".."} or "/" in base or "\\" in base:
        raise ValueError("File name is not safe for a local path")
    return base


def require_folder_name(name: str) -> str:
    """Strip; reject empty names and path separators (New folder and transfer mkdir)."""
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValueError("Folder name is required")
    if "/" in cleaned or "\\" in cleaned:
        raise ValueError("Folder name cannot contain /")
    return cleaned
