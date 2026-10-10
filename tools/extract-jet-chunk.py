#!/usr/bin/env python3
"""Extract one logical resource out of a BLUSTONE ``.jet`` package.

Why this exists
---------------
``tools/jet-viewer/jet_decoder.py`` is a *display* decoder: it recognises media
payloads and renders layers for a browser.  It is not a byte-faithful extractor,
and during the 2026-10-03 ``environments.csv`` investigation it was found to
emit identical output for several ``PK_*`` packages, so it cannot be trusted for
enumeration or extraction.  This tool is deliberately minimal and *verifiable*.

Container layout (recovered from the base APK assets, e.g. ``LEVELING.jet``)
------------------------------------------------------------------------------
A ``.jet`` is a flat concatenation of chunks.  Each chunk is::

    offset  size  field
    0       4     u32  uncompressed size of the inflated record
    4       4     u32  uncompressed size again (duplicated)
    8       4     u32  compressed size of the zlib stream that follows
    12      4     u32  unknown - NOT a plain CRC-32 (see note below)
    16      2     u16  unknown
    18      2     char[2]  record tag, usually 'RW' / 'RWM' / 'I2'
    20      4     u32  for 'RW': 0x00000052 ('R') ; for 'I2': the raw length
    24      ...   payload

For ``RW``/``RWM`` chunks the payload at +24 is a zlib stream and the inflated
result is the record body, which is itself ``"RW"``/``"RWM"`` + u32 length +
content (so the real content starts at +6).  For ``I2`` chunks the payload is
stored uncompressed and its length is the u32 at +20.

Integrity note (measured, 2026-10-03)
-------------------------------------
The u32 at chunk offset +12 does **not** equal crc32(inflated), crc32(compressed),
crc32(body), adler32(inflated) or crc32c(inflated) for any chunk of
``LEVELING.jet``.  It is therefore recorded as unknown and is *not* used as a
check.  Verification instead uses ``--expect-sha256`` plus the chunk's own
uncompressed-size field, both of which do match.

The tool never writes to the source ``.jet``.

Usage
-----
    python tools/extract-jet-chunk.py --list analysis/extracted/assets/LEVELING.jet
    python tools/extract-jet-chunk.py --index 5 --expect-sha256 <hex> \\
        --out analysis/recovered-data/environments.csv \\
        analysis/extracted/assets/LEVELING.jet
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import sys
import zlib
from pathlib import Path

HEADER_SIZE = 24
ZLIB_HEADERS = (b"\x78\x01", b"\x78\x5e", b"\x78\x9c", b"\x78\xda")
MAX_INFLATED = 512 * 1024 * 1024


def walk(data: bytes):
    """Yield (index, file_offset, header_tuple, record_bytes, tag_bytes)."""

    base = 0
    index = 0
    while len(data) - base >= HEADER_SIZE + 2:
        chunk = data[base:]
        head = struct.unpack_from("<IIIII", chunk, 0)
        tag = chunk[18:20]
        if chunk[24:26] in ZLIB_HEADERS:
            engine = zlib.decompressobj()
            try:
                record = engine.decompress(chunk[HEADER_SIZE:], MAX_INFLATED)
                record += engine.flush()
            except zlib.error as exc:
                raise SystemExit(f"chunk {index} @ {base:#x}: zlib error: {exc}")
            consumed = len(chunk) - len(engine.unused_data)
            if consumed <= 0:
                return
            yield index, base, head, record, tag
            base += consumed
        elif chunk[24:26] == b"I2":
            size = struct.unpack_from("<I", chunk, 20)[0]
            if size <= 0 or HEADER_SIZE + size > len(chunk):
                return
            yield index, base, head, chunk[HEADER_SIZE:HEADER_SIZE + size], tag
            base += HEADER_SIZE + size
        else:
            return
        index += 1


def body_of(record: bytes) -> bytes:
    """Strip the inner 'RW'+length envelope when present."""

    return record[6:] if record[:2] in (b"RW", b"RWM") else record


def ascii_preview(record: bytes, limit: int = 110) -> str:
    body = body_of(record)[:limit]
    text = body.decode("utf-8", "replace").replace("\r", "\\r").replace("\n", "\\n")
    return text.encode("ascii", "backslashreplace").decode("ascii")


def describe(index: int, offset: int, head, record: bytes, tag: bytes) -> str:
    size, _dup, comp, unk32, u16 = head
    ok = "size-OK" if size == len(record) else f"size-MISMATCH({len(record)})"
    return (
        f"[{index:3d}] @{offset:#08x} tag={tag.decode('latin1')!r} "
        f"usize={size} csize={comp} unk32={unk32:#010x} u16={u16:#06x} {ok} "
        f"sha256={hashlib.sha256(body_of(record)).hexdigest()[:16]} "
        f"body={ascii_preview(record)!r}"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--list", action="store_true", help="list every chunk and exit")
    parser.add_argument("--index", type=int, help="chunk index to extract")
    parser.add_argument("--out", type=Path, help="output file (default: stdout)")
    parser.add_argument("--expect-sha256", help="fail unless the body hashes to this")
    args = parser.parse_args(argv)

    data = args.path.read_bytes()
    if args.list or args.index is None:
        for row in walk(data):
            print(describe(*row))
        return 0

    for row in walk(data):
        if row[0] != args.index:
            continue
        index, offset, head, record, _tag = row
        body = body_of(record)
        digest = hashlib.sha256(body).hexdigest()
        if head[0] != len(record):
            raise SystemExit(
                f"chunk {index}: header usize {head[0]} != inflated {len(record)}"
            )
        if args.expect_sha256 and digest.lower() != args.expect_sha256.lower():
            raise SystemExit(
                f"chunk {index}: sha256 {digest} != expected {args.expect_sha256}"
            )
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(body)
            print(
                f"wrote {args.out}: chunk {index} @ {offset:#x}, {len(body)} bytes, "
                f"sha256={digest}"
            )
        else:
            sys.stdout.buffer.write(body)
        return 0
    raise SystemExit(f"chunk {args.index} not found in {args.path}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))