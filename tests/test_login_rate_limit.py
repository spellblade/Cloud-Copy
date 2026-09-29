from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.login_rate_limit import login_rate_limiter
from app.services.mega_client import mega_adapter
from app.services.pikpak_client import pikpak_adapter

_LOGIN = {"username": "user@example.com", "password": "secret"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(mega_adapter, "restore_session", AsyncMock(return_value=False))
    monkeypatch.setattr(pikpak_adapter, "restore_session", AsyncMock(return_value=False))
    monkeypatch.setattr(mega_adapter, "login", AsyncMock(side_effect=RuntimeError("bad login")))
    monkeypatch.setattr(settings, "auth_login_max_attempts", 3)
    monkeypatch.setattr(settings, "auth_login_window_s", 60.0)
    login_rate_limiter.reset()
    with TestClient(app) as test_client:
        yield test_client


def test_login_mega_rate_limited_after_threshold(client):
    for _ in range(3):
        res = client.post("/api/auth/mega", json=_LOGIN)
        assert res.status_code == 400
    limited = client.post("/api/auth/mega", json=_LOGIN)
    assert limited.status_code == 429
    assert limited.headers.get("retry-after")
    assert "Too many login" in limited.json()["detail"]


def test_auth_status_and_logout_not_rate_limited(client, monkeypatch):
    monkeypatch.setattr(mega_adapter, "logout", AsyncMock())
    for _ in range(3):
        assert client.post("/api/auth/mega", json=_LOGIN).status_code == 400
    assert client.post("/api/auth/mega", json=_LOGIN).status_code == 429
    assert client.get("/api/auth/status").status_code == 200
    assert client.delete("/api/auth/mega").status_code == 200


def test_login_pikpak_shares_limit_with_mega(client, monkeypatch):
    monkeypatch.setattr(
        pikpak_adapter, "login", AsyncMock(side_effect=RuntimeError("bad login"))
    )
    for _ in range(2):
        assert client.post("/api/auth/mega", json=_LOGIN).status_code == 400
    assert client.post("/api/auth/pikpak", json=_LOGIN).status_code == 400
    assert client.post("/api/auth/pikpak", json=_LOGIN).status_code == 429
