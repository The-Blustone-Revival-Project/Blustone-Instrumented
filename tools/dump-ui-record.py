#!/usr/bin/env python3
"""Dump one UI_XML_RO record's bytes, and optionally the image/resource tokens
referenced inside it.

The battle scene's UI records are XML fragments produced by the game's UI
tooling.  Those fragments name image resources (buttons, frames, skill icons),
and those names are the second half of the battle scene's resource
requirements: even with every `EN/...` record present, the scene will still
render nothing if the named image is not in the reconstructed resource tree.

This helper therefore reports, per record:
  * the raw value with non-printable bytes escaped
  * every `.ext` token found in the value (candidate resource names)
  * every `[Upper_Snake_Group]` style token found (candidate nested record keys)

Usage:
    python tools/dump-ui-record.py --db <dir> --key EN/SR_INGAME2/MODULE_UI
    python tools/dump-ui-record.py --db <dir> --group SR_INGAME --resources-only
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TOKEN_RE = re.compile(r"[A-Za-z0-9_\-./]+\.[A-Za-z0-9]{2,5}")
GROUP_RE = re.compile(r"\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--key", action="append", default=[])
    parser.add_argument("--group", action="append", default=[],
                        help="select every key whose tail starts with this")
    parser.add_argument("--resources-only", action="store_true",
                        help="print only the referenced-token summary")
    parser.add_argument("--max-bytes", type=int, default=2000)
    args = parser.parse_args()

    try:
        import plyvel
    except ImportError:
        print("plyvel-ci is required: set PYTHONPATH to analysis/leveldb-tooling-ci",
              file=sys.stderr)
        return 2

    db = plyvel.DB(str(args.db), create_if_missing=False)
    try:
        for key, value in db:
            text = key.decode("utf-8", "replace")
            _head, _, tail = text.partition("/")
            if args.key and text not in args.key and tail not in args.key:
                continue
            if args.group and not any(
                tail.upper().startswith(group.upper() + "/") for group in args.group
            ):
                continue
            if not args.key and not args.group:
                continue

            printable = value.decode("utf-8", "replace")
            tokens = sorted(set(TOKEN_RE.findall(printable)))
            groups = sorted(set(GROUP_RE.findall(printable)) - set(tokens))

            if not args.resources_only:
                print(f"=== {text}  bytes={len(value)} ===")
                shown = printable[: args.max_bytes]
                print(shown)
                if len(printable) > args.max_bytes:
                    print(f"... [{len(printable) - args.max_bytes} more chars]")
            print(f"  resource-tokens({len(tokens)}): {' '.join(tokens)}")
            print(f"  record-tokens({len(groups)}): {' '.join(groups)}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())