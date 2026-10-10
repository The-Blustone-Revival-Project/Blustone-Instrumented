#!/usr/bin/env python3
"""Enumerate and dump records from a raw LevelDB write-ahead log / WriteBatch.

Some shipped LevelDB databases survive in the recovered phone snapshot only as
an unrecovered `NNNNNN.log` plus a ~50-byte MANIFEST, so `plyvel` cannot open
them. This helper reads them directly.

A LevelDB log file is a sequence of 32 KiB blocks. Each physical record is

    <crc32c:4> <length:2> <type:1> <payload>

with `type` in {1=FULL, 2=FIRST, 3=MIDDLE, 4=LAST}. A logical write batch may
be split across several physical records; the FIRST record's payload begins with
the WriteBatch header

    <sequence:8> <count:4>

followed by `count` operations, each `<tag:1>` then a length-prefixed key and
(for `tag == 1`, kTypeValue) a length-prefixed value. `tag == 0` is kTypeDeletion
and carries only a key.

Both this helper and `tools/read-leveldb-log.py` exist because the framing and
the batch encoding are separate problems: this one understands the batch
encoding, which is what you need to recover the *keys*.

Usage:
    python tools/read-leveldb-log.py <dbdir>/000003.log --keys-only
    python tools/read-leveldb-log.py <dbdir> --grep SR_INGAME
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

BLOCK_SIZE = 32768
HEADER_SIZE = 7
REC_FULL, REC_FIRST, REC_MIDDLE, REC_LAST = 1, 2, 3, 4
OP_DELETE, OP_VALUE = 0, 1


def read_varint32(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while pos < len(data):
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7
        if shift > 28:
            break
    return result, pos


def physical_records(data: bytes):
    """Yield (type, payload) for each physical record, joining nothing."""
    pos = 0
    size = len(data)
    while pos + HEADER_SIZE <= size:
        in_block = pos % BLOCK_SIZE
        if BLOCK_SIZE - in_block < HEADER_SIZE:
            pos += BLOCK_SIZE - in_block
            continue
        _crc, length, kind = struct.unpack_from("<IHB", data, pos)
        if length == 0 and kind == 0:
            pos += BLOCK_SIZE - in_block
            continue
        if length > BLOCK_SIZE - HEADER_SIZE:
            pos += BLOCK_SIZE - in_block
            continue
        pos += HEADER_SIZE
        yield kind, data[pos:pos + length]
        pos += length


def write_batches(data: bytes):
    """Join FIRST/MIDDLE/LAST fragments and yield each WriteBatch payload."""
    buffer = bytearray()
    joining = False
    for kind, payload in physical_records(data):
        if kind == REC_FULL:
            yield bytes(payload)
            joining = False
        elif kind == REC_FIRST:
            buffer = bytearray(payload)
            joining = True
        elif kind == REC_MIDDLE and joining:
            buffer += payload
        elif kind == REC_LAST and joining:
            buffer += payload
            yield bytes(buffer)
            buffer = bytearray()
            joining = False


def batch_operations(batch: bytes):
    """Yield (tag, key, value) from one WriteBatch payload."""
    if len(batch) < 12:
        return
    count = struct.unpack_from("<I", batch, 8)[0]
    pos = 12
    for _ in range(count):
        if pos >= len(batch):
            return
        tag = batch[pos]
        pos += 1
        try:
            klen, pos = read_varint32(batch, pos)
            key = batch[pos:pos + klen]
            pos += klen
            if tag == OP_VALUE:
                vlen, pos = read_varint32(batch, pos)
                value = batch[pos:pos + vlen]
                pos += vlen
            else:
                value = b""
        except Exception:  # noqa: BLE001
            return
        yield tag, key, value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path,
                        help="a .log file, or a directory containing one")
    parser.add_argument("--grep", default=None,
                        help="only show records whose key or value matches")
    parser.add_argument("--keys-only", action="store_true")
    parser.add_argument("--max-bytes", type=int, default=1500)
    args = parser.parse_args()

    path = args.path
    if path.is_dir():
        logs = sorted(path.glob("*.log"))
        if not logs:
            print(f"no .log file in {path}", file=sys.stderr)
            return 2
        path = logs[0]

    data = path.read_bytes()
    needle = args.grep.encode() if args.grep else None

    total = 0
    shown = 0
    seen: set[str] = set()
    for batch in write_batches(data):
        for tag, key, value in batch_operations(batch):
            total += 1
            text = key.decode("utf-8", "replace")
            if needle and needle not in key and needle not in value:
                continue
            if text in seen and args.keys_only:
                continue
            seen.add(text)
            shown += 1
            if args.keys_only:
                print(text)
                continue
            print(f"=== {text}  tag={tag} bytes={len(value)} ===")
            body = value.decode("utf-8", "replace")
            print(body[: args.max_bytes])
            if len(body) > args.max_bytes:
                print(f"... [{len(body) - args.max_bytes} more chars]")

    print(f"# {total} operations, {shown} matched, from {path.name}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())