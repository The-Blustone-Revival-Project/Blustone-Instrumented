from __future__ import annotations

import struct
import sys
from pathlib import Path


def varint(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, pos
        shift += 7


def block_entries(block: bytes):
    if len(block) < 4:
        return
    restart_count = struct.unpack_from("<I", block, len(block) - 4)[0]
    restart_start = len(block) - 4 - restart_count * 4
    pos = 0
    previous = b""
    while pos < restart_start:
        shared, pos = varint(block, pos)
        unshared, pos = varint(block, pos)
        value_length, pos = varint(block, pos)
        key_suffix = block[pos:pos + unshared]
        pos += unshared
        value = block[pos:pos + value_length]
        pos += value_length
        key = previous[:shared] + key_suffix
        previous = key
        yield key, value


def read_block(data: bytes, offset: int, size: int) -> bytes:
    raw = data[offset:offset + size]
    if len(raw) < size + 5:
        raw = data[offset:offset + size + 5]
    if len(raw) < 5:
        return b""
    compression_type = raw[size]
    payload = raw[:size]
    if compression_type == 0:
        return payload
    raise RuntimeError(f"unsupported LevelDB compression type {compression_type}")


def handle(data: bytes, pos: int) -> tuple[int, int, int]:
    offset, pos = varint(data, pos)
    size, pos = varint(data, pos)
    return offset, size, pos


def dump(path: Path) -> None:
    data = path.read_bytes()
    if len(data) < 48:
        return
    footer = data[-48:]
    meta_offset, meta_size, pos = handle(footer, 0)
    index_offset, index_size, _ = handle(footer, pos)
    index = read_block(data, index_offset, index_size)
    for index_key, index_value in block_entries(index):
        block_offset, block_size, _ = handle(index_value, 0)
        block = read_block(data, block_offset, block_size)
        for key, value in block_entries(block):
            user_key = key[:-8] if len(key) >= 8 else key
            printable_key = user_key.decode("utf-8", "replace")
            printable_value = value.decode("utf-8", "replace")
            if "--keys" in sys.argv:
                print(f"{path.name}\t{printable_key!r}\tbytes={len(value)}")
            elif "--focus" in sys.argv:
                if printable_key in {"type:CDN\\header\\stamp", "type:CDN\\header\\size", "type:CDN\\header\\cnt"} or printable_key.startswith("type:CDN\\header\\items\\E_NEW"):
                    print(f"{path.name}\t{printable_key!r}\tlen={len(value)}\thex={value.hex()}")
            elif any(term in printable_key.lower() or term in printable_value.lower() for term in ("cdn", "stamp", "res", "jet", "pkg", "pvc", "header")):
                print(f"{path.name}\t{printable_key!r}\t{printable_value!r}")


if __name__ == "__main__":
    for filename in sys.argv[1:]:
        if filename.startswith("--"):
            continue
        dump(Path(filename))
