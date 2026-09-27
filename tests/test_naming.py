from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.mega_client import MegaAdapter
from app.services.naming import require_folder_name, safe_local_name
from app.services.pikpak_client import PikPakAdapter


def test_safe_local_name_strips_parents():
    assert safe_local_name("../../evil.txt") == "evil.txt"
    assert safe_local_name("a/b/c.txt") == "c.txt"
    assert safe_local_name(r"a\b\c.txt") == "c.txt"


def test_safe_local_name_keeps_unicode():
    assert safe_local_name("café.pdf") == "café.pdf"


@pytest.mark.parametrize("bad", ["", ".", ".."])
def test_safe_local_name_rejects_empty_and_dots(bad):
    with pytest.raises(ValueError, match="not safe"):
        safe_local_name(bad)


def test_require_folder_name_strips():
    assert require_folder_name("  Docs  ") == "Docs"


@pytest.mark.parametrize("bad", ["", "   ", "a/b", r"a\b"])
def test_require_folder_name_rejects(bad):
    with pytest.raises(ValueError):
        require_folder_name(bad)


@pytest.mark.asyncio
async def test_mega_download_stays_in_dest_dir(tmp_path, monkeypatch):
    adapter = MegaAdapter()
    adapter._m = object()
    monkeypatch.setattr(adapter, "_refresh_files_cache", AsyncMock())
    monkeypatch.setattr(
        adapter, "_get_node_pair", lambda _fid: ("id", {"a": {"n": "../../evil.txt"}})
    )

    def fake_dl(_mega, _node, dest_dir, file_name, on_progress=None):
        path = dest_dir / file_name
        path.write_bytes(b"x")
        return path

    monkeypatch.setattr(adapter, "_download_file_windows_safe", staticmethod(fake_dl))
    out = await adapter.download_to_path("id", tmp_path)
    assert out.parent.resolve() == tmp_path.resolve()
    assert out.name == "evil.txt"
    assert list(tmp_path.rglob("*")) == [out]


@pytest.mark.asyncio
async def test_pikpak_download_stays_in_dest_dir(tmp_path, monkeypatch):
    adapter = PikPakAdapter()
    client = MagicMock()
    client.get_download_url = AsyncMock(
        return_value={
            "name": "../../evil.txt",
            "size": 1,
            "web_content_link": "https://example.invalid/x",
        }
    )
    client.get_headers.return_value = {"User-Agent": "t"}
    adapter._client = client

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        async def aiter_bytes(self, _n: int):
            yield b"x"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a):
            return None

    class _Http:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a):
            return None

        def stream(self, *_a, **_k):
            return _Resp()

    monkeypatch.setattr(
        "app.services.pikpak_client.httpx.AsyncClient", lambda **_k: _Http()
    )
    out = await adapter.download_to_path("id", tmp_path)
    assert out.parent.resolve() == tmp_path.resolve()
    assert out.name == "evil.txt"
    assert out.read_bytes() == b"x"
