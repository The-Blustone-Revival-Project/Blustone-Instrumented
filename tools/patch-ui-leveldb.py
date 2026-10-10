"""Clone preserved Korean UI records under missing English keys.

The archived phone resource store contains a large Korean UI catalog, while the
emulator requests the same records under EN/... .  This local compatibility
transform preserves the original database and only adds aliases for English
keys that are absent from an explicitly selected output directory.  Existing
English records always win.

Requires the official-compatible ``plyvel-ci`` Windows wheel:
    python -m pip install plyvel-ci
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Preserved UI_XML_RO LevelDB directory")
    parser.add_argument("destination", type=Path, help="New output LevelDB directory")
    parser.add_argument("--compact", action="store_true", help="Compact aliases into SSTables before closing")
    parser.add_argument("--rebuild", action="store_true", help="Build a fresh LevelDB instead of copying source files")
    parser.add_argument(
        "--force-prefix",
        action="append",
        default=[],
        help="Also write every source record with this key prefix into the new SSTable",
    )
    args = parser.parse_args()

    try:
        import plyvel
    except ImportError as error:
        raise SystemExit("Install plyvel-ci before running this tool: python -m pip install plyvel-ci") from error

    if args.destination.exists():
        raise SystemExit(f"Refusing to overwrite existing destination: {args.destination}")
    args.destination.parent.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    force_prefixes = tuple(prefix.encode("utf-8") for prefix in args.force_prefix)
    if args.rebuild:
        source_db = plyvel.DB(str(args.source), create_if_missing=False)
        try:
            source_items = list(source_db)
        finally:
            source_db.close()
        source_keys = {key for key, _value in source_items}
        db = plyvel.DB(str(args.destination), create_if_missing=True, error_if_exists=True,
                       write_buffer_size=64 * 1024 * 1024, compression=None)
        try:
            with db.write_batch(transaction=True) as batch:
                for key, value in source_items:
                    batch.put(key, value)
                for key, value in source_items:
                    if not key.startswith(b"KO/"):
                        continue
                    # DEFINE_COLOR is locale-specific engine metadata; the
                    # Korean payload is not a valid English color-table seed.
                    if key == b"KO/DEFINE_COLOR":
                        continue
                    target = b"EN/" + key[len(b"KO/"):]
                    if target not in source_keys:
                        batch.put(target, value)
                        copied.append(target.decode("utf-8"))
            if args.compact:
                db.compact_range()
        finally:
            db.close()
    else:
        shutil.copytree(args.source, args.destination)
        # The native client accepts the uncompressed LevelDB blocks emitted by
        # the Android-side fork. Its Snappy reader rejects the blocks emitted
        # by the Windows wheel, so leave newly-created delta SSTables plain.
        db = plyvel.DB(str(args.destination), create_if_missing=False, compression=None)
        try:
            with db.write_batch(transaction=True) as batch:
                if force_prefixes:
                    for key, value in db:
                        if any(key.startswith(prefix) for prefix in force_prefixes):
                            batch.put(key, value)
                            copied.append(key.decode("utf-8"))
                for key, value in db:
                    if not key.startswith(b"KO/"):
                        continue
                    if key == b"KO/DEFINE_COLOR":
                        continue
                    target = b"EN/" + key[len(b"KO/"):]
                    if db.get(target) is None:
                        batch.put(target, value)
                        copied.append(target.decode("utf-8"))
            if args.compact:
                db.compact_range()
        finally:
            db.close()

    print(f"copied={len(copied)}")
    for key in copied:
        print(key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
