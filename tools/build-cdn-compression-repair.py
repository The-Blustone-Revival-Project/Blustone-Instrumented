"""Prepare public bootstrap-table replacement; preserve live table history.

Only the already-released bootstrap table and manifest metadata become assets.
Live encrypted values in other tables remain private and byte-identical.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import shutil
import json
import re
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cdn_writer", ROOT / "tools/build-episode-ui-delta.py")
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)
audit = writer.audit
PIN = "e2ae5a5d12dc208a0991e2435fcf8ae117cab4a64e02e45174220300e2ce100b"


def rows(data):
    footer = data[-48:]
    _, _, pos = audit.sst.handle(footer, 0)
    offset, size, _ = audit.sst.handle(footer, pos)
    result = []
    for _, handle in audit.sst.block_entries(audit.block(data, offset, size)):
        offset, size, _ = audit.sst.handle(handle, 0)
        result.extend(audit.sst.block_entries(audit.block(data, offset, size)))
    return result


def manifest(original, records, size):
    # Builder retains its first same-number added-file object across edits.
    # Rewrite existing size fields; delete/re-add of file5 is NOT an update.
    result = b""
    changed = 0
    for data in audit.log.write_batches(original):
        pos = 0
        patches = []
        def field():
            nonlocal pos
            length, pos = audit.sst.varint(data, pos)
            value = data[pos:pos + length]
            pos += length
            return value
        while pos < len(data):
            tag, pos = audit.sst.varint(data, pos)
            if tag == 1:
                field()
            elif tag in (2, 3, 4, 9):
                _, pos = audit.sst.varint(data, pos)
            elif tag == 5:
                _, pos = audit.sst.varint(data, pos)
                field()
            elif tag == 6:
                _, pos = audit.sst.varint(data, pos)
                _, pos = audit.sst.varint(data, pos)
            elif tag == 7:
                level, pos = audit.sst.varint(data, pos)
                number, pos = audit.sst.varint(data, pos)
                start = pos
                old_size, pos = audit.sst.varint(data, pos)
                end = pos
                smallest, largest = field(), field()
                if number == 5:
                    if level != 0 or old_size not in (1503, 2962) or smallest != records[0][0] or largest != records[-1][0]:
                        raise ValueError("Unsupported table5 manifest metadata")
                    patches.append((start, end, writer.varint(size)))
                    changed += 1
            else:
                raise ValueError("Unsupported manifest tag")
        rewritten = bytearray(data)
        for start, end, value in reversed(patches):
            rewritten[start:end] = value
        result = writer.append_log(result, bytes(rewritten))
    if changed != 1:
        raise ValueError("Expected exactly one table5 addition")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bootstrap", type=Path)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Output must be new")
    before = audit.files_hash(args.snapshot)
    original = (args.bootstrap / "000005.ldb").read_bytes()
    if hashlib.sha256(original).hexdigest() != PIN:
        raise SystemExit("Unsupported bootstrap/live compressed table")
    records = rows(original)
    replacement = writer.table(records)
    if (args.snapshot / "000005.ldb").read_bytes() not in (original, replacement):
        raise SystemExit("Unsupported live bootstrap table")
    if rows(replacement) != records:
        raise RuntimeError("Internal keys, sequence tags or encrypted values changed")
    migration = args.output / "migration"
    migration.mkdir(parents=True)
    (migration / "000005.ldb").write_bytes(replacement)
    name = (args.snapshot / "CURRENT").read_text().strip()
    if not re.fullmatch(r"MANIFEST-[0-9]{6}", name):
        raise SystemExit("Unsupported live manifest")
    (migration / name).write_bytes(manifest((args.snapshot / name).read_bytes(), records, len(replacement)))
    bootstrap = args.output / "bootstrap"
    shutil.copytree(args.bootstrap, bootstrap)
    bootstrap_name = (bootstrap / "CURRENT").read_text().strip()
    (bootstrap / "000005.ldb").write_bytes(replacement)
    (bootstrap / bootstrap_name).write_bytes(manifest((bootstrap / bootstrap_name).read_bytes(), records, len(replacement)))
    check = Path(tempfile.mkdtemp(prefix="physical-repair-check-", dir=ROOT / "recovered-assets/cdn-cache-20261010")) / "CDN.db"
    shutil.copytree(args.snapshot, check)
    for item in migration.iterdir():
        shutil.copyfile(item, check / item.name)
    old, *_ = audit.read_database(args.snapshot)
    new, *_ = audit.read_database(check)
    if old != new or before != audit.files_hash(args.snapshot):
        raise RuntimeError("Live values/source changed")
    # Actually open the disposable validation copy: this catches recovered
    # file-size/footer failures that the pure key replay intentionally ignores.
    sys.path.insert(0, str(ROOT / "analysis/leveldb-tooling-ci"))
    import plyvel
    db = plyvel.DB(str(check), create_if_missing=False, compression=None)
    try:
        recovered = {key.decode("utf8"): value for key, value in db.iterator(verify_checksums=True)}
        if recovered != old:
            raise RuntimeError("LevelDB recovery changed live entries")
    finally:
        db.close()
    proof = {"bootstrap_internal_records_preserved": len(records),
             "live_entries_preserved": len(new), "replacement_bytes": len(replacement),
             "source_unchanged": before == audit.files_hash(args.snapshot),
             "host_leveldb_recovery_and_checksums_passed": True,
             "assets": audit.files_hash(migration), "installed": False}
    (args.output / "proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof))


if __name__ == "__main__":
    main()
