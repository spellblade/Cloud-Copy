from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.mega_client import MegaAdapter, mega_adapter
from app.services.pikpak_client import pikpak_adapter


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(mega_adapter, "restore_session", AsyncMock(return_value=False))
    monkeypatch.setattr(pikpak_adapter, "restore_session", AsyncMock(return_value=False))
    with TestClient(app) as test_client:
        yield test_client


def test_auth_status_surfaces_restore_error(client, monkeypatch):
    monkeypatch.setattr(mega_adapter, "is_authenticated", lambda: False)
    mega_adapter.last_error = "MEGA login failed: invalid or expired 2FA code."
    try:
        res = client.get("/api/auth/status")
        assert res.status_code == 200
        assert res.json()["mega"]["connected"] is False
        assert "2FA" in res.json()["mega"]["error"]
        assert res.json()["pikpak"]["error"] is None
    finally:
        mega_adapter.last_error = None


def test_auth_status_hides_error_when_connected(client, monkeypatch):
    monkeypatch.setattr(mega_adapter, "is_authenticated", lambda: True)
    mega_adapter.last_error = "stale"
    try:
        res = client.get("/api/auth/status")
        assert res.json()["mega"]["error"] is None
    finally:
        mega_adapter.last_error = None


@pytest.mark.asyncio
async def test_mega_restore_sets_last_error(monkeypatch):
    adapter = MegaAdapter()
    monkeypatch.setattr(
        "app.services.mega_client.credential_store.get",
        lambda _p: {"username": "u@x", "password": "p"},
    )
    monkeypatch.setattr(
        adapter, "login", AsyncMock(side_effect=RuntimeError("invalid or expired 2FA code"))
    )
    ok = await adapter.restore_session()
    assert ok is False
    assert adapter.last_error is not None
    assert "2FA" in adapter.last_error


@pytest.mark.asyncio
async def test_mega_restore_without_saved_creds_does_not_set_error(monkeypatch):
    adapter = MegaAdapter()
    monkeypatch.setattr("app.services.mega_client.credential_store.get", lambda _p: None)
    ok = await adapter.restore_session()
    assert ok is False
    assert adapter.last_error is None
