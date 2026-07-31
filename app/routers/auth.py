from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import (
    AuthProviderStatus,
    AuthStatus,
    LoginRequest,
    MessageResponse,
    Provider,
)
from app.services.mega_client import mega_adapter
from app.services.pikpak_client import pikpak_adapter

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status", response_model=AuthStatus)
async def auth_status() -> AuthStatus:
    return AuthStatus(
        mega=AuthProviderStatus(
            connected=mega_adapter.is_authenticated(),
            username=mega_adapter.username,
            totp_configured=mega_adapter.totp_configured,
        ),
        pikpak=AuthProviderStatus(
            connected=pikpak_adapter.is_authenticated(),
            username=pikpak_adapter.username,
            totp_configured=False,
        ),
    )


@router.post("/mega", response_model=MessageResponse)
async def login_mega(body: LoginRequest) -> MessageResponse:
    try:
        await mega_adapter.login(
            body.username,
            body.password,
            mfa_code=body.mfa_code,
            totp_secret=body.totp_secret,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    msg = "Connected to MEGA"
    if mega_adapter.totp_configured:
        msg += " (TOTP auto-login saved)"
    return MessageResponse(ok=True, message=msg)


@router.post("/pikpak", response_model=MessageResponse)
async def login_pikpak(body: LoginRequest) -> MessageResponse:
    try:
        await pikpak_adapter.login(body.username, body.password)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageResponse(ok=True, message="Connected to PikPak")


@router.delete("/{provider}", response_model=MessageResponse)
async def logout(provider: Provider) -> MessageResponse:
    if provider == "mega":
        await mega_adapter.logout()
    else:
        await pikpak_adapter.logout()
    return MessageResponse(ok=True, message=f"Logged out of {provider}")
