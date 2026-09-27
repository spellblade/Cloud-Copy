# MEGA node attribute ``c``: sparse CRC32 + mtime (official SDK FileFingerprint).

from __future__ import annotations

import base64
import struct
import zlib
from pathlib import Path

_MAX_FULL = 8192
_CRC_LANES = 4
_CRC_BYTES = 16
_SPARSE_BLOCK = 64  # 4 * sizeof(crc)


def _b64url(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii").replace("+", "-").replace("/", "_").rstrip("=")


def _serialize64(value: int) -> bytes:
    # MEGA Serialize64: count byte, then little-endian value bytes.
    parts = bytearray([0])
    remaining = max(0, int(value))
    count = 0
    while remaining:
        count += 1
        parts.append(remaining & 0xFF)
        remaining >>= 8
    parts[0] = count
    return bytes(parts)


def _sparse_offset(size: int, lane: int, block: int, blocks: int) -> int:
    idx = lane * blocks + block
    numer = (size - _SPARSE_BLOCK) * idx
    denom = _CRC_LANES * blocks - 1
    off = numer // denom if denom else 0
    return min(off, size - _SPARSE_BLOCK)


def sparse_crc16(path: Path) -> bytes:
    """16-byte MEGA sparse CRC (four big-endian CRC32s, or raw bytes if tiny)."""
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size <= _CRC_BYTES:
            data = handle.read(size)
            return data + b"\0" * (_CRC_BYTES - len(data))
        if size <= _MAX_FULL:
            buf = handle.read(size)
            out = bytearray(_CRC_BYTES)
            for i in range(_CRC_LANES):
                begin = i * size // _CRC_LANES
                end = (i + 1) * size // _CRC_LANES
                crc = zlib.crc32(buf[begin:end]) & 0xFFFFFFFF
                struct.pack_into(">I", out, i * 4, crc)
            return bytes(out)
        blocks = _MAX_FULL // (_SPARSE_BLOCK * _CRC_LANES)
        out = bytearray(_CRC_BYTES)
        for i in range(_CRC_LANES):
            crc = 0
            for j in range(blocks):
                off = _sparse_offset(size, i, j, blocks)
                handle.seek(off)
                block = handle.read(_SPARSE_BLOCK)
                if len(block) < _SPARSE_BLOCK:
                    block += b"\0" * (_SPARSE_BLOCK - len(block))
                crc = zlib.crc32(block, crc)
            struct.pack_into(">I", out, i * 4, crc & 0xFFFFFFFF)
        return bytes(out)


def fingerprint_for_path(path: Path, mtime: int | None = None) -> str:
    """Base64url fingerprint for node attribute ``c`` (CRC + mtime)."""
    crc = sparse_crc16(path)
    if mtime is None:
        mtime = int(path.stat().st_mtime)
    return _b64url(crc + _serialize64(mtime))


def file_attribs(name: str, local_path: Path) -> dict[str, str]:
    # Name plus fingerprint so MEGA Desktop does not report "fingerprint missing".
    return {"n": name, "c": fingerprint_for_path(local_path)}
