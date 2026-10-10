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


def entries(block: bytes):
    restart_count = struct.unpack_from("<I", block, len(block) - 4)[0]
    restart_start = len(block) - 4 - restart_count * 4
    pos = 0
    previous = b""
    while pos < restart_start:
        shared, pos = varint(block, pos)
        unshared, pos = varint(block, pos)
        value_length, pos = varint(block, pos)
        suffix = block[pos:pos + unshared]
        pos += unshared
        value = block[pos:pos + value_length]
        pos += value_length
        key = previous[:shared] + suffix
        previous = key
        yield key, value


def handle(data: bytes, pos: int) -> tuple[int, int, int]:
    offset, pos = varint(data, pos)
    size, pos = varint(data, pos)
    return offset, size, pos


def block(data: bytes, offset: int, size: int) -> bytes:
    payload = data[offset:offset + size]
    compression = data[offset + size]
    if compression != 0:
        raise RuntimeError(f"unsupported compression {compression}")
    return payload


def dump(path: Path) -> None:
    data = path.read_bytes()
    footer = data[-48:]
    _, _, pos = handle(footer, 0)
    index_offset, index_size, _ = handle(footer, pos)
    print(f"FILE {path} index=0x{index_offset:x}/{index_size}")
    index = block(data, index_offset, index_size)
    for index_key, index_value in entries(index):
        data_offset, data_size, _ = handle(index_value, 0)
        print(f"  INDEX key={index_key!r} block=0x{data_offset:x}/{data_size}")
        for key, value in entries(block(data, data_offset, data_size)):
            print(f"    key={key!r} value_len={len(value)} value_hex={value.hex()}")


for filename in sys.argv[1:]:
    dump(Path(filename))
