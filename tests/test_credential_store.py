import json
import os
from pathlib import Path

import pytest

from app.services.credential_store import CredentialStore


def test_set_get_delete_round_trip(tmp_path: Path):
    store = CredentialStore(tmp_path / "credentials.json")
    store.set("mega", {"username": "a@x", "password": "secret"})
    assert store.get("mega") == {"username": "a@x", "password": "secret"}
    assert store.get("pikpak") is None
    store.delete("mega")
    assert store.get("mega") is None
    data = json.loads((tmp_path / "credentials.json").read_text(encoding="utf-8"))
    assert "mega" not in data


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes only")
def test_posix_permissions_on_write(tmp_path: Path):
    path = tmp_path / "credentials.json"
    store = CredentialStore(path)
    store.set("mega", {"username": "a@x", "password": "secret"})
    assert oct(path.stat().st_mode)[-3:] == "600"
    assert oct(path.parent.stat().st_mode)[-3:] == "700"


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes only")
def test_posix_permissions_upgraded_on_init(tmp_path: Path):
    path = tmp_path / "credentials.json"
    path.write_text("{}", encoding="utf-8")
    os.chmod(path, 0o644)
    os.chmod(tmp_path, 0o755)
    CredentialStore(path)
    assert oct(path.stat().st_mode)[-3:] == "600"
    assert oct(tmp_path.stat().st_mode)[-3:] == "700"


def test_write_keeps_original_if_replace_fails(tmp_path: Path, monkeypatch):
    path = tmp_path / "credentials.json"
    store = CredentialStore(path)
    store.set("mega", {"username": "a@x", "password": "old"})
    original = path.read_text(encoding="utf-8")

    def boom(_src: str | os.PathLike, _dst: str | os.PathLike) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        store.set("pikpak", {"username": "b@x", "password": "new"})
    assert path.read_text(encoding="utf-8") == original
    assert json.loads(original)["mega"]["password"] == "old"
