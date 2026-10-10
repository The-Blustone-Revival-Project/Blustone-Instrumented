#!/usr/bin/env python3
"""Report native string literals that look like UI record paths but have no
record in a UI_XML_RO LevelDB database under any locale prefix.

This is the "what is missing outright" direction of
tools/map-ui-records-to-strings.py: that tool walks DB records and asks whether
the native library names them, this tool walks the native string table and asks
whether the database has them.  The difference is exactly the set of records the
client could ask for and could never be given.

A literal is treated as a candidate UI record path when it contains at least one
'/' , has no whitespace, no '://', no '=' and does not look like a URL, an API
route or a file path with a known extension.  Every survivor is printed so the
result can be reviewed rather than trusted.

Usage:
    python tools/find-missing-ui-records.py \
        --db recovered-assets/phone-2026-09-18/private/files/local/UI_XML_RO.db \
        --strings analysis/native-all-strings.tsv --grep 'BATTLE|INGAME'
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SKIP_EXT = (
    ".json", ".png", ".jpg", ".xml", ".txt", ".mp4", ".so", ".db", ".ini",
    ".cfg", ".csv", ".dat", ".ttf", ".otf", ".plist", ".wav", ".ogg", ".ttc",
)
RESERVED = ("http", "https", "ftp")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--strings", type=Path, required=True)
    parser.add_argument("--grep", default=None,
                        help="regex the candidate literal must match")
    parser.add_argument("--extra-db", type=Path, action="append", default=[],
                        help="also treat records from this DB as present")
    args = parser.parse_args()

    try:
        import plyvel
    except ImportError:
        print("plyvel-ci is required: set PYTHONPATH to analysis/leveldb-tooling-ci",
              file=sys.stderr)
        return 2

    present: set[str] = set()
    for dbdir in [args.db, *args.extra_db]:
        db = plyvel.DB(str(dbdir), create_if_missing=False)
        try:
            for key, _value in db:
                text = key.decode("utf-8", "replace")
                _head, _, tail = text.partition("/")
                if tail:
                    present.add(tail)
        finally:
            db.close()

    pattern = re.compile(args.grep) if args.grep else None

    missing: list[tuple[str, str]] = []
    with args.strings.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            address, _, text = line.rstrip("\n").partition("\t")
            if not text or "/" not in text:
                continue
            if text in present:
                continue
            if any(ch.isspace() for ch in text):
                continue
            if text.lower().startswith(RESERVED) or "://" in text or "=" in text:
                continue
            if text.lower().endswith(SKIP_EXT):
                continue
            if text.startswith(("/", "..", "./")):
                continue
            if any(ord(ch) < 0x20 or ord(ch) > 0x7E for ch in text):
                continue
            if pattern and not pattern.search(text):
                continue
            missing.append((address, text))

    for address, text in missing:
        print(f"{address}\t{text}")
    print(f"# {len(missing)} candidate literals with no DB record", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())