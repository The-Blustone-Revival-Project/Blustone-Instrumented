#!/usr/bin/env python3
"""Add explicitly recovered UI records to a preserved native LevelDB tree.

The destination keeps the source tree's original SSTables and manifest. Only
the requested keys are copied from a separate recovered database, so a native
client A/B run can distinguish a missing record from a database-packaging
problem. Neither input tree is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path, help="native-compatible base LevelDB tree")
    parser.add_argument("source", type=Path, help="recovered source LevelDB tree")
    parser.add_argument("destination", type=Path, help="new merged LevelDB tree")
    parser.add_argument("--key", action="append", required=True, help="exact UTF-8 key to copy; repeat")
    args = parser.parse_args()

    import plyvel

    base = args.base.resolve()
    source = args.source.resolve()
    destination = args.destination.resolve()
    if destination.exists():
        raise SystemExit(f"destination already exists: {destination}")
    shutil.copytree(base, destination)

    source_db = plyvel.DB(str(source), create_if_missing=False)
    # Native28010 ReadBlock rejects type1 (Snappy) unconditionally.
    destination_db = plyvel.DB(str(destination), create_if_missing=False, compression=None)
    copied = 0
    try:
        for key_text in args.key:
            key = key_text.encode("utf-8")
            value = source_db.get(key)
            if value is None:
                raise SystemExit(f"source key is missing: {key_text}")
            existing = destination_db.get(key)
            if existing is not None:
                if existing != value:
                    raise SystemExit(f"destination key differs: {key_text}")
                print(f"verified {key_text} bytes={len(value)} sha256={digest(value)}")
                continue
            destination_db.put(key, value)
            copied += 1
            print(f"copied {key_text} bytes={len(value)} sha256={digest(value)}")
    finally:
        source_db.close()
        destination_db.close()
    print(f"copied={copied} destination={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
