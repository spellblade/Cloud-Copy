from pathlib import Path

from app.services.mega_fingerprint import file_attribs, fingerprint_for_path, sparse_crc16


def test_tiny_file_crc_is_padded_content(tmp_path: Path):
    path = tmp_path / "tiny.bin"
    path.write_bytes(b"ab")
    crc = sparse_crc16(path)
    assert crc[:2] == b"ab"
    assert crc[2:] == b"\0" * 14


def test_empty_file_crc_is_zeros(tmp_path: Path):
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")
    assert sparse_crc16(path) == b"\0" * 16


def test_fingerprint_includes_mtime_and_name(tmp_path: Path):
    path = tmp_path / "a.txt"
    path.write_bytes(b"hello")
    fp = fingerprint_for_path(path, mtime=1_700_000_000)
    assert fp
    assert "+" not in fp and "/" not in fp
    attribs = file_attribs("a.txt", path)
    assert attribs["n"] == "a.txt"
    assert "c" in attribs
    assert attribs["c"] == fingerprint_for_path(path)


def test_different_content_different_crc(tmp_path: Path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"x" * 100)
    b.write_bytes(b"y" * 100)
    assert sparse_crc16(a) != sparse_crc16(b)
