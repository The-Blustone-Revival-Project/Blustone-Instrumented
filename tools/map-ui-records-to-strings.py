#!/usr/bin/env python3
"""Cross-reference UI_XML_RO record names against the native string table.

The preserved `UI_XML_RO.db` ships essentially every UI record under the `KO`
locale prefix, while the client resolves UI records by the language code it
selected (`EN/...`).  This helper answers three questions in one pass:

  * which records does the native library actually name as a string literal
    (i.e. records the client can be asked to load)?
  * of those, which have an `EN/...` record in the database?
  * which have a `KO/...` counterpart that could be aliased to EN?

Record names are matched on the *suffix after the locale prefix*, because the
native library stores `SR_BATTLE/3_UI_BT_DF`-style relative names and prefixes
the language at resolution time.  `DEFINE_COLOR` is reported separately
because it is unsafe to alias across locales (see AGENTS.md section 7).

Usage:
    python tools/map-ui-records-to-strings.py \
        --db recovered-assets/phone-2026-09-18/private/files/local/UI_XML_RO.db \
        --strings analysis/native-all-strings.tsv \
        --group BATTLE
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def load_db_keys(dbdir: Path) -> dict[str, list[str]]:
    try:
        import plyvel
    except ImportError:
        print(
            "plyvel-ci is required: set PYTHONPATH to analysis/leveldb-tooling-ci",
            file=sys.stderr,
        )
        raise SystemExit(2)

    keys: dict[str, list[str]] = {}
    db = plyvel.DB(str(dbdir), create_if_missing=False)
    try:
        for key, _value in db:
            text = key.decode("utf-8", "replace")
            head, _, tail = text.partition("/")
            keys.setdefault(head, []).append(tail)
    finally:
        db.close()
    return keys


def load_strings(path: Path) -> dict[str, list[str]]:
    """address -> string, but indexed for reverse lookup by exact string."""
    out: dict[str, list[str]] = {}
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            address, _, text = line.rstrip("\n").partition("\t")
            if not text:
                continue
            out.setdefault(text, []).append(address)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--strings", type=Path, required=True)
    parser.add_argument("--db2", type=Path, default=None,
                        help="optional second DB (e.g. the delta seed) to test EN coverage")
    parser.add_argument("--group", action="append", default=[],
                        help="only consider records whose tail starts with this group")
    args = parser.parse_args()

    db = load_db_keys(args.db)
    db2 = load_db_keys(args.db2) if args.db2 else None
    strings = load_strings(args.strings)

    locales = sorted(db)
    print(f"# locales in {args.db}: {locales}")
    if db2:
        print(f"# locales in {args.db2}: {sorted(db2)}")

    # Union of every record tail seen under any locale.
    tails: dict[str, list[str]] = {}
    for locale, entries in db.items():
        if locale in {"SC", "TC", "JA", "KO", "EN"} or "/" not in locale:
            for tail in entries:
                tails.setdefault(tail, []).append(locale)
    for locale, entries in (db2 or {}).items():
        for tail in entries:
            tails.setdefault(tail, []).append(locale)

    def of_interest(tail: str) -> bool:
        if not args.group:
            return True
        return any(tail.upper().startswith(group.upper() + "/") for group in args.group)

    rows = []
    for tail in sorted(tails):
        if not of_interest(tail):
            continue
        locales_present = sorted(set(tails[tail]))
        addresses = strings.get(tail)
        rows.append((tail, locales_present, addresses[0] if addresses else ""))

    width = max((len(row[0]) for row in rows), default=10)
    print(f"{'record'.ljust(width)}  locales-in-db  native-string-address")
    for tail, locales_present, address in rows:
        flag = "" if address else "   <- NOT NAMED IN NATIVE TABLE"
        print(f"{tail.ljust(width)}  {','.join(locales_present):14}  {address}{flag}")

    named = [row for row in rows if row[2]]
    print(f"# {len(rows)} records in scope, {len(named)} named in the native string table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())