"""Enumerate `EN/<record>` keys stored in a raw LevelDB write-ahead log.

Some shipped LevelDB databases survive in the recovered phone snapshot only as
an unrecovered write-ahead log (`NNNNNN.log`) plus a tiny MANIFEST, so plyvel
cannot open them. This helper walks the log's logical records, decodes the
LevelDB length-prefixed key, and prints the ones matching a pattern. That is how
the original, unpatched `UI_XML.db` record set was recovered and compared with
the patched `UI_XML_RO.db` used at runtime.

Unlike `tools/read-leveldb-log.py` this does not require the record framing to
be intact; it falls back to scanning for length-prefixed printable keys when a
log has been truncated, which is the common case for a snapshot.

Usage:
    python tools/scan-leveldb-log-keys.py <dbdir> [--prefix EN/] [--locs]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HEADER_SIZE = 7
BLOCK_SIZE = 32768
FULL, FIRST, MIDDLE, LAST = 1, 2, 3, 4


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
    return result, pos


def framed_records(data: bytes):
    import struct
    pos = 0
    pending_key = None
    pending_value = bytearray()
    pending = False
    while pos + HEADER_SIZE <= len(data):
        in_block = pos % BLOCK_SIZE
        if BLOCK_SIZE - in_block < HEADER_SIZE:
            pos += BLOCK_SIZE - in_block
            continue
        try:
            _cs, length, kind = struct.unpack_from("<IHB", data, pos)
        except struct.error:
            break
        if length == 0 and kind == 0:
            pos += BLOCK_SIZE - in_block
            continue
        pos += HEADER_SIZE
        payload = data[pos:pos + length]
        pos += length
        if kind == FULL:
            try:
                klen, p = read_varint32(payload, 0)
                yield payload[p:p + klen], payload[p + klen:]
            except Exception:  # noqa: BLE001
                pass
            pending = False
        elif kind == FIRST:
            try:
                klen, p = read_varint32(payload, 0)
                pending_key = payload[p:p + klen]
                pending_value = bytearray(payload[p + klen:])
                pending = True
            except Exception:  # noqa: BLE001
                pending = False
        elif kind == MIDDLE and pending:
            pending_value += payload
        elif kind == LAST and pending:
            pending_value += payload
            yield pending_key, bytes(pending_value)
            pending = False


def printable_key(candidate: bytes) -> str | None:
    try:
        text = candidate.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not text or any(ord(ch) < 0x20 or ord(ch) > 0x7E for ch in text):
        return None
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dbdir", type=Path)
    parser.add_argument("--prefix", default=None)
    parser.add_argument("--locs", action="store_true")
    args = parser.parse_args()

    seen: dict[str, int] = {}
    for logfile in sorted(args.dbdir.glob("*.log")):
        data = logfile.read_bytes()
        for key, value in framed_records(data):
            text = printable_key(key)
            if text and (args.prefix is None or text.startswith(args.prefix)):
                seen[text] = len(value)
        if not seen:
            # Fall back: the snapshot's log may be truncated, so scan for
            # length-prefixed printable keys directly.
            pos = 0
            limit = len(data)
            while pos + 2 < limit:
                klen = data[pos]
                pos += 1
                if klen < 3 or pos + klen > limit:
                    continue
                text = printable_key(data[pos:pos + klen])
                pos += klen
                if text and (args.prefix is None or text.startswith(args.prefix)):
                    seen[text] = 0

    for text in sorted(seen):
        if args.locs:
            print(f"{text}\tbytes={seen[text]}")
        else:
            print(text)
    print(f"# {len(seen)} keys", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())