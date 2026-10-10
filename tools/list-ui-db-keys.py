#!/usr/bin/env python3
"""List every key in a UI_XML_RO LevelDB directory, one per line.

Read-only helper used by the battle-scene resource mapping work.  Unlike
tools/inspect-leveldb.py (which only handles uncompressed .ldb blocks and
skips values) this opens the database properly, so it also works on the
snappy-compressed delta tables produced by tools/patch-ui-leveldb-selective.py.

Example:
    python tools/list-ui-db-keys.py analysis/original/UI_XML_RO.db
    python tools/list-ui-db-keys.py analysis/original/UI_XML_RO.db --prefix EN/
    python tools/list-ui-db-keys.py analysis/original/UI_XML_RO.db --match BATTLE

Nothing is ever written; the LOCK file is bypassed by opening read-only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dbdir", type=Path, help="UI_XML_RO.db directory")
    parser.add_argument("--prefix", default=None, help="only keys with this prefix")
    parser.add_argument("--match", default=None, help="only keys containing this substring")
    parser.add_argument("--locs", action="store_true", help="also print value byte length")
    args = parser.parse_args()

    try:
        import plyvel
    except ImportError:
        print(
            "plyvel-ci is required: "
            "set PYTHONPATH to analysis/leveldb-tooling-ci",
            file=sys.stderr,
        )
        return 2

    dbdir = args.dbdir.resolve()
    if not dbdir.is_dir():
        print(f"not a directory: {dbdir}", file=sys.stderr)
        return 2

    needle = args.match.encode() if args.match else None
    count = 0
    db = plyvel.DB(str(dbdir), create_if_missing=False)
    try:
        for key, value in db:
            if args.prefix and not key.startswith(args.prefix.encode()):
                continue
            if needle and needle not in key:
                continue
            count += 1
            line = key.decode("utf-8", "replace")
            if args.locs:
                print(f"{line}\tbytes={len(value)}")
            else:
                print(line)
    finally:
        db.close()

    print(f"# {count} keys", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())