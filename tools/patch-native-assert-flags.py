"""Make --keep-asserts apply only to the assertion patches.

Previously --keep-asserts returned early, which also skipped the video/UI
compatibility patches. That made it useless: the client died on the known
BlueStacks UI_MA_L1 video fault at the lobby bootstrap, long before reaching
the code anyone wanted to observe.

Now the video fixes, the LoadAnim2 MN_CLOUD fallback and the tutorial guard
always apply, and the three assertion patches are governed by the flags:

  (default)                    RMAssert -> no-op, call-site asserts inverted
  --assert-log-continue        RMAssert keeps logging, only the exit is removed
  --keep-asserts               all three left fully live
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tools" / "patch-native-ui-animation.py"

EARLY_RETURN_START = "    if args.keep_asserts:\n"
EARLY_RETURN_END = "        return 0\n\n    actual_parser_assert = bytes(\n"

GUARD_PARSER = """    data[PARSE_ANIM_ASSERT_OFFSET : PARSE_ANIM_ASSERT_OFFSET + len(PARSE_ANIM_ASSERT_PATCH)] = (
        PARSE_ANIM_ASSERT_PATCH
    )
"""
GUARD_PARSER_NEW = """    if not args.keep_asserts:
        data[PARSE_ANIM_ASSERT_OFFSET : PARSE_ANIM_ASSERT_OFFSET + len(PARSE_ANIM_ASSERT_PATCH)] = (
            PARSE_ANIM_ASSERT_PATCH
        )
"""

GUARD_LEVELDB = """    data[GM_LEVELDB_PUT_ASSERT_OFFSET : GM_LEVELDB_PUT_ASSERT_OFFSET + len(GM_LEVELDB_PUT_ASSERT_PATCH)] = (
        GM_LEVELDB_PUT_ASSERT_PATCH
    )
"""
GUARD_LEVELDB_NEW = """    if not args.keep_asserts:
        data[GM_LEVELDB_PUT_ASSERT_OFFSET : GM_LEVELDB_PUT_ASSERT_OFFSET + len(GM_LEVELDB_PUT_ASSERT_PATCH)] = (
            GM_LEVELDB_PUT_ASSERT_PATCH
        )
"""


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")

    if "if not args.keep_asserts:" in src:
        print("already restructured")
        return 0

    start = src.index(EARLY_RETURN_START)
    end = src.index(EARLY_RETURN_END) + len("    actual_parser_assert = bytes(\n")
    src = src[:start] + "    actual_parser_assert = bytes(\n" + src[end:]

    for old, new in ((GUARD_PARSER, GUARD_PARSER_NEW), (GUARD_LEVELDB, GUARD_LEVELDB_NEW)):
        if src.count(old) != 1:
            raise SystemExit(f"guard anchor found {src.count(old)} times: {old[:60]!r}")
        src = src.replace(old, new)

    TARGET.write_text(src, encoding="utf-8")
    print(f"restructured {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
