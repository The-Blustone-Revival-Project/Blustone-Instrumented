"""Add --assert-log-continue to the native patcher.

Keeps the real _RMAssert (so it logs "ASSERTION Failed on 'file(line)'") and
removes only the process-terminating call, so a wrong replica response surfaces
the parser and source line that rejected it instead of vanishing.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tools" / "patch-native-ui-animation.py"

BLOCK = '''
# --- assertions that report and continue -------------------------------------
#
# _RMAssert (0x10B3ABC) does, in order:
#   0x10b3b18  bl  _RMAssertSave     record the failure
#   0x10b3b24  bl  _RMAssertPrint    log "ASSERTION Failed on 'file(line)'"
#   0x10b3b48  bl  RMPopMessageBox   tear down the message box
#   0x10b3b5c  blx <plt>             exit()/abort(): the process dies here
#
# The default build replaces the whole function with a no-op, which silences the
# log too, so a bad replica response is indistinguishable from a hang.
# --assert-log-continue keeps the real function and replaces only the
# terminating blx with a branch back to the function's own epilogue at
# 0x10b3b4c. That epilogue re-evaluates the same condition it just evaluated, so
# it takes the same return path; nothing but the exit is removed. The literal
# pool starts at 0x10b3b60, so only 4 bytes at 0x10b3b5c are touched.
#
# Execution may still fault a few instructions later where the caller
# dereferences the value it just asserted on. That is the point: the assertion
# line is already in the log, naming the parser and source line.
RM_ASSERT_TERM_OFFSET = 0x10B3B5C
RM_ASSERT_TERM_EXPECTED = bytes.fromhex("fc8df03d")
RM_ASSERT_EPILOGUE = 0x10B3B4C
RM_ASSERT_TERM_PATCH_LEN = 4
'''

FLAG = '''    parser.add_argument(
        "--assert-log-continue",
        action="store_true",
        help="Keep the native assertion reporter but do not exit on failure.",
    )
'''

OLD_SILENCE = """    actual_rm_assert = bytes(data[RM_ASSERT_OFFSET : RM_ASSERT_OFFSET + len(RM_ASSERT_EXPECTED)])
    if actual_rm_assert != RM_ASSERT_EXPECTED:
        raise SystemExit(
            f"unexpected RMAssert bytes at 0x{RM_ASSERT_OFFSET:x}: "
            f"{actual_rm_assert.hex()} expected {RM_ASSERT_EXPECTED.hex()}"
        )
    data[RM_ASSERT_OFFSET : RM_ASSERT_OFFSET + len(RM_ASSERT_PATCH)] = RM_ASSERT_PATCH
"""

NEW_SILENCE = """    actual_rm_assert = bytes(data[RM_ASSERT_OFFSET : RM_ASSERT_OFFSET + len(RM_ASSERT_EXPECTED)])
    if actual_rm_assert != RM_ASSERT_EXPECTED:
        raise SystemExit(
            f"unexpected RMAssert bytes at 0x{RM_ASSERT_OFFSET:x}: "
            f"{actual_rm_assert.hex()} expected {RM_ASSERT_EXPECTED.hex()}"
        )
    if args.assert_log_continue:
        # Keep the reporter, drop only the exit.
        term = bytes(
            data[RM_ASSERT_TERM_OFFSET : RM_ASSERT_TERM_OFFSET + len(RM_ASSERT_TERM_EXPECTED)]
        )
        if term != RM_ASSERT_TERM_EXPECTED:
            raise SystemExit(
                f"unexpected RMAssert terminator at 0x{RM_ASSERT_TERM_OFFSET:x}: "
                f"{term.hex()} expected {RM_ASSERT_TERM_EXPECTED.hex()}"
            )
        patch = thumb_branch(RM_ASSERT_TERM_OFFSET, RM_ASSERT_EPILOGUE)
        patch += b"\\x00\\xbf" * ((RM_ASSERT_TERM_PATCH_LEN - len(patch)) // 2)
        data[RM_ASSERT_TERM_OFFSET : RM_ASSERT_TERM_OFFSET + len(patch)] = patch
    else:
        data[RM_ASSERT_OFFSET : RM_ASSERT_OFFSET + len(RM_ASSERT_PATCH)] = RM_ASSERT_PATCH
"""


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "assert_log_continue" in src:
        print("already patched")
        return 0

    anchor = 'BOOTSTRAP_TARGET = b"10.0.2.2:8080"\n'
    if src.count(anchor) != 1:
        raise SystemExit(f"anchor found {src.count(anchor)} times")
    src = src.replace(anchor, anchor + BLOCK)

    if src.count('    args = parser.parse_args()') != 1:
        raise SystemExit("parse_args anchor not unique")
    src = src.replace('    args = parser.parse_args()', FLAG + "    args = parser.parse_args()")

    if src.count(OLD_SILENCE) != 1:
        raise SystemExit(f"RMAssert block found {src.count(OLD_SILENCE)} times")
    src = src.replace(OLD_SILENCE, NEW_SILENCE)

    TARGET.write_text(src, encoding="utf-8")
    print(f"patched {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
