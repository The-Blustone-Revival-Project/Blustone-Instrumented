"""Check that every `text-global` id used by a set of UI records exists for the
`EN` locale in a sibling UI database.

The battle scene's UI records carry `text-global="TX_..."` attributes. Those ids
are not in `UI_XML_RO.db`; they live in `UI_JSON.db`, keyed
`<group>|<TX_ID>|<LOCALE>` (observed form: `0|TX_MY_ST|EN`). If the `EN` row is
missing the battle scene renders with blank strings — a silent failure, not a
crash, which is exactly the kind of thing that is easy to misattribute.

This helper takes a UI_XML_RO database, reads the ids out of the records in the
given groups, and reports which ones have no EN row in the UI_JSON database.

Usage:
    python tools/check-text-global-coverage.py \
        --xml-db instrumentation/assets/instrumented-seed-complete-ui-delta-v2/UI_XML_RO.db \
        --json-dir recovered-assets/phone-2026-09-18/extracted/split_PADResource/assets/UI_JSON.db
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TEXT_GLOBAL = re.compile(r'text-global\s*=\s*"([^"]+)"')
# `text="..."` is usually a literal placeholder, not a UI_JSON.db key, so it is
# only collected when it looks like a TX_ id.
TEXT_ATTR = re.compile(r'\btext\s*=\s*"(TX_[A-Z0-9_]+)"')
TX_ID = re.compile(r'^[A-Z][A-Z0-9_]*$')

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "read_leveldb_log", Path(__file__).resolve().parent / "read-leveldb-log.py")
_rll = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rll)
batch_operations = _rll.batch_operations
write_batches = _rll.write_batches


def load_json_rows(dbdir: Path) -> set[str]:
    rows: set[str] = set()
    for logfile in sorted(dbdir.glob("*.log")):
        for batch in write_batches(logfile.read_bytes()):
            for _tag, key, value in batch_operations(batch):
                text = key.decode("utf-8", "replace")
                if "|" not in text:
                    continue
                rows.add(text)
                if value:
                    rows.add(text)  # keep keys; values are the translated strings
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml-db", type=Path, required=True)
    parser.add_argument("--json-dir", type=Path, required=True)
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

    wanted: dict[str, set[str]] = {}
    db = plyvel.DB(str(args.xml_db), create_if_missing=False)
    try:
        for key, value in db:
            text = key.decode("utf-8", "replace")
            head, _, tail = text.partition("/")
            if head != "EN":
                continue
            if not any(tail.upper().startswith(g.upper() + "/") for g in args.group):
                continue
            body = value.decode("utf-8", "replace")
            for ident in TEXT_GLOBAL.findall(body) + TEXT_ATTR.findall(body):
                if ident:
                    wanted.setdefault(ident, set()).add(tail)
    finally:
        db.close()

    rows = load_json_rows(args.json_dir)
    have_en = {r for r in rows if r.endswith("|EN")}
    ids = {r.split("|")[1] for r in have_en if r.count("|") >= 2}
    ko_ids = {r.split("|")[1] for r in rows if r.endswith("|KO") and r.count("|") >= 2}

    # Only treat the reference as a real UI_JSON.db key when it looks like one.
    wanted = {k: v for k, v in wanted.items() if TX_ID.match(k)}
    missing_en = sorted(set(wanted) - ids)
    missing_all = sorted(set(wanted) - ids - ko_ids)

    print(f"# {len(wanted)} distinct text ids referenced by the battle records")
    print(f"# UI_JSON.db has {len(ids)} ids with an EN row, {len(ko_ids)} with a KO row")
    print()
    print("## referenced ids with NO EN row in UI_JSON.db")
    for ident in missing_en:
        srcs = sorted(wanted[ident])
        where = "in UI_JSON.db under KO only" if ident in ko_ids else "ABSENT from UI_JSON.db"
        print(f"  {ident:22} {where:32} <- {', '.join(srcs[:3])}")
    print(f"# {len(missing_en)} missing EN rows "
          f"({len(missing_all)} of those are absent from UI_JSON.db entirely)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())