#!/usr/bin/env python3
"""Merge a recovered LevelDB key prefix into an instrumented UI database."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path, help="base destination tree to copy")
    parser.add_argument("source", type=Path, help="recovered LevelDB tree")
    parser.add_argument("destination", type=Path, help="new merged LevelDB tree")
    parser.add_argument("--prefix", default="EN/NEW/SR_MISSION")
    parser.add_argument("--animation", default="UI_BT_PRE_S")
    args = parser.parse_args()

    import plyvel

    base = args.base.resolve()
    source = args.source.resolve()
    destination = args.destination.resolve()
    if destination.exists():
        raise SystemExit(f"destination already exists: {destination}")
    shutil.copytree(base, destination)

    source_db = plyvel.DB(str(source), create_if_missing=False)
    destination_db = plyvel.DB(str(destination), create_if_missing=False, compression=None)
    animation = args.animation.encode("utf-8")
    prefix = args.prefix.encode("utf-8")

    def add_default_motion(match: re.Match[bytes]) -> bytes:
        tag = match.group(0)
        if b"file=" in tag:
            return tag
        return tag[:-1] + b' file="' + animation + b'">'

    merged = 0
    try:
        for key, value in source_db:
            if not key.startswith(prefix):
                continue
            patched = re.sub(rb"<comp-motion[^>]*>", add_default_motion, value)
            destination_db.put(key, patched)
            merged += 1
    finally:
        source_db.close()
        destination_db.close()
    print(f"merged={merged} prefix={args.prefix} destination={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
