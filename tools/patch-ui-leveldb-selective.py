#!/usr/bin/env python3
"""Create a UI_XML_RO LevelDB copy with explicitly selected key aliases.

The game sometimes requests EN records that are present only under KO in the
preserved client database.  Full-database rebuilding changes too much state
for native-client testing, so this helper copies the original directory and
adds only aliases explicitly named by the investigator.

Example:
    python tools/patch-ui-leveldb-selective.py \
      analysis/original/UI_XML_RO.db analysis/selective/UI_XML_RO.db \
      --alias KO/NEW/SR_MISSION/2_SR_UI_MS_ST/1_MS_ST_MAP=EN/NEW/SR_MISSION/2_SR_UI_MS_ST/1_MS_ST_MAP

The source directory is never modified.  The destination is created as a
preserved copy, and the new records are written without compaction so the
original SSTables remain available for comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path


def parse_alias(value: str) -> tuple[bytes, bytes]:
    source, separator, target = value.partition("=")
    if not separator or not source or not target:
        raise argparse.ArgumentTypeError(
            "aliases must use SOURCE_KEY=TARGET_KEY syntax"
        )
    return source.encode("utf-8"), target.encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="preserved LevelDB directory")
    parser.add_argument("destination", type=Path, help="new LevelDB directory")
    parser.add_argument(
        "--alias",
        action="append",
        type=parse_alias,
        required=True,
        help="explicit SOURCE_KEY=TARGET_KEY alias; repeat for multiple keys",
    )
    parser.add_argument(
        "--compression",
        choices=("snappy", "none"),
        default="none",
        help="compression for newly written tables (default: none; native 28010 rejects Snappy)",
    )
    args = parser.parse_args()

    try:
        import plyvel
    except ImportError:
        print(
            "Install plyvel-ci before running this tool: "
            "python -m pip install plyvel-ci",
            file=sys.stderr,
        )
        return 2

    source = args.source.resolve()
    destination = args.destination.resolve()
    if not source.is_dir():
        print(f"source is not a directory: {source}", file=sys.stderr)
        return 2
    if destination.exists():
        print(f"destination already exists: {destination}", file=sys.stderr)
        return 2

    shutil.copytree(source, destination)
    db = plyvel.DB(
        str(destination),
        create_if_missing=False,
        compression=None if args.compression == "none" else "snappy",
    )
    try:
        for source_key, target_key in args.alias:
            value = db.get(source_key)
            if value is None:
                raise RuntimeError(
                    f"source key is missing: {source_key.decode('utf-8', 'replace')}"
                )
            existing = db.get(target_key)
            if existing is not None and existing != value:
                raise RuntimeError(
                    "target exists with different bytes: "
                    f"{target_key.decode('utf-8', 'replace')}"
                )
            if existing is None:
                db.put(target_key, value)
                action = "aliased"
            else:
                action = "verified"
            print(
                f"{action} {target_key.decode('utf-8', 'replace')} "
                f"bytes={len(value)} sha256={sha256(value)}"
            )
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
