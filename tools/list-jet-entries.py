#!/usr/bin/env python3
"""List the sprite/resource names inside one or more Blustone `.jet` packages.

The battle scene's UI records in `UI_XML_RO.db` name sprites through
`res-name="..."` attributes, but the sprites themselves live inside CDN
resource packages (`.jet`).  This helper inflates a package with the project's
existing `tools/jet-viewer/jet_decoder.py` and prints the entry names it finds,
optionally filtered by a substring, so a UI record's `res-name` can be checked
against what a package actually contains.

Package formats seen in this project: `PKGI1` (zlib-wrapped) and `I2`
(`split_raw_i2_resources`).  Both are handled; unrecognised payloads are
reported rather than silently skipped.

Usage:
    python tools/list-jet-entries.py analysis/extracted/assets/UI_BATTLE.jet
    python tools/list-jet-entries.py --grep '^IG_' UI_INGAME.jet INGAME_ICON.jet
"""

from __future__ import annotations

import argparse
import re
import sys
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools" / "jet-viewer"))

import jet_decoder as jd  # noqa: E402


def walk(data: bytes, depth: int = 0, out: list[str] | None = None) -> list[str]:
    """Recursively collect entry names from a PKGI1 tree."""
    if out is None:
        out = []
    if depth > 6 or len(data) < 8:
        return out
    # PKGI1 header: 'PKGI' + version + 4-byte BE count
    if data[:4] == b"PKGI":
        try:
            count = int.from_bytes(data[8:12], "big")
        except Exception:
            return out
        pos = 12
        for _ in range(count):
            if pos + 2 > len(data):
                break
            name_len = int.from_bytes(data[pos:pos + 2], "big")
            pos += 2
            if name_len == 0:
                continue
            name = data[pos:pos + name_len].rstrip(b"\x00").decode("utf-8", "replace")
            pos += name_len
            if pos + 8 > len(data):
                break
            offset = int.from_bytes(data[pos:pos + 4], "big")
            size = int.from_bytes(data[pos + 4:pos + 8], "big")
            pos += 8
            out.append(f"{name}\t{size}")
            if size and offset and offset < len(data):
                blob = data[offset:offset + size]
                if blob[:4] in (b"PKGI", b"\x78\x9c", b"\x78\x01", b"\x78\xda"):
                    try:
                        walk(zlib.decompress(blob), depth + 1, out)
                    except zlib.error:
                        pass
        return out
    if data[:2] == b"I2":
        for name, blob in jd.split_raw_i2_resources(data):
            out.append(f"{name}\t{len(blob)}")
        return out
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path, nargs="+")
    parser.add_argument("--grep", default=None, help="regex the entry name must match")
    parser.add_argument("--quiet-count", action="store_true")
    args = parser.parse_args()

    pattern = re.compile(args.grep) if args.grep else None
    rc = 0

    for path in args.paths:
        raw = path.read_bytes()
        entries: list[str] = []
        entries = walk(raw)
        if not entries:
            # Fall back to the project decoder, which understands the
            # chunked I2 / zlib-JET container format used by the shipped packs.
            try:
                for _offset, payload, _chunks in jd.inflate_jet_resources(raw):
                    sub = walk(payload)
                    if sub:
                        entries.extend(sub)
                    else:
                        entries.append(f"<unparsed resource {len(payload)} bytes>\t{len(payload)}")
            except Exception as exc:  # noqa: BLE001
                print(f"{path.name}: cannot decode ({exc})", file=sys.stderr)
                rc = 1
                continue

        shown = 0
        for entry in entries:
            name = entry.split("\t", 1)[0]
            if pattern and not pattern.search(name):
                continue
            shown += 1
            if not args.quiet_count:
                print(f"{path.name}\t{entry}")
        print(f"# {path.name}: {len(entries)} entries, {shown} matched", file=sys.stderr)

    return rc


if __name__ == "__main__":
    raise SystemExit(main())