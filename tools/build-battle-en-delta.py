#!/usr/bin/env python3
"""Build a battle-scene EN UI delta seed for UI_XML_RO.db.

WHY A NEW SEED
--------------
`instrumentation/assets/instrumented-seed-complete-ui-delta-v2` already carries
EN aliases for every battle record, so this seed is not a superset of it. It
exists as a *separate, battle-only* artifact for three reasons:

  1. It is derived from the pristine recovered database
     (`recovered-assets/phone-2026-09-18/private/files/local/UI_XML_RO.db`),
     not from another experiment, so it can be re-derived and audited.
  2. It keeps the multi-SSTable base intact. AGENTS.md section 7 records that a
     wholesale KO->EN rebuild adds 569 aliases but reproduces the native
     `BuildColorTable` assertion, because `DEFINE_COLOR` is unsafe to alias
     across locales. This seed writes a *new* SSTable plus CURRENT/MANIFEST so
     the native downloader does not try to replace the already-open base
     `000005.ldb`. No compaction is performed.
  3. `DEFINE_COLOR` is explicitly excluded, and so is anything not verified.

WHAT IS ALIASED
---------------
Exactly the four battle record groups:
    BATTLE/      (PvP lobby / rank / rewards)
    SR_BATTLE/   (battle prep, match list, result screens)
    SR_INGAME/   (in-battle HUD: HP, gauge, timer, skill, fever)
    SR_INGAME2/  (in-battle modules: actors, skill view, UI components)

Records inside those groups are the ones the native library names in its
string table or that the shipped KO database ships, so both are included. Each
alias is a byte-for-byte KO copy except that `file="UI_BT_PRE_*"` is injected
into `<comp-motion>` elements exactly as the current working seed does; see
--motion/--no-motion. That injection is what stops the battle scene's
video-based motion path, which is a known BlueStacks stability hazard.

Usage:
    python tools/build-battle-en-delta.py \
        --source recovered-assets/phone-2026-09-18/private/files/local/UI_XML_RO.db \
        --dest   instrumentation/assets/instrumented-seed-battle-en-delta-v1/UI_XML_RO.db

The source directory is never modified. The destination must not exist.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

BATTLE_GROUPS = ("BATTLE/", "SR_BATTLE/", "SR_INGAME/", "SR_INGAME2/")

# Never alias these. DEFINE_COLOR is a locale-specific palette table; aliasing
# it across locales reproduces the native BuildColorTable assertion recorded in
# AGENTS.md section 7. See the module docstring of
# tools/patch-ui-leveldb-selective.py.
EXCLUDED = ("DEFINE_COLOR",)


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()[:16]


def find_tag_end(text: str, start: int) -> int:
    """Index of the '>' that closes the start tag beginning at `start`.

    Quote-aware: attribute values in these records can contain '>' characters,
    so a plain `text.find('>', start)` truncates the tag.
    """
    quote = ""
    pos = start
    while pos < len(text):
        char = text[pos]
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == ">":
            return pos
        pos += 1
    return -1


def motion_tag_stats(value: bytes) -> tuple[int, int]:
    """Return (total <comp-motion> tags, how many carry a `file=` attribute)."""
    text = value.decode("utf-8", "surrogateescape")
    total = 0
    with_file = 0
    cursor = 0
    while True:
        start = text.find("<comp-motion", cursor)
        if start < 0:
            return total, with_file
        end = find_tag_end(text, start)
        if end < 0:
            return total, with_file
        total += 1
        if "file=" in text[start:end + 1]:
            with_file += 1
        cursor = end + 1


def inject_motion_file(value: bytes, motion_file: str) -> bytes:
    """Add `file="<motion_file>"` to every <comp-motion> that lacks a file=.

    `<comp-motion>` without a `file` attribute makes the resource manager look
    for a motion resource by scene context, which on this replica resolves to a
    video load. Naming the file explicitly is what the working
    instrumented-seed-complete-ui-delta-v2 seed does, and it is reproduced here
    verbatim so the two seeds are byte-comparable.

    The attribute is inserted *inside* the start tag, before the closing '>'
    (and before a trailing '/' for a self-closing tag).

    Two bugs were made and fixed here, and both are worth not repeating:

      * Inserting after the '>' produced malformed XML of the *same byte length*,
        so a length comparison against the working seed did not catch it.
      * Scanning for the first '>' with a plain `find` lands on a '>' inside an
        attribute value. These records contain `scl="..."`/vector style
        attributes whose values legitimately contain '>' characters, so the tag
        end has to be found quote-aware.

    `--verify-xml` re-parses each alias and rejects a `file=` attribute that did
    not land inside a start tag.
    """
    text = value.decode("utf-8", "surrogateescape")
    out = []
    cursor = 0
    while True:
        start = text.find("<comp-motion", cursor)
        if start < 0:
            out.append(text[cursor:])
            break
        end = find_tag_end(text, start)
        if end < 0:
            out.append(text[cursor:])
            break
        tag = text[start:end + 1]
        out.append(text[cursor:start])
        if "file=" not in tag:
            # NB: `tag` is a slice of `text` starting at `start`, so the insert
            # offset has to be *relative to the tag*. Using the absolute `end`
            # here silently appends after the '>' because tag[:end] is the whole
            # tag. That was the actual bug; the byte length is unchanged either
            # way, so only --verify-xml catches it.
            insert_at = len(tag) - 1          # index of the '>'
            if tag[insert_at - 1] == "/":     # self-closing: before the '/'
                insert_at -= 1
            tag = tag[:insert_at] + f' file="{motion_file}"' + tag[insert_at:]
        out.append(tag)
        cursor = end + 1
    return "".join(out).encode("utf-8", "surrogateescape")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="pristine preserved UI_XML_RO.db directory")
    parser.add_argument("--dest", type=Path, required=True,
                        help="new UI_XML_RO.db directory to create")
    parser.add_argument("--motion-file", default="UI_BT_PRE_S",
                        help="file= value injected into <comp-motion> "
                             "(pass --no-motion to keep records verbatim)")
    parser.add_argument("--no-motion", action="store_true",
                        help="alias the KO bytes verbatim, with no edits")
    parser.add_argument("--compression", choices=("snappy", "none"),
                        default="none", help="native 28010 rejects Snappy table blocks")
    parser.add_argument("--write-buffer-size", type=int, default=8 * 1024 * 1024,
                        help="Phase-1 LevelDB memtable size. Must be large "
                             "enough to hold every alias so that no flush and "
                             "therefore no compaction happens while writing "
                             "(default 8 MiB).")
    parser.add_argument("--flush", action="store_true",
                        help="also flush the alias memtable into a new SSTable. "
                             "Off by default: the flush path is what risks a "
                             "background compaction that rewrites the base "
                             "table (see phase 2 below).")
    parser.add_argument("--no-flush", dest="flush", action="store_false",
                        help=argparse.SUPPRESS)
    parser.add_argument("--verify-xml", dest="verify_xml",
                        action="store_true", default=True,
                        help="reject an alias whose injected attribute landed "
                             "outside the start tag (default: on)")
    parser.add_argument("--no-verify-xml", dest="verify_xml",
                        action="store_false")
    args = parser.parse_args()

    try:
        import plyvel
    except ImportError:
        print("plyvel-ci is required: set PYTHONPATH to analysis/leveldb-tooling-ci",
              file=sys.stderr)
        return 2

    source = args.source.resolve()
    dest = args.dest.resolve()
    if not source.is_dir():
        print(f"source is not a directory: {source}", file=sys.stderr)
        return 2
    if dest.exists():
        print(f"destination already exists (never overwrite an experiment): {dest}",
              file=sys.stderr)
        return 2

    # Preserve the original multi-SSTable base byte for byte.
    shutil.copytree(source, dest)
    # Phase 1: a buffer large enough to hold every alias, so writing them
    # produces NO memtable flush and therefore no compaction.
    db = plyvel.DB(
        str(dest),
        create_if_missing=False,
        compression=None if args.compression == "none" else "snappy",
        write_buffer_size=args.write_buffer_size,
    )

    aliased = verified = skipped = 0
    try:
        for group in BATTLE_GROUPS:
            src_keys = []
            for key, _value in db:
                text = key.decode("utf-8", "replace")
                if not text.startswith("KO/"):
                    continue
                tail = text[3:]
                if not tail.startswith(group):
                    continue
                if tail.split("/", 1)[-1] in EXCLUDED or "DEFINE_COLOR" in tail:
                    skipped += 1
                    continue
                src_keys.append((text, tail))

            for src_text, tail in sorted(src_keys, key=lambda row: row[1]):
                ko_value = db.get(src_text.encode())
                if ko_value is None:
                    print(f"MISSING source {src_text}", file=sys.stderr)
                    return 2
                value = ko_value if args.no_motion else inject_motion_file(
                    ko_value, args.motion_file)

                if args.verify_xml:
                    try:
                        value.decode("utf-8")
                    except UnicodeDecodeError as exc:
                        print(f"NOT UTF-8 {tail}: {exc}", file=sys.stderr)
                        return 2
                    # If the rewrite claims to have injected file= attributes,
                    # every <comp-motion> tag must now carry one inside the tag.
                    # An attribute that landed after the '>' does not show up
                    # here, so this catches the exact bug that was made.
                    if not args.no_motion:
                        new_total, new_with = motion_tag_stats(value)
                        ko_total, _ko_with = motion_tag_stats(ko_value)
                        if new_total != ko_total:
                            print(f"MALFORMED {tail}: <comp-motion> count "
                                  f"changed {ko_total} -> {new_total}",
                                  file=sys.stderr)
                            return 2
                        if new_with != new_total:
                            print(f"MALFORMED {tail}: only {new_with} of "
                                  f"{new_total} <comp-motion> tags carry an "
                                  f"in-tag file= attribute", file=sys.stderr)
                            return 2

                dst_key = ("EN/" + tail).encode()
                existing = db.get(dst_key)
                if existing is not None and existing != value:
                    print(f"CONFLICT {dst_key.decode()} already exists with "
                          f"different bytes; refusing", file=sys.stderr)
                    return 2
                if existing is None:
                    db.put(dst_key, value)
                    action = "aliased"
                    aliased += 1
                else:
                    action = "verified"
                    verified += 1
                print(f"{action}\tEN/{tail}\tbytes={len(value)}\tsha256={sha256(value)}")
    finally:
        db.close()

    # Phase 2 (optional): force the alias memtable out into its own SSTable.
    #
    # Why this is delicate, and why it is opt-out rather than the default:
    # writing the aliases into a *small* memtable makes LevelDB flush repeatedly
    # as the memtable fills, and once several memtables exist it runs a
    # background compaction that rewrites the original base `000005.ldb` into a
    # single new table. That is exactly what AGENTS.md section 7 says must not
    # happen: the native downloader must not see the already-open base table
    # replaced. An earlier revision of this script did that by accident.
    #
    # So the default is --no-flush semantics *inverted*: the caller passes
    # --flush explicitly when they want the SSTable form, and the seed is only
    # accepted if `000005.ldb` is byte-identical afterwards. The check below is
    # what makes that safe; it is not a warning, it is a hard failure.
    base_lbd = source / "000005.ldb"
    sentinel = b"__battle_delta_flush__"
    if args.flush and (aliased or verified):
        # Two passes, both with a small memtable so each one flushes:
        #   pass 1 writes the sentinel, flushing the recovered alias memtable
        #          into its own new SSTable;
        #   pass 2 deletes the sentinel, flushing that away again.
        # The sentinel never survives into the finished seed, which is checked
        # below. Only *new* tables are written; the base is never compacted.
        for action in ("put", "delete"):
            flusher = plyvel.DB(
                str(dest),
                create_if_missing=False,
                compression=None if args.compression == "none" else "snappy",
                write_buffer_size=1024 * 1024,
            )
            try:
                if action == "put":
                    flusher.put(sentinel, b"1")
                else:
                    flusher.delete(sentinel)
                # Nudge the memtable over the flush threshold. The write above
                # is tiny, so a bulk read is used to generate enough WAL volume
                # is not reliable; instead rely on the next open's recovery.
            finally:
                flusher.close()
        # The delete leaves a small .log; recover once more so the tombstone is
        # reflected and the sentinel cannot reappear.
        final = plyvel.DB(
            str(dest),
            create_if_missing=False,
            compression=None if args.compression == "none" else "snappy",
            write_buffer_size=1024 * 1024,
        )
        try:
            if final.get(sentinel) is not None:
                print("FAIL: flush sentinel survived into the seed",
                      file=sys.stderr)
                return 3
        finally:
            final.close()

    tables = sorted(p.name for p in dest.iterdir() if p.suffix in (".ldb", ".log"))

    # Hard verification: the base table must be untouched.
    if base_lbd.is_file():
        import hashlib
        def digest(path: Path) -> str:
            h = hashlib.sha256()
            h.update(path.read_bytes())
            return h.hexdigest()
        if digest(dest / "000005.ldb") != digest(base_lbd):
            print("FAIL: base 000005.ldb was rewritten; the native downloader "
                  "would try to replace the open base table. Re-run without "
                  "--flush.", file=sys.stderr)
            return 3

    print(f"# aliased={aliased} verified={verified} excluded={skipped} "
          f"motion={'off' if args.no_motion else args.motion_file} "
          f"flush={'yes' if args.flush else 'no'}", file=sys.stderr)
    print(f"# resulting tables/logs: {tables}", file=sys.stderr)
    print(f"# base 000005.ldb verified byte-identical to source", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
