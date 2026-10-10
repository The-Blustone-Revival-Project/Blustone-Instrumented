#!/usr/bin/env python3
"""Collect every resource name referenced by a set of UI_XML_RO records.

The battle scene renders from XML fragments stored in `UI_XML_RO.db`.  Each
fragment names the sprites, videos, fonts and motion files it needs via
`res-name=` / `file=` attributes.  Those names are the resource half of the
"what does the battle scene need" question: a record can be present and still
render nothing if the sprite it names is not in the reconstructed package tree.

This helper walks the records whose locale-stripped name matches --group (or
--key), collects:

  res-name / file  -> image, video, font and motion resources
  text-ko / text-en -> the localized string tokens (informational)

and prints a de-duplicated, sorted resource list with the record that named it,
so the result can be checked against the reconstructed resource tree by hand.

Optionally it also checks each resource against a directory of file stems and
reports which are missing, via --tree-dir (repeatable).  A resource is
considered present if any file under the tree has a matching stem, which is a
lower bound: the real client resolves sprites through the CDN package manifest,
not the filesystem.

Usage:
    python tools/collect-ui-resource-refs.py \
        --db instrumentation/assets/instrumented-seed-complete-ui-delta-v2/UI_XML_RO.db \
        --group SR_INGAME --group SR_INGAME2 --group SR_BATTLE \
        --tree-dir analysis/reconstructed-resources
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

RES_NAME_RE = re.compile(r'\bres-name\s*=\s*"([^"]*)"')
FILE_RE = re.compile(r'\bfile\s*=\s*"([^"]*)"')
# <res-sprite>, <sprite>, <video>, <font>, <motion>
ELEMENT_RE = re.compile(
    r"<(res-sprite|sprite|video|font|motion)\b[^>]*?\bres-name\s*=\s*\"([^\"]*)\"",
    re.IGNORECASE,
)
TEXT_RE = re.compile(r'\btext-(?:ko|en|jp)\s*=\s*"([^"]*)"')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--group", action="append", default=[])
    parser.add_argument("--key", action="append", default=[])
    parser.add_argument("--tree-dir", type=Path, action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        import plyvel
    except ImportError:
        print("plyvel-ci is required: set PYTHONPATH to analysis/leveldb-tooling-ci",
              file=sys.stderr)
        return 2

    # resource -> set of records naming it, and set of element kinds
    named_by: dict[str, set[str]] = defaultdict(set)
    kinds: dict[str, set[str]] = defaultdict(set)

    db = plyvel.DB(str(args.db), create_if_missing=False)
    try:
        for key, value in db:
            text_key = key.decode("utf-8", "replace")
            _head, _, tail = text_key.partition("/")
            if args.key and text_key not in args.key and tail not in args.key:
                continue
            if args.group and not any(
                tail.upper().startswith(group.upper() + "/") for group in args.group
            ):
                continue
            if not args.key and not args.group:
                continue
            body = value.decode("utf-8", "replace")
            for match in ELEMENT_RE.finditer(body):
                kind, name = match.group(1).lower(), match.group(2).strip()
                if not name:
                    continue
                named_by[name].add(text_key)
                kinds[name].add(kind)
            for match in RES_NAME_RE.finditer(body):
                name = match.group(1).strip()
                if name:
                    named_by[name].add(text_key)
            for match in FILE_RE.finditer(body):
                name = match.group(1).strip()
                if name:
                    named_by[name].add(text_key)
                    kinds[name].add("file")
    finally:
        db.close()

    stems: dict[str, str] = {}
    if args.tree_dir:
        for tree in args.tree_dir:
            if not tree.is_dir():
                print(f"# tree-dir missing: {tree}", file=sys.stderr)
                continue
            for path in tree.rglob("*"):
                if path.is_file():
                    stems.setdefault(path.stem.upper(), str(path))
                    stems.setdefault(path.name.upper(), str(path))

    present = []
    absent = []
    for name in sorted(named_by, key=str.upper):
        hit = stems.get(name.upper()) or stems.get(name.upper().rsplit(".", 1)[0])
        (present if hit else absent).append((name, sorted(kinds[name]), hit))

    if args.json:
        import json
        print(json.dumps({
            "referenced": sorted(named_by, key=str.upper),
            "present": [row[0] for row in present],
            "absent": [row[0] for row in absent],
        }, indent=2))
    else:
        print(f"# records scanned produced {len(named_by)} distinct resource names")
        for name, kind, hit in present:
            print(f"PRESENT\t{name}\t{','.join(sorted(kind))}\t{hit}")
        print()
        for name, kind, _hit in absent:
            print(f"ABSENT\t{name}\t{','.join(sorted(kind))}")

    print(f"# present={len(present)} absent={len(absent)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())