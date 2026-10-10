"""Build a separate uncompressed host cache, preserving every live raw key/value.

Never opens/writes the source LevelDB. Does not install a cache or modify the app.
Both source and new destination must be under this workspace's recovered-assets.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import sys

REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    source, destination = args.source.resolve(), args.destination.resolve()
    private = REPO / "recovered-assets"
    if not source.is_relative_to(private) or not destination.is_relative_to(private):
        raise SystemExit("Source and destination must be private host paths")
    proof_path = destination.with_suffix(".proof.json")
    if destination.exists() or proof_path.exists() or destination.is_relative_to(source):
        raise SystemExit("Destination must be new and outside source")
    spec = importlib.util.spec_from_file_location("cdn_tables", REPO / "analysis/research/episode-ui-audit.py")
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    before = reader.files_hash(source)
    rows, *_ = reader.read_database(source)
    if not rows or "CDN/header/stamp" not in rows:
        raise SystemExit("Source lacks a live CDN header")
    sys.path.insert(0, str(REPO / "analysis/leveldb-tooling-ci"))
    import plyvel
    destination.parent.mkdir(parents=True, exist_ok=True)
    db = plyvel.DB(str(destination), create_if_missing=True, error_if_exists=True, compression=None)
    try:
        with db.write_batch(sync=True) as batch:
            for key, value in sorted(rows.items()):
                batch.put(key.encode("utf8"), value)
        db.compact_range()
    finally:
        db.close()
    after, _, tables, *_ = reader.read_database(destination)
    if before != reader.files_hash(source) or rows != after:
        raise RuntimeError("Source changed or reconstructed live entries differ; do not install")
    block_count = 0
    for number in tables:
        data = (destination / f"{number:06}.ldb").read_bytes()
        footer = data[-48:]
        meta, meta_size, pos = reader.sst.handle(footer, 0)
        index, index_size, _ = reader.sst.handle(footer, pos)
        blocks = [(meta, meta_size), (index, index_size)]
        for _, value in reader.sst.block_entries(reader.block(data, index, index_size)):
            offset, size, _ = reader.sst.handle(value, 0)
            blocks.append((offset, size))
        for offset, size in blocks:
            if data[offset + size] != 0:
                raise RuntimeError("Reconstructed table is compressed; do not install")
        block_count += len(blocks)
    proof = {"live_entries_preserved_exactly": len(rows), "source_files_unchanged": True,
             "active_sst": tables, "checked_uncompressed_blocks": block_count,
             "installed": False, "files": reader.files_hash(destination)}
    # This proof is outside the DB; never add arbitrary files to a native store.
    with proof_path.open("x", encoding="utf8") as output:
        output.write(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({k: v for k, v in proof.items() if k != "files"}))


if __name__ == "__main__":
    main()
