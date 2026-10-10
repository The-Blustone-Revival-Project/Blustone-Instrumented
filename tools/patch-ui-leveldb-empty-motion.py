#!/usr/bin/env python3
"""Create an instrumented UI database with safe defaults for empty motions.

Some stage-popup XML records intentionally contain motion nodes that are
filled by native code at runtime. The recovered local fixture leaves those
nodes empty; the shipped client calls LoadAnim2 with an empty name and then
dereferences the missing resource. This diagnostic-only patch gives empty
motion nodes a known UI animation while preserving the source directory.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--key",
        action="append",
        dest="keys",
        help="XML key to patch; repeat for multiple records",
    )
    parser.add_argument("--animation", default="UI_BT_PRE_S")
    args = parser.parse_args()

    import plyvel

    source = args.source.resolve()
    destination = args.destination.resolve()
    if destination.exists():
        raise SystemExit(f"destination already exists: {destination}")
    shutil.copytree(source, destination)

    db = plyvel.DB(str(destination), create_if_missing=False, compression=None)
    try:
        animation = args.animation.encode("utf-8")

        def replace(match: re.Match[bytes]) -> bytes:
            tag = match.group(0)
            if b"file=" in tag:
                return tag
            return tag[:-1] + b' file="' + animation + b'">'

        keys = args.keys or ["EN/NEW/SR_MISSION/2_SR_UI_MS_ST/STAGE_POP"]
        for key_text in keys:
            key = key_text.encode("utf-8")
            value = db.get(key)
            if value is None:
                raise SystemExit(f"key is missing: {key_text}")
            updated = re.sub(rb"<comp-motion[^>]*>", replace, value)
            changed = value != updated
            if changed:
                db.put(key, updated)
            print(f"key={key_text} changed={changed} bytes={len(updated)}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
