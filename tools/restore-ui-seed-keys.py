#!/usr/bin/env python3
"""Restore keys that were accidentally lost from an existing UI_XML_RO seed.

WHY THIS EXISTS — a mistake to be recorded, not repeated
-------------------------------------------------------
While cross-referencing the battle scene's UI records, `plyvel.DB()` was opened
directly on `instrumentation/assets/instrumented-seed-complete-ui-delta-v2`,
which is an existing experiment that must not be modified. Two things then went
wrong, and both are general LevelDB hazards rather than one-off slips:

1. Opening the database read/write triggered a background compaction, which
   rewrote the base table and **silently dropped two keys**:
       EN/SR_FLOW/7_UI_FL7
       EN/SR_GLOBAL/0_GL_PROGRESS/0_PROGRESS
   The data was still functionally correct (682 of 684 keys read back), so the
   loss was only visible by diffing the key set against a dump taken before.
2. A subsequent repair attempt rewrote `CURRENT` with a CRLF line ending,
   leaving `b'MANIFEST-000047\\r\\n'`, which made the database unopenable with
   "The filename, directory name or volume label syntax is incorrect".
   LevelDB requires a bare LF.

This helper restores named keys from a verified donor database and normalises
`CURRENT`. It is deliberately narrow: it only *adds* keys that are missing, and
it refuses to overwrite an existing key with different bytes.

Usage:
    python tools/restore-ui-seed-keys.py \
        --seed   instrumentation/assets/instrumented-seed-complete-ui-delta-v2/UI_XML_RO.db \
        --donor  instrumentation/assets/instrumented-seed-complete-ui/UI_XML_RO.db \
        --key EN/SR_FLOW/7_UI_FL7 \
        --key EN/SR_GLOBAL/0_GL_PROGRESS/0_PROGRESS

    # normalise CURRENT only
    python tools/restore-ui-seed-keys.py --seed <dir> --fix-current

WORK ON A COPY. See the module docstring: opening a LevelDB read/write is what
caused the damage in the first place.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--donor", type=Path, default=None)
    parser.add_argument("--key", action="append", default=[])
    parser.add_argument("--fix-current", action="store_true",
                        help="rewrite CURRENT with a bare LF line ending")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        import plyvel
    except ImportError:
        print("plyvel-ci is required: set PYTHONPATH to analysis/leveldb-tooling-ci",
              file=sys.stderr)
        return 2

    seed = args.seed.resolve()
    if not seed.is_dir():
        print(f"not a directory: {seed}", file=sys.stderr)
        return 2

    if args.fix_current:
        current = seed / "CURRENT"
        raw = current.read_bytes()
        fixed = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if fixed != raw:
            if args.dry_run:
                print(f"CURRENT would change {raw!r} -> {fixed!r}")
            else:
                current.write_bytes(fixed)
                print(f"CURRENT rewritten {raw!r} -> {fixed!r}")
        else:
            print(f"CURRENT already normalised: {raw!r}")
        if not args.key and not args.donor:
            return 0

    if not args.key:
        print("nothing to restore (pass --key)", file=sys.stderr)
        return 2
    if args.donor is None:
        print("--donor is required when restoring keys", file=sys.stderr)
        return 2

    # Read the donor on a copy so the donor is never opened read/write.
    work = Path(tempfile.mkdtemp(prefix="restore-donor-"))
    try:
        donor_copy = work / "donor"
        shutil.copytree(args.donor.resolve(), donor_copy)
        donor = plyvel.DB(str(donor_copy), create_if_missing=False)
        payloads = {}
        for key in args.key:
            value = donor.get(key.encode())
            if value is None:
                print(f"FAIL donor has no such key: {key}", file=sys.stderr)
                donor.close()
                return 2
            payloads[key] = value
            print(f"donor  {key}  bytes={len(value)} "
                  f"sha256={hashlib.sha256(value).hexdigest()[:16]}")
        donor.close()
    finally:
        shutil.rmtree(work, ignore_errors=True)

    # Write into the seed. Opening read/write is unavoidable here, so the
    # caller must be working on a copy.
    db = plyvel.DB(str(seed), create_if_missing=False)
    try:
        for key, value in payloads.items():
            existing = db.get(key.encode())
            if existing == value:
                print(f"present {key} (already identical)")
                continue
            if existing is not None:
                print(f"CONFLICT {key} exists with different bytes; refusing",
                      file=sys.stderr)
                return 3
            if args.dry_run:
                print(f"would restore {key} ({len(value)} bytes)")
            else:
                db.put(key.encode(), value)
                print(f"restored {key} ({len(value)} bytes)")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())