from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import FileNode
from app.services.mega_client import MegaAdapter, mega_adapter
from app.services.pikpak_client import PikPakAdapter, pikpak_adapter


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(mega_adapter, "restore_session", AsyncMock(return_value=False))
    monkeypatch.setattr(pikpak_adapter, "restore_session", AsyncMock(return_value=False))
    with TestClient(app) as test_client:
        yield test_client


def _folder(item_id: str, name: str, parent_id: str | None = None) -> FileNode:
    return FileNode(id=item_id, name=name, is_dir=True, parent_id=parent_id)


def _file(item_id: str, name: str) -> FileNode:
    return FileNode(id=item_id, name=name, is_dir=False, size=10)


def test_mkdir_unauthorized(client, monkeypatch):
    monkeypatch.setattr(mega_adapter, "is_authenticated", lambda: False)
    res = client.post("/api/files/mega", json={"name": "Docs"})
    assert res.status_code == 401


def test_mkdir_success(client, monkeypatch):
    monkeypatch.setattr(mega_adapter, "is_authenticated", lambda: True)
    monkeypatch.setattr(mega_adapter, "list_folder", AsyncMock(return_value=[]))
    created = _folder("n1", "Docs", parent_id=None)
    mkdir = AsyncMock(return_value=created)
    monkeypatch.setattr(mega_adapter, "mkdir", mkdir)

    res = client.post("/api/files/mega", json={"parent_id": None, "name": "  Docs  "})
    assert res.status_code == 200
    assert res.json()["id"] == "n1"
    assert res.json()["name"] == "Docs"
    mkdir.assert_awaited_once_with(None, "Docs")


def test_mkdir_duplicate_conflict(client, monkeypatch):
    monkeypatch.setattr(mega_adapter, "is_authenticated", lambda: True)
    monkeypatch.setattr(
        mega_adapter,
        "list_folder",
        AsyncMock(return_value=[_folder("old", "Docs")]),
    )
    mkdir = AsyncMock()
    monkeypatch.setattr(mega_adapter, "mkdir", mkdir)

    res = client.post("/api/files/mega", json={"name": "Docs"})
    assert res.status_code == 409
    assert "already exists" in res.json()["detail"]
    mkdir.assert_not_called()


@pytest.mark.parametrize("name", ["", "   ", "a/b", r"a\b"])
def test_mkdir_invalid_name(client, monkeypatch, name):
    monkeypatch.setattr(mega_adapter, "is_authenticated", lambda: True)
    mkdir = AsyncMock()
    monkeypatch.setattr(mega_adapter, "mkdir", mkdir)
    res = client.post("/api/files/mega", json={"name": name})
    assert res.status_code == 400
    mkdir.assert_not_called()


def test_delete_unauthorized(client, monkeypatch):
    monkeypatch.setattr(pikpak_adapter, "is_authenticated", lambda: False)
    res = client.delete("/api/files/pikpak/folder1")
    assert res.status_code == 401


def test_delete_rejects_file(client, monkeypatch):
    monkeypatch.setattr(mega_adapter, "is_authenticated", lambda: True)
    monkeypatch.setattr(mega_adapter, "get_node", AsyncMock(return_value=_file("f1", "a.txt")))
    delete_folder = AsyncMock()
    monkeypatch.setattr(mega_adapter, "delete_folder", delete_folder)

    res = client.delete("/api/files/mega/f1")
    assert res.status_code == 400
    assert "folders" in res.json()["detail"]
    delete_folder.assert_not_called()


def test_delete_folder_calls_trash(client, monkeypatch):
    monkeypatch.setattr(mega_adapter, "is_authenticated", lambda: True)
    monkeypatch.setattr(
        mega_adapter,
        "get_node",
        AsyncMock(return_value=_folder("folder1", "Docs")),
    )
    delete_folder = AsyncMock()
    monkeypatch.setattr(mega_adapter, "delete_folder", delete_folder)

    res = client.delete("/api/files/mega/folder1")
    assert res.status_code == 200
    assert res.json()["ok"] is True
    delete_folder.assert_awaited_once_with("folder1")


def test_delete_missing_folder(client, monkeypatch):
    monkeypatch.setattr(mega_adapter, "is_authenticated", lambda: True)
    monkeypatch.setattr(
        mega_adapter,
        "get_node",
        AsyncMock(side_effect=FileNotFoundError("MEGA file not found: missing")),
    )
    res = client.delete("/api/files/mega/missing")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_mega_delete_folder_moves_to_trash_not_destroy():
    adapter = MegaAdapter()
    mega = MagicMock()
    mega.delete.return_value = 0
    mega.get_files.return_value = {}
    adapter._m = mega

    await adapter.delete_folder("folder1")

    mega.delete.assert_called_once_with("folder1")
    mega.destroy.assert_not_called()
    mega.get_files.assert_called()


@pytest.mark.asyncio
async def test_pikpak_delete_folder_uses_trash_not_forever():
    adapter = PikPakAdapter()
    client = MagicMock()
    client.delete_to_trash = AsyncMock(return_value={})
    client.delete_forever = AsyncMock(return_value={})
    adapter._client = client

    await adapter.delete_folder("abc")

    client.delete_to_trash.assert_awaited_once_with(["abc"])
    client.delete_forever.assert_not_called()
