from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


Provider = Literal["mega", "pikpak"]
Direction = Literal["mega_to_pikpak", "pikpak_to_mega"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    # MEGA: one-shot 6-digit authenticator code (optional override)
    mfa_code: Optional[str] = None
    # MEGA: base32 TOTP secret from 2FA setup; stored locally, used to mint fresh codes
    totp_secret: Optional[str] = None


class AuthProviderStatus(BaseModel):
    connected: bool
    username: Optional[str] = None
    error: Optional[str] = None
    # True when a TOTP secret is saved (never return the secret itself)
    totp_configured: bool = False


class AuthStatus(BaseModel):
    mega: AuthProviderStatus
    pikpak: AuthProviderStatus


class FileNode(BaseModel):
    id: str
    name: str
    is_dir: bool
    size: int = 0
    modified_at: Optional[str] = None
    parent_id: Optional[str] = None
    path: Optional[str] = None


class FileListResponse(BaseModel):
    provider: Provider
    parent_id: Optional[str] = None
    items: list[FileNode]


class TransferStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class TransferCreateRequest(BaseModel):
    direction: Direction
    source_ids: list[str] = Field(min_length=1)
    # Destination folder id; null/empty = root
    dest_parent_id: Optional[str] = None
    # Optional display names for selected items (id -> name, is_dir)
    source_meta: dict[str, dict[str, Any]] = Field(default_factory=dict)


class TransferJob(BaseModel):
    id: str
    direction: Direction
    source_ids: list[str]
    dest_parent_id: Optional[str] = None
    source_meta: dict[str, dict[str, Any]] = Field(default_factory=dict)
    status: TransferStatus = TransferStatus.queued
    progress: float = 0.0
    bytes_done: int = 0
    bytes_total: int = 0
    current_file: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()


class TransferListResponse(BaseModel):
    jobs: list[TransferJob]


class MessageResponse(BaseModel):
    ok: bool = True
    message: str = ""
