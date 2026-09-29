"""MEGA adapter refetches get_files only when the cache is dirty (F-003)."""

import pytest

from app.services.mega_client import MegaAdapter


class _FakeMega:
    def __init__(self) -> None:
        self.root_id = "root"
        self.files: dict = {}
        self.get_files_calls = 0
        self.mkdir_calls = 0

    def get_files(self) -> dict:
        self.get_files_calls += 1
        return dict(self.files)

    def _mkdir(self, name: str, parent_node_id: str) -> dict:
        self.mkdir_calls += 1
        handle = f"f{self.mkdir_calls}"
        self.files[handle] = {"a": {"n": name}, "t": 1, "p": parent_node_id}
        return {"f": [{"h": handle}]}

    def delete(self, item_id: str) -> None:
        self.files.pop(item_id, None)


@pytest.mark.asyncio
async def test_list_folder_reuses_cache_without_mutation():
    adapter = MegaAdapter()
    mega = _FakeMega()
    mega.files["a"] = {"a": {"n": "a.txt"}, "t": 0, "p": "root", "s": 1}
    adapter._m = mega

    first = await adapter.list_folder(None)
    second = await adapter.list_folder(None)

    assert [n.name for n in first] == ["a.txt"]
    assert [n.name for n in second] == ["a.txt"]
    assert mega.get_files_calls == 1


@pytest.mark.asyncio
async def test_mkdir_does_not_fetch_three_times():
    adapter = MegaAdapter()
    mega = _FakeMega()
    adapter._m = mega

    created = await adapter.mkdir("root", "Docs")

    assert created.name == "Docs"
    assert mega.mkdir_calls == 1
    assert mega.get_files_calls == 2


@pytest.mark.asyncio
async def test_list_folder_sees_mkdir_then_reuses():
    adapter = MegaAdapter()
    mega = _FakeMega()
    adapter._m = mega

    await adapter.mkdir("root", "Docs")
    assert mega.get_files_calls == 2
    listed = await adapter.list_folder("root")
    again = await adapter.list_folder("root")

    assert [n.name for n in listed] == ["Docs"]
    assert [n.name for n in again] == ["Docs"]
    assert mega.get_files_calls == 2


@pytest.mark.asyncio
async def test_delete_folder_refreshes_and_list_omits_it():
    adapter = MegaAdapter()
    mega = _FakeMega()
    mega.files["docs1"] = {"a": {"n": "Docs"}, "t": 1, "p": "root"}
    adapter._m = mega

    await adapter.list_folder("root")
    calls_after_list = mega.get_files_calls
    await adapter.delete_folder("docs1")
    listed = await adapter.list_folder("root")

    assert listed == []
    assert mega.get_files_calls == calls_after_list + 1
    await adapter.list_folder("root")
    assert mega.get_files_calls == calls_after_list + 1


@pytest.mark.asyncio
async def test_get_node_reuses_cache():
    adapter = MegaAdapter()
    mega = _FakeMega()
    mega.files["n1"] = {"a": {"n": "x.bin"}, "t": 0, "p": "root", "s": 3}
    adapter._m = mega

    first = await adapter.get_node("n1")
    second = await adapter.get_node("n1")

    assert first.name == second.name == "x.bin"
    assert mega.get_files_calls == 1
