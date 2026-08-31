# Pydantic models and enums for auth, file listings, and transfer jobs.

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

Provider = Literal["mega", "pikpak"]
Direction = Literal["mega_to_pikpak", "pikpak_to_mega"]


class LoginRequest(BaseModel):
    # Credentials for MEGA or PikPak login; MEGA may also send TOTP secret or a 6-digit code.

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    # MEGA: one-shot 6-digit authenticator code (optional override)
    mfa_code: str | None = None
    # MEGA: base32 TOTP secret from 2FA setup; stored locally, used to mint fresh codes
    totp_secret: str | None = None


class AuthProviderStatus(BaseModel):
    # Connection state for one provider. ``totp_configured`` never includes the secret.

    connected: bool
    username: str | None = None
    error: str | None = None
    # True when a TOTP secret is saved (never return the secret itself)
    totp_configured: bool = False


class AuthStatus(BaseModel):
    # Both providers, as returned by ``GET /api/auth/status``.

    mega: AuthProviderStatus
    pikpak: AuthProviderStatus


class FileNode(BaseModel):
    # One file or folder in a provider listing.

    id: str
    name: str
    is_dir: bool
    size: int = 0
    modified_at: str | None = None
    parent_id: str | None = None
    path: str | None = None


class FileListResponse(BaseModel):
    # Children of ``parent_id`` (null = root) for one provider pane.

    provider: Provider
    parent_id: str | None = None
    items: list[FileNode]


class TransferStatus(str, Enum):
    # Lifecycle of a transfer job (queue → running → terminal).

    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class TransferStage(str, Enum):
    # Which step was last in progress — used when a job fails so the UI can say download vs upload.

    queued = "queued"
    auth = "auth"
    listing = "listing"
    mkdir = "mkdir"
    download = "download"
    upload = "upload"


class TransferCreateRequest(BaseModel):
    # Queue a job: selected source ids, dest folder, and display metadata (name / is_dir).

    direction: Direction
    source_ids: list[str] = Field(min_length=1)
    # Destination folder id; null/empty = root
    dest_parent_id: str | None = None
    # Optional display names for selected items (id -> name, is_dir)
    source_meta: dict[str, dict[str, Any]] = Field(default_factory=dict)


class TransferJob(BaseModel):
    # In-memory transfer record: progress, current file, stage, and cancel/retry state.

    id: str
    direction: Direction
    source_ids: list[str]
    dest_parent_id: str | None = None
    source_meta: dict[str, dict[str, Any]] = Field(default_factory=dict)
    status: TransferStatus = TransferStatus.queued
    progress: float = 0.0
    bytes_done: int = 0
    bytes_total: int = 0
    current_file: str | None = None
    message: str | None = None
    error: str | None = None
    stage: TransferStage | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def touch(self) -> None:
        # Bump ``updated_at`` after a status/progress change.
        self.updated_at = datetime.now(UTC)

    def source_label(self) -> str:
        # Human name of the download side for this direction.
        return "MEGA" if self.direction == "mega_to_pikpak" else "PikPak"

    def dest_label(self) -> str:
        # Human name of the upload side for this direction.
        return "PikPak" if self.direction == "mega_to_pikpak" else "MEGA"

    def stage_label(self) -> str | None:
        # Human-readable stage, e.g. 'MEGA download'.
        if self.stage is None:
            return None
        mapping = {
            TransferStage.download: f"{self.source_label()} download",
            TransferStage.upload: f"{self.dest_label()} upload",
            TransferStage.mkdir: "Create folder",
            TransferStage.listing: "List folder",
            TransferStage.auth: "Sign-in",
            TransferStage.queued: "Queue",
        }
        return mapping.get(self.stage, self.stage.value)


class TransferListResponse(BaseModel):
    # All jobs, newest first (see ``TransferService.list_jobs``).

    jobs: list[TransferJob]


class MessageResponse(BaseModel):
    # Generic ok/message payload for login, logout, and similar actions.

    ok: bool = True
    message: str = ""
