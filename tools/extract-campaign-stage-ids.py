"""Extract the campaign stage-id list from ``LEVELING.jet`` chunk 0.

Why this exists
---------------
``analysis/research/catalogue-report.md`` §4.2 observed that chunk 0 of
``LEVELING.jet`` enumerates the full 50-stage expedition list
``n_01_01``..``n_05_10``, but never wrote it out as data, and
``server-ts/src/bootstrap.ts`` kept publishing an unrelated
``N001``-``N013``/``N500``-``N502`` sweep derived from CDN *art filenames*
instead. This tool turns that observation into a checkable artefact.

What chunk 0 actually is  [CORRECTS the brief]
--------------------------------------------
Chunk 0 is **not** campaign metadata. It is the **CMGE analytics event-key
table**: a flat JSON array of ``{key, global, cmge, pv}`` records whose ``pv``
values are analytics event ids (``1100001``..``1100050`` for the expedition
stages, ``1000200``+ for tutorial events, ``5000000``+ for main-scene
events). It carries **no** titles, no ``ap_cost``, no recommend level, no
monster groups and no area records. The only thing it proves is the exact,
contiguous **id enumeration and its order**.

Usage
-----
    python tools/extract-campaign-stage-ids.py --list analysis/extracted/assets/LEVELING.jet
    python tools/extract-campaign-stage-ids.py analysis/extracted/assets/LEVELING.jet \
        --csv analysis/recovered-data/campaign-stages.csv \
        --json analysis/recovered-data/campaign-stages.json

Writes nothing outside the paths given. Never modifies the source ``.jet``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

# `n_01_01` .. `n_05_10`. The area part is zero-padded to 2 and the stage part
# to 2 in every shipped id, which is what makes the scheme unambiguous.
STAGE_ID_RE = re.compile(r"^n_(\d{2})_(\d{2})$")
# The tutorial keys in the same table use a DIFFERENT, underscore-free scheme.
TUTORIAL_KEY_RE = re.compile(r"^Tuto_(n\d{4})_(\d{2})$")

EXPECTED_SHA256 = "11f902a20b4beed58359da5ae9486ac4246424255fd41041f8e578cb29f2a65d"


def chunk0_bytes(jet: Path) -> bytes:
    """Inflate chunk 0 of ``jet`` using tools/extract-jet-chunk.py's format."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import zlib

    data = jet.read_bytes()
    usize = int.from_bytes(data[0:4], "little")
    csize = int.from_bytes(data[8:12], "little")
    payload = data[24 : 24 + csize]
    body = zlib.decompress(payload)
    # RW records wrap the real content as "RW" + u32 length + content.
    assert body[:2] in (b"RW", b"RWM"), body[:2]
    return body[6 : 6 + usize]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("jet", type=Path)
    ap.add_argument("--csv", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--list", action="store_true", help="print the table and exit")
    args = ap.parse_args()

    body = chunk0_bytes(args.jet)
    digest = hashlib.sha256(body).hexdigest()
    # The table is a UTF-8-BOM JSON array; it is NOT strict JSON because a few
    # records are preceded by a stray leading comma. Tolerate that.
    text = body.decode("utf-8-sig").replace("\r", "").replace("\t", "")
    records = json.loads("[" + text.strip().lstrip("[").rstrip("]").replace(",]", "]") + "]")

    rows = []
    for rec in records:
        key = str(rec.get("key", ""))
        m = STAGE_ID_RE.match(key)
        if m:
            area, stage = int(m.group(1)), int(m.group(2))
            rows.append(
                {
                    "stage_id": key,
                    "area_id": f"n_{area:02d}",
                    "area_serial": area,
                    "stage_serial_in_area": stage,
                    "cmge_pv": rec.get("pv"),
                    "cmge_global": rec.get("global", ""),
                    "cmge_cmge": rec.get("cmge", ""),
                }
            )

    rows.sort(key=lambda r: r["cmge_pv"])
    tutorial = [
        r["key"] for r in records if TUTORIAL_KEY_RE.match(str(r.get("key", "")))
    ]

    if args.list or not (args.csv or args.json):
        print(f"LEVELING.jet chunk 0 sha256={digest}")
        print(f"{len(records)} records; {len(rows)} expedition stage ids; "
              f"{len(tutorial)} tutorial keys")
        print("stage_id      area_id  in_area  pv        global   cmge")
        for r in rows:
            print(
                f"{r['stage_id']:<13} {r['area_id']:<8} {r['stage_serial_in_area']:<8} "
                f"{r['cmge_pv']:<9} {r['cmge_global']:<9} {r['cmge_cmge']}"
            )

    problems = []
    if len(rows) != 50:
        problems.append(f"expected 50 expedition ids, got {len(rows)}")
    for area in range(1, 6):
        got = sorted(r["stage_serial_in_area"] for r in rows if r["area_serial"] == area)
        if got != list(range(1, 11)):
            problems.append(f"n_{area:02d} serials are {got}, expected 1..10")

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(
                fh,
                fieldnames=["stage_id", "area_id", "area_serial",
                            "stage_serial_in_area", "cmge_pv", "cmge_global",
                            "cmge_cmge"],
            )
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {args.csv} ({len(rows)} rows)")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "source": str(args.jet),
                    "chunk": 0,
                    "chunk_name": "common.JSON (CMGE analytics event-key table)",
                    "sha256": digest,
                    "note": (
                        "This is an ANALYTICS EVENT-KEY TABLE, not campaign "
                        "metadata. It proves the exact id enumeration and order "
                        "and nothing else: there are no titles, ap_cost, "
                        "recommend levels, monster groups or area records in it."
                    ),
                    "expedition_stage_count": len(rows),
                    "area_ids": [f"n_{a:02d}" for a in range(1, 6)],
                    "tutorial_keys": tutorial,
                    "stages": rows,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"wrote {args.json}")

    for p in problems:
        print(f"PROBLEM: {p}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())