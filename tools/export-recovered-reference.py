"""Decode allowlisted, read-only game reference SSTables from the preserved phone copy.

No account databases or live phone files are accessed. Refuse nonempty WALs or
multiple tables because that would require replaying LevelDB's manifest/WAL.
These are client reference/localization records, NOT HTTP endpoint responses.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location("ldb", Path(__file__).with_name("inspect-leveldb.py"))
ldb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ldb)
root = Path(__file__).resolve().parents[1]
source = root / "recovered-assets/phone-2026-09-18/game-assets"
destination = root / "analysis/recovered-reference"
destination.mkdir(exist_ok=True)
manifest = {}
for name in ("CHAR_STR", "INGAME_TALK", "SKILL_DESC", "SKILL_EFFECT", "SKILL_REF", "SKILL_TAG", "TAG_REF", "UI_EPISODE"):
    directory = source / f"{name}_RO.db"
    tables = list(directory.glob("*.ldb"))
    assert len(tables) == 1, directory
    assert not any(log.stat().st_size for log in directory.glob("*.log")), directory
    table = tables[0]
    data = table.read_bytes()
    assert data[-8:] == bytes.fromhex("57fb808b247547db"), table
    _, _, position = ldb.handle(data[-48:], 0)
    offset, size, _ = ldb.handle(data[-48:], position)
    records = {}
    for _, index_value in ldb.block_entries(ldb.read_block(data, offset, size)):
        block_offset, block_size, _ = ldb.handle(index_value, 0)
        for key, value in ldb.block_entries(ldb.read_block(data, block_offset, block_size)):
            sequence_and_type = int.from_bytes(key[-8:], "little")
            key_text = key[:-8].decode("utf-8")
            sequence, kind = sequence_and_type >> 8, sequence_and_type & 255
            assert kind in (0, 1), kind
            if key_text not in records or sequence > records[key_text][0]:
                text = value.decode("utf-8") if kind == 1 else None
                if text is not None:
                    try:
                        parsed = json.loads(text)
                    except json.JSONDecodeError:
                        parsed = text
                else:
                    parsed = None
                records[key_text] = (sequence, kind, parsed)
    exported = {key: record[2] for key, record in sorted(records.items()) if record[1] == 1}
    encoded = (json.dumps(exported, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (destination / f"{name}.json").write_bytes(encoded)
    manifest[name] = {"records": len(exported), "source": str(table.relative_to(root)),
                      "sourceSha256": hashlib.sha256(data).hexdigest(),
                      "exportSha256": hashlib.sha256(encoded).hexdigest()}
    print(f"{name}: {len(exported)} records")
(destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
