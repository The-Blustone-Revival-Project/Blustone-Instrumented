#!/usr/bin/env python3
"""Create an instrumented-only native library with local bootstrap routing.

The shipped ARM function CRMResourceMgr::MakeAnim2FromVideo begins at the
known offset below.  Its normal path dereferences an uninitialized video
animation global for UI_MA_L1 on BlueStacks/Houdini.  Replace only that
function prologue with ``movs r0, #0; bx lr; nop`` in a copy of the library.
The stage-map path can also request an empty animation name. A small Thumb
stub is placed in the now-unreachable body of the bypassed video function; it
keeps the normal ``LoadAnim2`` prologue, substitutes ``MN_CLOUD`` only for a
null/empty or ``UI_MA_*`` name, and resumes at the original resource lookup. The same copy
also makes the recovered ``CSRUIParser::ParseRes2`` missing-animation
assertion non-fatal, allowing a missing visual to be skipped while keeping the
rest of the UI scene alive. A second small guard preserves the base Snowfield
stage map while skipping only the null tutorial-finger animation object. The same copy
turns the native RANN assertion reporter into a no-op for this instrumented
build; this is deliberately scoped to the research APK so a protocol/data
mistake can be observed without the client exiting before its request is
captured. The source library is verified and never modified.
The same copy
redirects the native launcher host from the retired production host to the
local replica. The source library is verified and never modified.
"""

from __future__ import annotations

import argparse
import shutil
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FUNCTION_OFFSET = 0x10DA690
EXPECTED = bytes.fromhex("f0b503af2de9")
PATCH = bytes.fromhex("0020704700bf")
LOAD_ANIM_OFFSET = 0x10DA4E8
LOAD_ANIM_CAVE_OFFSET = 0x10DA696
LOAD_ANIM_BRANCH = bytes.fromhex("d5e0")
LOAD_ANIM_CAVE_RESOURCE_ADR = 0x2C
LOAD_ANIM_CAVE_BRANCH = 0x32
LOAD_ANIM_CAVE_RESOURCE_TEXT = 0x40
LOAD_ANIM_CAVE = bytes.fromhex(
    "f0b503af4df804bd82b0054671b10b7863b1552b08d14b78492b05d18b785f2b"
    "02d1cb784d2b01d00e4600e0034e2846"
    "3146dff800f00000000000bf00000000"
)
LOAD_ANIM_FALLBACK = b"MN_CLOUD\x00"
PARSE_ANIM_ASSERT_OFFSET = 0x107FA10
PARSE_ANIM_ASSERT_EXPECTED = bytes.fromhex("0020")
PARSE_ANIM_ASSERT_PATCH = bytes.fromhex("0120")
GM_LEVELDB_PUT_ASSERT_OFFSET = 0x784CFE
GM_LEVELDB_PUT_ASSERT_EXPECTED = bytes.fromhex("0020")
GM_LEVELDB_PUT_ASSERT_PATCH = bytes.fromhex("0120")
RM_ASSERT_OFFSET = 0x10B3ABC
RM_ASSERT_EXPECTED = bytes.fromhex("f0b503af2de9")
RM_ASSERT_PATCH = bytes.fromhex("0020704700bf")
TUTORIAL_ANIM_GUARD_OFFSET = 0x10DA700
TUTORIAL_ANIM_GUARD_ENTRY_OFFSET = 0xEECC00
TUTORIAL_ANIM_GUARD_ENTRY_EXPECTED = bytes.fromhex("70690168")
TUTORIAL_ANIM_GUARD_NONNULL_RETURN = 0xEECC0A
TUTORIAL_ANIM_GUARD_NULL_RETURN = 0xEECC38
TUTORIAL_ANIM_GUARD = bytes.fromhex("706928b10168d1f89010884700f000b800f000b8")
BOOTSTRAP_HOST_OFFSET = 0x1D5EC56
BOOTSTRAP_HOST = b"pv-prd.vshower.com"
BOOTSTRAP_TARGET = b"10.0.2.2:8080"

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
# blx <plt+0x2c> - objdump prints the halfwords swapped, the file holds this.
RM_ASSERT_TERM_EXPECTED = bytes.fromhex("5df5becf")
RM_ASSERT_EPILOGUE = 0x10B3B4C
RM_ASSERT_TERM_PATCH_LEN = 4

# .text of the shipped armeabi-v7a libnative_core.so. vaddr == file offset here.
TEXT_START = 0x00612CC0
TEXT_END = 0x01BD46F8

# --- optional assertion-argument tracer (--assert-arg-trace) ----------------
#
# _RMAssert is the only place the engine says "I will not continue", and its log
# line names the source location but never the offending value. The tracer is a
# freestanding Thumb stub (instrumentation/native/blustone-assert-trace.S) that
# is built and independently verified by tools/build-assert-trace-blob.py.
#
# _RMAssert's first four bytes become a 4-byte B.W to the stub. The stub
# restores every register, RE-CREATES the removed prologue verbatim, and then
# branches to 0x10B3AC0. Re-creating it is mandatory: the second removed
# instruction, `add r7, sp, #0xc`, sets the frame pointer that _RMAssert then
# dereferences (`add.w r1, r7, #8` at 0x10B3ADA, `ldr r0, [r7, #8]` at 0x10B3AEC).
# Resuming without it makes the first assertion read through whatever the caller
# left in r7. Because the stub re-creates the prologue, the resume state is
# bit-identical to a normal call, so --assert-log-continue still logs without
# exiting and --keep-asserts still exits. Nothing is weakened.
#
# Requiring an assertion-live build is deliberate: the default build replaces
# _RMAssert with `movs r0,#0; bx lr; nop`, so there would be no assertion left to
# describe and the resume address would differ.
#
# STATUS: the cave offset below is 0x10DA720, which is WRONG and must stay
# disabled. 2.8.0.1+6 shipped it and boot-broke the client 5 launches out of 5.
# "The function's prologue is stubbed, so its body is dead" is false: twelve
# direct branches inside MakeAnim2FromVideo target 0x10DA720-0x10DA8C1, and
# overwriting that inner loop broke the lobby bootstrap. The
# incoming_branch_targets gate below now refuses this offset, so the boot-breaking
# library can no longer be produced. A correct tracer needs a cave that no branch
# in the library targets and that nothing falls into; see
# analysis/testing/instr-002.md for the search and why no static cave works for a
# stub of this size.
ASSERT_TRACE_BLOB = ROOT / "local" / "legacy-analysis" / "patched" / "assert-trace-blob.bin"
ASSERT_TRACE_SENTINEL = bytes.fromhex("11ba57ba")
ASSERT_TRACE_CAVE_OFFSET = 0x10DA720
ASSERT_TRACE_HOOK_OFFSET = 0x10B3ABC
ASSERT_TRACE_HOOK_EXPECTED = RM_ASSERT_EXPECTED
ASSERT_TRACE_RESUME = 0x10B3AC0
# The bytes actually present at the top of _RMAssert in the shipped library, and
# the four bytes the stub re-creates before resuming, so that the resume state
# (sp and the r7 frame pointer) is bit-identical to a normal call.
#
# These are TWO 16-bit Thumb instructions, not one 32-bit one. That is easy to
# get wrong, so the values are cross-checked against each other below as
# halfwords rather than trusted as a byte blob:
#
#   0x10B3ABC  f0b5 = b5f0  push {r4, r5, r6, r7, lr}   ; sp -= 24
#   0x10B3ABE  03af = af03  add  r7, sp, #0xc           ; r7 = sp+0xc, FRAME PTR
#   0x10B3AC0  e92d 0700  push.w {r8, r9, r10}          ; first real body insn
#
# The second instruction is why the stub must re-create the prologue rather than
# merely restore registers: _RMAssert dereferences r7 at 0x10B3ADA
# (`add.w r1, r7, #8`) and 0x10B3AEC (`ldr r0, [r7, #8]`). 2.8.0.1+6 skipped
# this and crashed on the first assertion.
ASSERT_TRACE_PROLOGUE = bytes.fromhex("f0b503af")
ASSERT_TRACE_STUB_RECREATE_PROLOGUE = bytes.fromhex("f0b503af")
ASSERT_TRACE_BODY_INSTRUCTION = 0x10B3AC0
# Where the hook lands in the shipped library, and what the original prologue is
# expected to be, checked independently of the stub's own claims.
ASSERT_TRACE_PROLOGUE_OFFSET = 0x10B3ABC
# Every region this patcher already writes, so the new cave can be proven to be
# dead-and-free rather than assumed to be. RM_ASSERT_OFFSET itself is not listed:
# that is the hook site, and replacing the _RMAssert prologue with a branch is the
# whole point, so its expected bytes are checked separately.
ASSERT_TRACE_RESERVED = (
    (FUNCTION_OFFSET, FUNCTION_OFFSET + len(PATCH)),
    (LOAD_ANIM_OFFSET, LOAD_ANIM_OFFSET + len(LOAD_ANIM_BRANCH)),
    (LOAD_ANIM_CAVE_OFFSET, LOAD_ANIM_CAVE_OFFSET + 0x80),
    (TUTORIAL_ANIM_GUARD_OFFSET, TUTORIAL_ANIM_GUARD_OFFSET + len(TUTORIAL_ANIM_GUARD)),
    (TUTORIAL_ANIM_GUARD_ENTRY_OFFSET, TUTORIAL_ANIM_GUARD_ENTRY_OFFSET + 4),
    (RM_ASSERT_TERM_OFFSET, RM_ASSERT_TERM_OFFSET + RM_ASSERT_TERM_PATCH_LEN),
    (PARSE_ANIM_ASSERT_OFFSET, PARSE_ANIM_ASSERT_OFFSET + len(PARSE_ANIM_ASSERT_PATCH)),
    (GM_LEVELDB_PUT_ASSERT_OFFSET, GM_LEVELDB_PUT_ASSERT_OFFSET + len(GM_LEVELDB_PUT_ASSERT_PATCH)),
)


def thumb_branch(origin: int, target: int) -> bytes:
    """Encode a relocatable 16-bit Thumb B instruction."""
    delta = target - (origin + 4)
    if delta % 2:
        raise SystemExit(f"unaligned Thumb branch 0x{origin:x}->0x{target:x}")
    immediate = delta // 2
    if immediate < -(1 << 10) or immediate >= (1 << 10):
        raise SystemExit(f"Thumb branch is out of range 0x{origin:x}->0x{target:x}")
    return struct.pack("<H", 0xE000 | (immediate & 0x7FF))


def thumb_branch_w(origin: int, target: int) -> bytes:
    """Encode a relocatable 32-bit Thumb-2 B.W instruction."""
    delta = target - (origin + 4)
    if delta % 2 or delta < -(1 << 24) or delta >= (1 << 24):
        raise SystemExit(f"Thumb-2 branch is out of range 0x{origin:x}->0x{target:x}")
    value = delta & 0x01FFFFFF
    s = (value >> 24) & 1
    i1 = (value >> 23) & 1
    i2 = (value >> 22) & 1
    imm10 = (value >> 12) & 0x3FF
    imm11 = (value >> 1) & 0x7FF
    j1 = (~(i1 ^ s)) & 1
    j2 = (~(i2 ^ s)) & 1
    first = 0xF000 | (s << 10) | imm10
    second = 0x9000 | (j1 << 13) | (j2 << 11) | imm11
    return struct.pack("<HH", first, second)


def decode_thumb_branch_w(origin: int, encoded: bytes) -> int:
    """Decode a Thumb-2 B.W back to its absolute target.

    The patcher writes branches by hand, so every branch it writes is decoded
    again immediately afterwards and compared with the intended target. That
    turns "the encoder is probably right" into "the bytes provably mean this".
    """
    first, second = struct.unpack("<HH", encoded)
    s = (first >> 10) & 1
    imm10 = first & 0x3FF
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    imm11 = second & 0x7FF
    i1 = (~(j1 ^ s)) & 1
    i2 = (~(j2 ^ s)) & 1
    value = (
        (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
    )
    # The 25-bit immediate is signed on bit 24 (the S bit).
    if value & (1 << 24):
        value -= 1 << 25
    return (origin + 4) + value


def sign_extend(value: int, bits: int) -> int:
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def incoming_branch_targets(data: bytes, lo: int, hi: int) -> list[tuple[int, int]]:
    """Every direct branch in the whole library whose target lands in [lo, hi).

    Overwriting a region on the grounds that "the function's prologue is stubbed,
    so the body is dead" is precisely the reasoning that shipped the boot-breaking
    2.8.0.1+6: twelve branches inside CRMResourceMgr::MakeAnim2FromVideo targeted
    the chosen cave, and overwriting them broke the client at the lobby bootstrap.
    Proving a range is dead is easy to get wrong, so this gate can only REFUSE a
    build, never justify one. A range with no incoming branch is a candidate, not
    a proof: a taken address (vtable, function pointer, callback) would not show
    up here, and fallthrough into the range would not either.
    """
    hits: list[tuple[int, int]] = []
    for off in range(TEXT_START, TEXT_END - 1, 2):
        hw = struct.unpack_from("<H", data, off)[0]
        if hw & 0xF800 == 0xF000:
            if off + 3 < TEXT_END:
                hw2 = struct.unpack_from("<H", data, off + 2)[0]
                if hw2 & 0xD000 == 0xD000:
                    s = (hw >> 10) & 1
                    j1 = (hw2 >> 13) & 1
                    j2 = (hw2 >> 11) & 1
                    imm = (
                        (s << 24)
                        | (((~(j1 ^ s)) & 1) << 23)
                        | (((~(j2 ^ s)) & 1) << 22)
                        | ((hw & 0x3FF) << 12)
                        | ((hw2 & 0x7FF) << 1)
                    )
                    target = off + 4 + sign_extend(imm, 25)
                    if lo <= target < hi:
                        hits.append((off, target))
            continue
        if hw & 0xF000 == 0xD000 and hw & 0x0F00 != 0x0F00:
            target = off + 4 + sign_extend(((hw & 0xFF) << 1) & 0xFFF, 12)
            if lo <= target < hi:
                hits.append((off, target))
            continue
        if hw & 0xF800 == 0xE000:
            target = off + 4 + sign_extend((hw & 0x3FF) << 1, 12)
            if lo <= target < hi:
                hits.append((off, target))
    return hits


def load_assert_trace_blob() -> bytes:
    """Read the pre-verified tracer blob built by tools/build-assert-trace-blob.py."""
    if not ASSERT_TRACE_BLOB.exists():
        raise SystemExit(
            f"missing {ASSERT_TRACE_BLOB}. Build it first:\n"
            f"  python tools/build-assert-trace-blob.py"
        )
    blob = ASSERT_TRACE_BLOB.read_bytes()
    if not blob:
        raise SystemExit(f"{ASSERT_TRACE_BLOB} is empty")
    return blob


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--keep-asserts",
        action="store_true",
        help="Leave the native assertion machinery live (see module docstring).",
    )
    parser.add_argument(
        "--assert-log-continue",
        action="store_true",
        help="Keep the native assertion reporter but do not exit on failure.",
    )
    parser.add_argument(
        "--assert-arg-trace",
        action="store_true",
        help=(
            "Plant a freestanding Thumb stub at the entry of _RMAssert that prints the "
            "failing call site and the assertion's variadic words to stderr, then "
            "re-enters the untouched _RMAssert body. Requires --assert-log-continue or "
            "--keep-asserts, because the default build removes the assertion reporter."
        ),
    )
    args = parser.parse_args()
    if args.assert_arg_trace and not (args.assert_log_continue or args.keep_asserts):
        raise SystemExit(
            "--assert-arg-trace describes failing assertions, so it needs a build where "
            "the assertion reporter is still live: add --assert-log-continue (or "
            "--keep-asserts). The default build replaces _RMAssert with a no-op."
        )
    source = args.source.resolve()
    destination = args.destination.resolve()
    data = bytearray(source.read_bytes())
    actual = bytes(data[FUNCTION_OFFSET : FUNCTION_OFFSET + len(EXPECTED)])
    if actual != EXPECTED:
        raise SystemExit(
            f"unexpected bytes at 0x{FUNCTION_OFFSET:x}: {actual.hex()} "
            f"expected {EXPECTED.hex()}"
        )
    data[FUNCTION_OFFSET : FUNCTION_OFFSET + len(PATCH)] = PATCH

    # CRMResourceMgr4::LoadAnim2 has a normal Thumb prologue at this offset.
    # Redirect it into the unreachable tail of the patched video-animation
    # function. The cave recreates the prologue, preserves non-empty names,
    # and routes only null/empty/UI_MA_* names to a known loaded UI animation.
    actual_load_anim = bytes(data[LOAD_ANIM_OFFSET : LOAD_ANIM_OFFSET + 2])
    if actual_load_anim != bytes.fromhex("f0b5"):
        raise SystemExit(
            f"unexpected LoadAnim2 bytes at 0x{LOAD_ANIM_OFFSET:x}: "
            f"{actual_load_anim.hex()} expected f0b5"
        )
    cave = bytearray(LOAD_ANIM_CAVE)
    target = LOAD_ANIM_OFFSET + 0x28
    # Both addresses are reached relative to the relocated library: the
    # fallback string uses ADR, and the normal path uses a direct Thumb B.
    cave[LOAD_ANIM_CAVE_RESOURCE_ADR : LOAD_ANIM_CAVE_RESOURCE_ADR + 2] = bytes.fromhex("04a6")
    cave[LOAD_ANIM_CAVE_BRANCH : LOAD_ANIM_CAVE_BRANCH + 2] = thumb_branch(
        LOAD_ANIM_CAVE_OFFSET + LOAD_ANIM_CAVE_BRANCH, target
    )
    cave[LOAD_ANIM_CAVE_BRANCH + 2 : LOAD_ANIM_CAVE_RESOURCE_TEXT] = b"\x00\xbf" * 6
    cave.extend(LOAD_ANIM_FALLBACK)
    data[LOAD_ANIM_CAVE_OFFSET : LOAD_ANIM_CAVE_OFFSET + len(cave)] = cave
    data[LOAD_ANIM_OFFSET : LOAD_ANIM_OFFSET + len(LOAD_ANIM_BRANCH)] = LOAD_ANIM_BRANCH

    # Assertion handling. The three patches below are what stop a failing native
    # assertion from being reported: RMAssert is stubbed to return 0, and the two
    # call-site conditionals are inverted so the branch that would raise is never
    # taken. That makes a broken replica response indistinguishable from a hang,
    # because the client steps over the failure and then waits for something that
    # never happens. --assert-log-continue keeps the reporter and removes only
    # the exit; --keep-asserts leaves all three fully live.
    actual_parser_assert = bytes(
        data[PARSE_ANIM_ASSERT_OFFSET : PARSE_ANIM_ASSERT_OFFSET + len(PARSE_ANIM_ASSERT_EXPECTED)]
    )
    if actual_parser_assert != PARSE_ANIM_ASSERT_EXPECTED:
        raise SystemExit(
            f"unexpected ParseRes2 animation assertion bytes at 0x{PARSE_ANIM_ASSERT_OFFSET:x}: "
            f"{actual_parser_assert.hex()} expected {PARSE_ANIM_ASSERT_EXPECTED.hex()}"
        )
    if not args.keep_asserts:
        data[PARSE_ANIM_ASSERT_OFFSET : PARSE_ANIM_ASSERT_OFFSET + len(PARSE_ANIM_ASSERT_PATCH)] = (
            PARSE_ANIM_ASSERT_PATCH
        )

    actual_leveldb_assert = bytes(
        data[GM_LEVELDB_PUT_ASSERT_OFFSET : GM_LEVELDB_PUT_ASSERT_OFFSET + len(GM_LEVELDB_PUT_ASSERT_EXPECTED)]
    )
    if actual_leveldb_assert != GM_LEVELDB_PUT_ASSERT_EXPECTED:
        raise SystemExit(
            f"unexpected GMLevelDB Put assertion bytes at 0x{GM_LEVELDB_PUT_ASSERT_OFFSET:x}: "
            f"{actual_leveldb_assert.hex()} expected {GM_LEVELDB_PUT_ASSERT_EXPECTED.hex()}"
        )
    if not args.keep_asserts:
        data[GM_LEVELDB_PUT_ASSERT_OFFSET : GM_LEVELDB_PUT_ASSERT_OFFSET + len(GM_LEVELDB_PUT_ASSERT_PATCH)] = (
            GM_LEVELDB_PUT_ASSERT_PATCH
        )

    # Keep the instrumented client alive long enough to capture the next
    # request when a native assertion describes incomplete replica data. This
    # is intentionally an APK-only diagnostic patch, not a server behavior.
    actual_rm_assert = bytes(data[RM_ASSERT_OFFSET : RM_ASSERT_OFFSET + len(RM_ASSERT_EXPECTED)])
    if actual_rm_assert != RM_ASSERT_EXPECTED:
        raise SystemExit(
            f"unexpected RMAssert bytes at 0x{RM_ASSERT_OFFSET:x}: "
            f"{actual_rm_assert.hex()} expected {RM_ASSERT_EXPECTED.hex()}"
        )
    if args.keep_asserts:
        pass  # leave the real reporter and its exit in place
    elif args.assert_log_continue:
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
        patch += b"\x00\xbf" * ((RM_ASSERT_TERM_PATCH_LEN - len(patch)) // 2)
        data[RM_ASSERT_TERM_OFFSET : RM_ASSERT_TERM_OFFSET + len(patch)] = patch
    else:
        data[RM_ASSERT_OFFSET : RM_ASSERT_OFFSET + len(RM_ASSERT_PATCH)] = RM_ASSERT_PATCH

    # --- optional: plant the assertion-argument tracer ------------------------
    trace_note = ""
    if args.assert_arg_trace:
        blob = load_assert_trace_blob()
        hook_span = (ASSERT_TRACE_HOOK_OFFSET, ASSERT_TRACE_HOOK_OFFSET + 4)
        cave_span = (ASSERT_TRACE_CAVE_OFFSET, ASSERT_TRACE_CAVE_OFFSET + len(blob))
        if not (TEXT_START <= ASSERT_TRACE_HOOK_OFFSET and TEXT_START <= ASSERT_TRACE_CAVE_OFFSET):
            raise SystemExit("assertion tracer is placed outside .text")

        # --- gate: the hook site must really hold the prologue we replace -----
        prologue = bytes(
            data[ASSERT_TRACE_PROLOGUE_OFFSET : ASSERT_TRACE_PROLOGUE_OFFSET + len(ASSERT_TRACE_PROLOGUE)]
        )
        if prologue != ASSERT_TRACE_PROLOGUE:
            raise SystemExit(
                f"_RMAssert prologue at 0x{ASSERT_TRACE_PROLOGUE_OFFSET:x} is {prologue.hex()}, "
                f"expected {ASSERT_TRACE_PROLOGUE.hex()}; the stub's prologue re-creation "
                f"assumes exactly these bytes"
            )
        if ASSERT_TRACE_PROLOGUE != ASSERT_TRACE_STUB_RECREATE_PROLOGUE:
            raise SystemExit(
                f"stub re-creates {ASSERT_TRACE_STUB_RECREATE_PROLOGUE.hex()} but the hook "
                f"replaces {ASSERT_TRACE_PROLOGUE.hex()}; the resume state would differ "
                f"from a normal call"
            )
        if ASSERT_TRACE_HOOK_EXPECTED[:4] != ASSERT_TRACE_PROLOGUE:
            raise SystemExit(
                f"prologue {ASSERT_TRACE_PROLOGUE.hex()} does not match the first four bytes "
                f"of the hook site expectation {ASSERT_TRACE_HOOK_EXPECTED.hex()}"
            )
        # The stub resumes at the first real body instruction. Check that the
        # instruction really is one, rather than assuming the prologue is four
        # bytes: 2.8.0.1+6 branched into the middle of the prologue for exactly
        # this reason. Read as two 16-bit Thumb halfwords, low halfword first.
        lo_hw, hi_hw = struct.unpack_from("<HH", data, ASSERT_TRACE_BODY_INSTRUCTION)
        if (lo_hw, hi_hw) != (0xE92D, 0x0700):
            raise SystemExit(
                f"expected `push.w {{r8, r9, r10}}` (e92d 0700) at the resume address "
                f"0x{ASSERT_TRACE_BODY_INSTRUCTION:x}, found {lo_hw:04x} {hi_hw:04x}; the "
                f"prologue is not the four bytes this patcher assumes"
            )

        # --- gate: the cave must be genuinely unbranched ----------------------
        # This is the gate that would have prevented the boot-breaking release.
        # It can only refuse; passing it is necessary but not sufficient, because
        # a taken address or a fallthrough into the range would not be detected.
        reachers = incoming_branch_targets(bytes(data), *cave_span)
        if reachers:
            listed = ", ".join(f"0x{origin:08x}->0x{target:08x}" for origin, target in reachers[:8])
            raise SystemExit(
                f"assertion tracer cave 0x{cave_span[0]:x}-0x{cave_span[1]:x} is targeted by "
                f"{len(reachers)} direct branch(es) in the live library ({listed}"
                f"{', ...' if len(reachers) > 8 else ''}). Overwriting it corrupts a "
                f"function that is still executed. Pick a cave that no branch targets."
            )
        for reserved_start, reserved_end in ASSERT_TRACE_RESERVED:
            if hook_span[0] < reserved_end and reserved_start < hook_span[1]:
                raise SystemExit(
                    f"assertion tracer hook 0x{hook_span[0]:x} overlaps an existing patch "
                    f"at 0x{reserved_start:x}"
                )
            if cave_span[0] < reserved_end and reserved_start < cave_span[1]:
                raise SystemExit(
                    f"assertion tracer cave 0x{cave_span[0]:x}-0x{cave_span[1]:x} overlaps an "
                    f"existing patch at 0x{reserved_start:x}-0x{reserved_end:x}"
                )
        stub = bytearray(blob)
        sentinels = [
            i
            for i in range(len(stub) - len(ASSERT_TRACE_SENTINEL) + 1)
            if stub[i : i + len(ASSERT_TRACE_SENTINEL)] == ASSERT_TRACE_SENTINEL
        ]
        if len(sentinels) != 1:
            raise SystemExit(
                f"assertion tracer blob must hold exactly one {ASSERT_TRACE_SENTINEL.hex()} "
                f"sentinel, found {len(sentinels)}"
            )
        slot = sentinels[0] + len(ASSERT_TRACE_SENTINEL)
        if slot + 4 > len(stub):
            raise SystemExit("assertion tracer sentinel has no branch slot after it")
        origin = ASSERT_TRACE_CAVE_OFFSET + slot
        resume = thumb_branch_w(origin, ASSERT_TRACE_RESUME)
        # The assembler encodes `b.w .` as a branch to the instruction itself.
        if decode_thumb_branch_w(origin, bytes(stub[slot : slot + 4])) != origin:
            raise SystemExit(
                "assertion tracer branch slot is not the expected placeholder self-branch, "
                "so the blob does not match instrumentation/native/blustone-assert-trace.S"
            )
        if decode_thumb_branch_w(origin, resume) != ASSERT_TRACE_RESUME:
            raise SystemExit("rewritten assertion tracer resume branch does not decode back")
        stub[slot : slot + 4] = resume
        if bytes(stub[slot : slot + 4]) != resume:
            raise SystemExit("rewritten assertion tracer resume branch did not land as written")
        entry = thumb_branch_w(ASSERT_TRACE_HOOK_OFFSET, ASSERT_TRACE_CAVE_OFFSET)
        if decode_thumb_branch_w(ASSERT_TRACE_HOOK_OFFSET, entry) != ASSERT_TRACE_CAVE_OFFSET:
            raise SystemExit("assertion tracer entry branch does not decode back")
        if len(entry) != 4:
            raise SystemExit(f"assertion tracer entry must be 4 bytes, got {len(entry)}")
        cave_actual = bytes(data[cave_span[0] : cave_span[1]])
        data[cave_span[0] : cave_span[1]] = stub
        data[ASSERT_TRACE_HOOK_OFFSET : ASSERT_TRACE_HOOK_OFFSET + 4] = entry
        # Re-read the finished image and prove it, rather than trusting the writes.
        if bytes(data[cave_span[0] : cave_span[1]]) != bytes(stub):
            raise SystemExit("assertion tracer cave did not land in the image as written")
        if bytes(data[hook_span[0] : hook_span[1]]) != entry:
            raise SystemExit("assertion tracer hook did not land in the image as written")
        if cave_actual == bytes(stub):
            raise SystemExit(
                "assertion tracer cave was already byte-identical, so the write is unproven"
            )
        trace_note = (
            f" assert_arg_trace=0x{ASSERT_TRACE_HOOK_OFFSET:x}->0x{ASSERT_TRACE_CAVE_OFFSET:x} "
            f"size=0x{len(stub):x} resume=0x{ASSERT_TRACE_RESUME:x}"
        )

    actual_tutorial = bytes(
        data[TUTORIAL_ANIM_GUARD_ENTRY_OFFSET : TUTORIAL_ANIM_GUARD_ENTRY_OFFSET + len(TUTORIAL_ANIM_GUARD_ENTRY_EXPECTED)]
    )
    if actual_tutorial != TUTORIAL_ANIM_GUARD_ENTRY_EXPECTED:
        raise SystemExit(
            f"unexpected tutorial animation guard bytes at 0x{TUTORIAL_ANIM_GUARD_ENTRY_OFFSET:x}: "
            f"{actual_tutorial.hex()} expected {TUTORIAL_ANIM_GUARD_ENTRY_EXPECTED.hex()}"
        )
    guard = bytearray(TUTORIAL_ANIM_GUARD)
    guard[0x0C:0x10] = thumb_branch_w(
        TUTORIAL_ANIM_GUARD_OFFSET + 0x0C, TUTORIAL_ANIM_GUARD_NONNULL_RETURN
    )
    guard[0x10:0x14] = thumb_branch_w(
        TUTORIAL_ANIM_GUARD_OFFSET + 0x10, TUTORIAL_ANIM_GUARD_NULL_RETURN
    )
    data[TUTORIAL_ANIM_GUARD_OFFSET : TUTORIAL_ANIM_GUARD_OFFSET + len(guard)] = guard
    data[TUTORIAL_ANIM_GUARD_ENTRY_OFFSET : TUTORIAL_ANIM_GUARD_ENTRY_OFFSET + 4] = thumb_branch_w(
        TUTORIAL_ANIM_GUARD_ENTRY_OFFSET, TUTORIAL_ANIM_GUARD_OFFSET
    )

    actual_host = bytes(data[BOOTSTRAP_HOST_OFFSET : BOOTSTRAP_HOST_OFFSET + len(BOOTSTRAP_HOST)])
    if actual_host != BOOTSTRAP_HOST:
        raise SystemExit(
            f"unexpected bootstrap host at 0x{BOOTSTRAP_HOST_OFFSET:x}: "
            f"{actual_host!r} expected {BOOTSTRAP_HOST!r}"
        )
    if len(BOOTSTRAP_TARGET) > len(BOOTSTRAP_HOST):
        raise SystemExit("bootstrap target does not fit in the original host literal")
    data[BOOTSTRAP_HOST_OFFSET : BOOTSTRAP_HOST_OFFSET + len(BOOTSTRAP_HOST)] = (
        BOOTSTRAP_TARGET + b"\x00" * (len(BOOTSTRAP_HOST) - len(BOOTSTRAP_TARGET))
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    print(
        f"patched=0x{FUNCTION_OFFSET:x} bytes={PATCH.hex()} "
        f"empty_anim=0x{LOAD_ANIM_OFFSET:x}->MN_CLOUD "
        f"parser_assert=0x{PARSE_ANIM_ASSERT_OFFSET:x}->nonfatal "
        f"leveldb_put_assert=0x{GM_LEVELDB_PUT_ASSERT_OFFSET:x}->nonfatal "
        f"rm_assert=0x{RM_ASSERT_OFFSET:x}->nonfatal "
        f"tutorial_anim_guard=0x{TUTORIAL_ANIM_GUARD_ENTRY_OFFSET:x}->0x{TUTORIAL_ANIM_GUARD_OFFSET:x} "
        f"bootstrap=0x{BOOTSTRAP_HOST_OFFSET:x} target={BOOTSTRAP_TARGET.decode()} "
        f"source={source} destination={destination}{trace_note}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
