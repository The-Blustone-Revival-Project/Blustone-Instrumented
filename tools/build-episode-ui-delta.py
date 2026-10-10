"""Create six native-proved EN Episode layouts as an append-only SSTable delta.

Never opens LevelDB, compacts, or writes the source. Destination must be new.
This prepares a candidate, not an installed/rebuilt instrumented APK.
"""
import argparse
import hashlib
import importlib.util
import shutil
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("episode_audit", ROOT / "analysis/research/episode-ui-audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
LAYOUTS = ("E_T_EPISODE", "E_T_STAGE", "E_C_EPISODE", "E_C_STAGE", "E_C_MAPMARK", "E_T_STAGEMAP")

def varint(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    return bytes(result + bytes([value]))

def field(value):
    return varint(len(value)) + value

def crc(data):
    value = 0xffffffff
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0x82f63b78 if value & 1 else 0)
    return value ^ 0xffffffff

def masked_crc(data):
    value = crc(data)
    return ((value >> 15 | value << 17) + 0xa282ead8) & 0xffffffff

def block(rows):
    body, restarts = bytearray(), []
    for key, value in rows:
        restarts.append(len(body))
        body.extend(varint(0) + varint(len(key)) + varint(len(value)) + key + value)
    if not restarts:
        restarts = [0]
    body.extend(struct.pack("<" + "I" * (len(restarts) + 1), *restarts, len(restarts)))
    return bytes(body)

def physical_block(body):
    return body + b"\0" + struct.pack("<I", masked_crc(body + b"\0"))

def table(rows):
    data = block(rows)
    meta_offset = len(data) + 5
    meta = block([])
    index_offset = meta_offset + len(meta) + 5
    index = block([(rows[-1][0], varint(0) + varint(len(data)))])
    footer = (varint(meta_offset) + varint(len(meta)) + varint(index_offset) + varint(len(index))).ljust(40, b"\0")
    return physical_block(data) + physical_block(meta) + physical_block(index) + footer + bytes.fromhex("57fb808b247547db")

def append_log(original, record):
    result, pos, first = bytearray(original), 0, True
    while pos < len(record):
        remaining = 32768 - len(result) % 32768
        if remaining <= 7:
            result.extend(bytes(remaining))
            remaining = 32768
        size = min(remaining - 7, len(record) - pos)
        last = pos + size == len(record)
        kind = 1 if first and last else 2 if first else 4 if last else 3
        payload = record[pos:pos + size]
        result.extend(struct.pack("<IHB", masked_crc(bytes([kind]) + payload), size, kind) + payload)
        pos += size
        first = False
    return bytes(result)

def counters(manifest):
    sequence = next_file = 0
    for record in audit.log.write_batches(manifest):
        pos = 0
        while pos < len(record):
            tag, pos = audit.sst.varint(record, pos)
            if tag == 1:
                size, pos = audit.sst.varint(record, pos); pos += size
            elif tag in (2, 3, 4, 9):
                value, pos = audit.sst.varint(record, pos)
                if tag == 3: next_file = max(next_file, value)
                if tag == 4: sequence = max(sequence, value)
            elif tag in (5, 6, 7):
                _, pos = audit.sst.varint(record, pos)
                if tag != 5: _, pos = audit.sst.varint(record, pos)
                if tag == 7: _, pos = audit.sst.varint(record, pos)
                for _ in range(2 if tag == 7 else 1 if tag == 5 else 0):
                    size, pos = audit.sst.varint(record, pos); pos += size
            else:
                raise ValueError(f"Unsupported VersionEdit tag {tag}")
    return sequence, next_file

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    source, destination = args.source.resolve(), args.destination.resolve()
    if destination.exists() or source == destination:
        raise ValueError("Destination must be a new directory")
    before = audit.files_hash(source)
    existing, manifest_name, _, log_number, previous_log = audit.read_database(source)
    aliases = {}
    for name in LAYOUTS:
        original, target = "KO/EPISODE/" + name, "EN/EPISODE/" + name
        if original not in existing or target in existing:
            raise ValueError(f"Missing source or preexisting target: {name}")
        aliases[target] = existing[original]
    manifest = (source / manifest_name).read_bytes()
    sequence, next_file = counters(manifest)
    for number in {log_number, previous_log} - {0}:
        file = source / f"{number:06}.log"
        if file.exists():
            for record in audit.log.write_batches(file.read_bytes()):
                sequence = max(sequence, int.from_bytes(record[:8], "little") + int.from_bytes(record[8:12], "little"))
    used = [int(p.name.split("-")[-1].split(".")[0]) for p in source.iterdir() if p.name.split("-")[-1].split(".")[0].isdigit()]
    number = max(next_file, max(used) + 1)
    rows = [(key.encode() + struct.pack("<Q", ((sequence + i + 1) << 8) | 1), value)
            for i, (key, value) in enumerate(sorted(aliases.items()))]
    payload = table(rows)
    edit = varint(3) + varint(number + 2) + varint(4) + varint(sequence + len(rows))
    edit += varint(7) + varint(0) + varint(number) + varint(len(payload)) + field(rows[0][0]) + field(rows[-1][0])
    shutil.copytree(source, destination)
    (destination / f"{number:06}.ldb").write_bytes(payload)
    new_manifest = f"MANIFEST-{number + 1:06}"
    (destination / new_manifest).write_bytes(append_log(manifest, edit))
    (destination / "CURRENT").write_bytes((new_manifest + "\n").encode())
    actual, *_ = audit.read_database(destination)
    if actual != {**existing, **aliases} or audit.files_hash(source) != before:
        raise ValueError("Delta verification/source-preservation failed")
    for name, digest in before.items():
        if name != "CURRENT" and hashlib.sha256((destination / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Original file changed: {name}")
    if "EN/DEFINE_COLOR" in actual and "EN/DEFINE_COLOR" not in existing:
        raise ValueError("Unsafe palette alias")
    print(f"Verified six byte-identical Episode aliases; {len(existing)} -> {len(actual)} keys; original files preserved; candidate only.")

if __name__ == "__main__":
    main()
