"""Dump a recovered Blustone LevelDB reference table to a readable listing.

Read-only.  Prefers plyvel (from analysis/leveldb-tooling-ci), falls back to the
pure-python table reader in tools/inspect-leveldb.py.

Usage:
  python mine-leveldb-table.py --keys TABLE.db --limit 60
  python mine-leveldb-table.py --dump TABLE.db --out dir --limit 40
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

CI_PLYVEL = Path(r"C:\Users\shaha\Documents\ChatGPT\Blustone\analysis\leveldb-tooling-ci")
if CI_PLYVEL.exists():
    sys.path.insert(0, str(CI_PLYVEL))

ASSETS = Path(
    r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets"
    r"\phone-2026-09-18\extracted\split_PADResource\assets"
)


# --- pure python fallback (adapted from tools/inspect-leveldb.py) -------------
def varint(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, pos
        shift += 7


def block_entries(block: bytes):
    if len(block) < 4:
        return
    restart_count = struct.unpack_from("<I", block, len(block) - 4)[0]
    restart_start = len(block) - 4 - restart_count * 4
    pos = 0
    previous = b""
    while pos < restart_start:
        shared, pos = varint(block, pos)
        unshared, pos = varint(block, pos)
        value_length, pos = varint(block, pos)
        key_suffix = block[pos:pos + unshared]
        pos += unshared
        value = block[pos:pos + value_length]
        pos += value_length
        key = previous[:shared] + key_suffix
        previous = key
        yield key, value


def read_block(data: bytes, offset: int, size: int) -> bytes:
    raw = data[offset:offset + size + 5]
    if len(raw) < size + 1:
        return b""
    compression_type = raw[size]
    if compression_type != 0:
        return b""
    return raw[:size]


def handle(data: bytes, pos: int) -> tuple[int, int, int]:
    offset, pos = varint(data, pos)
    size, pos = varint(data, pos)
    return offset, size, pos


def iter_python(path: Path):
    data = path.read_bytes()
    if len(data) < 48:
        return
    footer = data[-48:]
    meta_offset, meta_size, pos = handle(footer, 0)
    index_offset, index_size, _ = handle(footer, pos)
    index = read_block(data, index_offset, index_size)
    for _ik, iv in block_entries(index):
        block_offset, block_size, _ = handle(iv, 0)
        block = read_block(data, block_offset, block_size)
        for key, value in block_entries(block):
            user_key = key[:-8] if len(key) >= 8 else key
            yield user_key, value


def iter_plyvel(path: Path):
    import plyvel  # type: ignore

    db = plyvel.DB(str(path.parent), create_if_missing=False)
    try:
        for key, value in db:
            yield key, value
    finally:
        db.close()


def show(raw: bytes, limit: int = 400) -> str:
    out = []
    printable = sum(1 for b in raw[:2048] if 32 <= b <= 126 or b in (9, 10, 13) or b >= 0x80)
    try:
        text = raw.decode("utf-8")
        if all(c.isprintable() or c in "\r\n\t" for c in text[:2048]):
            return f"TEXT({len(raw)}): " + text[:limit]
    except (UnicodeDecodeError, UnicodeError):
        pass
    if printable / max(1, len(raw[:2048])) > 0.9:
        try:
            return f"TEXT({len(raw)}): " + raw.decode("cp949")[:limit]
        except (UnicodeDecodeError, UnicodeError):
            pass
    return f"BIN({len(raw)}): {raw[:limit].hex(' ')}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keys", metavar="TABLE")
    parser.add_argument("--dump", metavar="TABLE")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--filter")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    name = args.keys or args.dump
    path = Path(name) if Path(name).exists() else ASSETS / name
    if not path.exists():
        cands = sorted(ASSETS.glob(f"{name}*"))
        if not cands:
            raise SystemExit(f"not found: {name}")
        path = cands[0]
    print(f"# table {path} ({path.stat().st_size} bytes)")

    try:
        rows = list(iter_plyvel(path))
        engine = "plyvel"
    except Exception as exc:  # noqa: BLE001
        print(f"# plyvel unavailable/failed ({exc}); using pure-python reader")
        rows = list(iter_python(path))
        engine = "python"

    rows = [(k, v) for k, v in rows if k not in (b"\x00\x01\x00\x00",)]
    print(f"# engine={engine} entries={len(rows)}")
    if args.filter:
        needle = args.filter.encode()
        rows = [(k, v) for k, v in rows if needle in k or needle in v]
        print(f"# after filter: {len(rows)}")

    if args.dump:
        out = args.out or Path(r"C:\Users\shaha\AppData\Local\Temp\opencode\ldb") / path.stem
        out.mkdir(parents=True, exist_ok=True)
        for key, value in rows[: args.limit]:
            try:
                kname = key.decode("utf-8").replace("/", "_").replace("\\", "_")
            except UnicodeDecodeError:
                kname = key.hex()
            (out / f"{kname}.txt").write_bytes(value)
        print(f"# wrote {min(len(rows), args.limit)} values to {out}")

    lines = []
    for key, value in rows[: args.limit]:
        try:
            ktext = key.decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            ktext = key.hex()
        line = f"{ktext}\t{show(value)}"
        print(line[:1200])
        lines.append({"key": ktext, "value": show(value)})
    if args.json_out:
        args.json_out.write_text(
            json.dumps({"table": str(path), "engine": engine, "entries": len(rows), "rows": lines},
                       indent=1, ensure_ascii=False),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()