"""Adapter mkdir reuses a same-name folder (F-014). Transfer calls these, not the files router."""

import pytest

from app.services.mega_client import MegaAdapter
from app.services.pikpak_client import PikPakAdapter


class _FakeMega:
    # In-memory mega.py stand-in: get_files / _mkdir only.

    def __init__(self) -> None:
        self.root_id = "root"
        self.files: dict = {}
        self.mkdir_calls = 0

    def get_files(self) -> dict:
        return dict(self.files)

    def _mkdir(self, name: str, parent_node_id: str) -> dict:
        self.mkdir_calls += 1
        handle = f"f{self.mkdir_calls}"
        self.files[handle] = {"a": {"n": name}, "t": 1, "p": parent_node_id}
        return {"f": [{"h": handle}]}


class _FakePikPak:
    # In-memory pikpakapi stand-in: file_list / create_folder only.

    def __init__(self) -> None:
        self.folders: list[dict] = []
        self.create_calls = 0

    async def file_list(self, size: int = 100, parent_id=None, next_page_token=None) -> dict:
        return {"files": list(self.folders)}

    async def create_folder(self, name: str, parent_id=None) -> dict:
        self.create_calls += 1
        node = {
            "id": f"p{self.create_calls}",
            "name": name,
            "kind": "drive#folder",
            "parent_id": parent_id,
        }
        self.folders.append(node)
        return {"file": node}


@pytest.mark.asyncio
async def test_mega_mkdir_reuses_existing_folder():
    adapter = MegaAdapter()
    mega = _FakeMega()
    mega.files["docs1"] = {"a": {"n": "Docs"}, "t": 1, "p": "root"}
    adapter._m = mega

    first = await adapter.mkdir(None, "Docs")
    second = await adapter.mkdir(None, "Docs")

    assert first.id == "docs1"
    assert second.id == "docs1"
    assert mega.mkdir_calls == 0


@pytest.mark.asyncio
async def test_mega_mkdir_creates_once_then_reuses():
    adapter = MegaAdapter()
    mega = _FakeMega()
    adapter._m = mega

    first = await adapter.mkdir("root", "Docs")
    second = await adapter.mkdir("root", "Docs")

    assert first.id == second.id == "f1"
    assert first.name == "Docs"
    assert mega.mkdir_calls == 1


@pytest.mark.asyncio
async def test_pikpak_mkdir_reuses_existing_folder():
    adapter = PikPakAdapter()
    client = _FakePikPak()
    client.folders.append({"id": "old", "name": "Docs", "kind": "drive#folder"})
    adapter._client = client

    first = await adapter.mkdir(None, "Docs")
    second = await adapter.mkdir(None, "Docs")

    assert first.id == "old"
    assert second.id == "old"
    assert client.create_calls == 0


@pytest.mark.asyncio
async def test_pikpak_mkdir_creates_once_then_reuses():
    adapter = PikPakAdapter()
    client = _FakePikPak()
    adapter._client = client

    first = await adapter.mkdir("parent", "Docs")
    second = await adapter.mkdir("parent", "Docs")

    assert first.id == second.id == "p1"
    assert first.name == "Docs"
    assert client.create_calls == 1
