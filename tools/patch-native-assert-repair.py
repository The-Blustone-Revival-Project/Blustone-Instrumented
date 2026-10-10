"""Repair the mangled line left by patch-native-assert-flags.py and finish the
RMAssert flag handling (--keep-asserts must leave RMAssert untouched).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tools" / "patch-native-ui-animation.py"


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")

    broken = "    actual_parser_assert = bytes(\nr_assert = bytes(\n"
    fixed = "    actual_parser_assert = bytes(\n"
    if broken in src:
        src = src.replace(broken, fixed)
    elif "r_assert = bytes(" not in src:
        print("nothing to repair")
    else:
        raise SystemExit("unexpected leftover fragment")

    old_doc = """    # --keep-asserts leaves the assertion machinery alone. The three patches
    # below are what stop a failing native assertion from being reported:
    # RMAssert is stubbed to return 0, and the two call-site conditionals are
    # inverted so the branch that would raise is never taken. That makes a
    # broken replica response indistinguishable from a hang, because the client
    # steps over the failure and then waits for something that never happens.
"""
    new_doc = """    # Assertion handling. The three patches below are what stop a failing native
    # assertion from being reported: RMAssert is stubbed to return 0, and the two
    # call-site conditionals are inverted so the branch that would raise is never
    # taken. That makes a broken replica response indistinguishable from a hang,
    # because the client steps over the failure and then waits for something that
    # never happens. --assert-log-continue keeps the reporter and removes only
    # the exit; --keep-asserts leaves all three fully live.
"""
    if old_doc in src:
        src = src.replace(old_doc, new_doc)

    # --keep-asserts must leave RMAssert completely alone.
    old_rm = """    if args.assert_log_continue:
        # Keep the reporter, drop only the exit."""
    new_rm = """    if args.keep_asserts:
        pass  # leave the real reporter and its exit in place
    elif args.assert_log_continue:
        # Keep the reporter, drop only the exit."""
    if src.count(old_rm) != 1:
        raise SystemExit(f"RMAssert branch anchor found {src.count(old_rm)} times")
    src = src.replace(old_rm, new_rm)

    TARGET.write_text(src, encoding="utf-8")
    print(f"repaired {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
