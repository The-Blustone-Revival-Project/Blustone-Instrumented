"""Resolve the battle scene's UI record dependency closure.

Starting from the battle record groups (`SR_BATTLE/`, `SR_INGAME/`,
`SR_INGAME2/`, `BATTLE/`), this walks the `EN/<record>` records in the delta
seed and finds (a) other `UI_XML_RO` records they reference by name and
(b) other UI databases they reference by key, so the seed covers the whole
scene and not just its top-level records.

It prints the records that are still missing an `EN` alias, which is exactly the
set the seed builder must add.

Usage:
    python tools/resolve-ui-record-deps.py <dbdir> [--groups SR_BATTLE SR_INGAME ...]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# A `UI_XML_RO` record name looks like GROUP/RECORD or GROUP/SUB/RECORD, where
# each segment is an upper-snake identifier. Sprite res-names overlap this shape
# heavily (UI_IG_CH_BG, IG_GAGE), so a candidate is only counted as a *record*
# reference when the same token set overlaps the known record namespace.
RECORD_TOKEN = re.compile(r"\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b")
# Text keys in the sibling UI databases use a pipe-delimited id|slot|locale form.
TEXT_KEY = re.compile(r"\b\d+\|[A-Z0-9_]+\|(?:EN|KO|JA|SC|TC)\b")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dbdir", type=Path)
    parser.add_argument("--group", action="append", default=[
        "SR_BATTLE", "SR_INGAME", "SR_INGAME2", "BATTLE",
    ])
    args = parser.parse_args()

    try:
        import plyvel
    except ImportError:
        print("plyvel-ci is required: set PYTHONPATH to analysis/leveldb-tooling-ci",
              file=sys.stderr)
        return 2

    db = plyvel.DB(str(args.dbdir), create_if_missing=False)
    try:
        # Every locale-stripped record name that exists anywhere in the database.
        known: set[str] = set()
        have_en: set[str] = set()
        records: dict[str, str] = {}
        for key, value in db:
            text = key.decode("utf-8", "replace")
            head, _, tail = text.partition("/")
            if not tail:
                continue
            known.add(tail)
            if head == "EN":
                have_en.add(tail)
                records[tail] = value.decode("utf-8", "replace")

        groups = [g.upper() for g in args.group]
        roots = {name for name in known
                 if any(name.upper().startswith(g + "/") for g in groups)}
        en_roots = sorted(name for name in roots if name in have_en)
        print(f"# {len(roots)} {args.group} records exist; "
              f"{len(en_roots)} have an EN alias")

        # Union of referenced names across the EN roots.
        referenced: dict[str, set[str]] = {}
        texts: set[str] = set()
        for name in en_roots:
            body = records[name]
            for token in RECORD_TOKEN.findall(body):
                referenced.setdefault(token, set()).add(name)
            texts.update(TEXT_KEY.findall(body))

        # Which of those are actually UI record names in the database?
        record_refs = {tok: srcs for tok, srcs in referenced.items()
                       if tok in known}
        missing = sorted(tok for tok in record_refs if tok not in have_en)

        print(f"# {len(record_refs)} referenced names are UI records in this DB")
        print(f"# {len(texts)} referenced keys are sibling-UI-DB text keys")
        print()
        print("## records referenced by the battle scene that still have no EN alias")
        for tok in missing:
            srcs = sorted(record_refs[tok])
            print(f"  {tok:44} <- {', '.join(srcs[:4])}"
                  f"{' ...' if len(srcs) > 4 else ''}")
        print(f"# {len(missing)} missing EN aliases")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())