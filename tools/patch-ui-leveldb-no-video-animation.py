#!/usr/bin/env python3
"""Copy a UI_XML_RO LevelDB and remove one unsupported optional animation.

The recovered main-menu XML references UI_MA_L1 as an ``Animation`` node.
On the instrumented BlueStacks client that resource is resolved through the
video-animation path before the corresponding native global is initialized,
causing a SIGSEGV during the first lobby transition.  This diagnostic-only
transform removes that optional node while preserving the rest of each XML
record and never mutating the source database.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


ANIMATION = re.compile(
    rb"\s*<Animation\s+res-name=[\"']UI_MA_L1[\"'][^>]*/>"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="source UI_XML_RO LevelDB")
    parser.add_argument("destination", type=Path, help="new destination LevelDB")
    parser.add_argument(
        "--key",
        action="append",
        dest="keys",
        default=["EN/SR_MAIN/0_SR_MN_BG", "KO/SR_MAIN/0_SR_MN_BG"],
        help="XML key to patch; repeat for multiple records",
    )
    args = parser.parse_args()

    try:
        import plyvel
    except ImportError as error:
        raise SystemExit("plyvel-ci is required to patch the UI database") from error

    source = args.source.resolve()
    destination = args.destination.resolve()
    if not source.is_dir():
        raise SystemExit(f"source is not a directory: {source}")
    if destination.exists():
        raise SystemExit(f"destination already exists: {destination}")

    shutil.copytree(source, destination)
    db = plyvel.DB(str(destination), create_if_missing=False, compression=None)
    changed = 0
    keys: list[str] = []
    try:
        for key_text in args.keys:
            key = key_text.encode("utf-8")
            value = db.get(key)
            if value is None:
                raise SystemExit(f"key is missing: {key_text}")
            updated = ANIMATION.sub(b"", value)
            if updated == value:
                print(f"key={key_text} changed=false bytes={len(value)}")
                continue
            db.put(key, updated)
            changed += 1
            keys.append(key_text)
            print(f"key={key_text} changed=true bytes={len(updated)}")
    finally:
        db.close()

    print(f"changed={changed} keys={','.join(keys)} destination={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
