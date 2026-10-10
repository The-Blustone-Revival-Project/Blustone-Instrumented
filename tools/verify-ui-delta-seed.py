#!/usr/bin/env python3
"""Verify a UI_XML_RO delta seed WITHOUT modifying it.

WHY THIS EXISTS
---------------
plyvel's `DB()` opens LevelDB read/write. Merely iterating such a database is
enough to trigger a background compaction, which rewrites the base table:

    Compacting 2@0 + 0@1 files
    Generated table #64@0: 639 keys, 983254 bytes
    Delete type=2 #5              <- the base 000005.ldb is gone

That destroys the property AGENTS.md section 7 depends on: the native downloader
must not see the already-open base table replaced. So *any* inspection of a seed
must happen on a throwaway copy.

This helper therefore always works on a temporary copy and leaves the seed
untouched. It reports:

  * whether the base `000005.ldb` is byte-identical to the pristine source
  * the key delta versus the pristine database
  * whether `EN/DEFINE_COLOR` exists (it must not)
  * whether the battle record groups are fully covered
  * whether every alias is byte-identical to a reference seed

Usage:
    python tools/verify-ui-delta-seed.py \
        --seed  instrumentation/assets/instrumented-seed-battle-en-delta-v1/UI_XML_RO.db \
        --pristine recovered-assets/phone-2026-09-18/private/files/local/UI_XML_RO.db \
        --reference instrumentation/assets/instrumented-seed-complete-ui-delta-v2/UI_XML_RO.db
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

BATTLE_GROUPS = ("BATTLE/", "SR_BATTLE/", "SR_INGAME/", "SR_INGAME2/")
BASE_TABLE = "000005.ldb"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def open_copy(dbdir: Path, workdir: Path, tag: str) -> Path:
    """Copy a LevelDB directory so it can be opened read/write safely."""
    target = workdir / tag
    shutil.copytree(dbdir, target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--pristine", type=Path, required=True)
    parser.add_argument("--reference", type=Path, default=None)
    args = parser.parse_args()

    try:
        import plyvel
    except ImportError:
        print("plyvel-ci is required: set PYTHONPATH to analysis/leveldb-tooling-ci",
              file=sys.stderr)
        return 2

    failures: list[str] = []
    workdir = Path(tempfile.mkdtemp(prefix="ui-seed-verify-"))
    try:
        # Byte-level checks on the real seed, no LevelDB open needed.
        print("1. BASE TABLE INTEGRITY (read directly, no open)")
        seed_base = args.seed / BASE_TABLE
        pris_base = args.pristine / BASE_TABLE
        if seed_base.is_file() and pris_base.is_file():
            same = digest(seed_base) == digest(pris_base)
            print(f"   {BASE_TABLE} seed={digest(seed_base)[:16]} "
                  f"pristine={digest(pris_base)[:16]}  {'OK' if same else 'FAIL'}")
            if not same:
                failures.append(f"{BASE_TABLE} was rewritten")
        else:
            print(f"   {BASE_TABLE} present in seed: {seed_base.is_file()}")
            if not seed_base.is_file():
                failures.append(f"{BASE_TABLE} missing from seed")
        stamp = args.seed / "stamp.json"
        print(f"   stamp.json preserved: {stamp.is_file()}")
        tables = sorted(p.name for p in args.seed.iterdir()
                        if p.suffix in (".ldb", ".log"))
        print(f"   tables/logs: {tables}")

        seed_copy = open_copy(args.seed, workdir, "seed")
        pris_copy = open_copy(args.pristine, workdir, "pristine")

        seed = plyvel.DB(str(seed_copy), create_if_missing=False)
        pristine = plyvel.DB(str(pris_copy), create_if_missing=False)

        seed_keys = {k for k, _ in seed}
        pristine_keys = {k for k, _ in pristine}

        print()
        print("2. KEY SET")
        print(f"   pristine={len(pristine_keys)}  seed={len(seed_keys)}")
        lost = pristine_keys - seed_keys
        print(f"   pristine keys lost: {len(lost)}  {'OK' if not lost else 'FAIL'}")
        if lost:
            failures.append(f"{len(lost)} pristine keys lost")
        added = sorted(seed_keys - pristine_keys)
        print(f"   keys added: {len(added)}")

        print()
        print("3. SAFETY RULES (AGENTS.md section 7)")
        color = [k for k in seed_keys
                 if k.startswith(b"EN/") and b"DEFINE_COLOR" in k]
        print(f"   EN/DEFINE_COLOR present: {len(color)}  "
              f"{'OK (must be 0)' if not color else 'FAIL'}")
        if color:
            failures.append("EN/DEFINE_COLOR was aliased")
        sentinels = [k for k in seed_keys
                     if b"flush" in k or b"battle_delta" in k]
        print(f"   build sentinels left: {len(sentinels)}  "
              f"{'OK' if not sentinels else 'FAIL'}")
        if sentinels:
            failures.append("build sentinel left in seed")

        print()
        print("4. BATTLE GROUP COVERAGE")
        ko_battle = {k[3:].decode() for k in pristine_keys
                     if k.startswith(b"KO/")
                     and k[3:].decode().startswith(BATTLE_GROUPS)}
        en_all = {k[3:].decode() for k in seed_keys if k.startswith(b"EN/")}
        missing = sorted(ko_battle - en_all)
        print(f"   KO battle records       {len(ko_battle)}")
        print(f"   with an EN alias        {len(ko_battle) - len(missing)}")
        print(f"   missing                 {len(missing)}"
              f"{'  ' + str(missing) if missing else ''}")
        if missing:
            failures.append(f"{len(missing)} battle records lack an EN alias")

        print()
        print("5. PRE-EXISTING RECORDS UNCHANGED")
        changed = [k for k in (pristine_keys & seed_keys)
                   if pristine.get(k) != seed.get(k)]
        print(f"   pre-existing keys whose bytes changed: {len(changed)}  "
              f"{'OK' if not changed else 'FAIL'}")
        for k in changed[:10]:
            print(f"     {k.decode('utf-8', 'replace')}")
        if changed:
            failures.append(f"{len(changed)} pre-existing records modified")

        seed.close()
        pristine.close()

        if args.reference:
            print()
            print("6. BYTE-IDENTITY vs REFERENCE SEED")
            ref_copy = open_copy(args.reference, workdir, "reference")
            ref = plyvel.DB(str(ref_copy), create_if_missing=False)
            seed2 = plyvel.DB(str(seed_copy), create_if_missing=False)
            same = differ = only_ref = 0
            for k in added:
                ref_value = ref.get(k)
                seed_value = seed2.get(k)
                if ref_value is None:
                    only_ref += 1
                    print(f"   not in reference: {k.decode('utf-8', 'replace')}")
                elif ref_value == seed_value:
                    same += 1
                else:
                    differ += 1
                    print(f"   DIFFERS: {k.decode('utf-8', 'replace')}")
            print(f"   identical={same}  differs={differ}  "
                  f"not-in-reference={only_ref}")
            if differ:
                failures.append(f"{differ} aliases differ from the reference seed")
            ref.close()
            seed2.close()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    print()
    if failures:
        print("RESULT: FAIL")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())