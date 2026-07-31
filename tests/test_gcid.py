from pathlib import Path

from app.services.pikpak_client import calc_gcid


def test_calc_gcid_small(tmp_path: Path):
    p = tmp_path / "sample.bin"
    p.write_bytes(b"hello cloud copy")
    g = calc_gcid(p)
    assert isinstance(g, str)
    assert len(g) == 40
    # deterministic
    assert g == calc_gcid(p)


def test_calc_gcid_empty(tmp_path: Path):
    p = tmp_path / "empty.bin"
    p.write_bytes(b"")
    g = calc_gcid(p)
    assert len(g) == 40
