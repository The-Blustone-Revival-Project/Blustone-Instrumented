#!/usr/bin/env python3
"""Verify every native patch in an instrumented libnative_core.so, byte for byte.

This is a HARD GATE. `tools/build-instrumented-apk.py` runs it immediately after
the patcher, so a build can never ship with a patch silently lost, misplaced, or
overwritten by another patch. It exits non-zero on the first mismatch.

It also classifies the `_RMAssert` entry mode, because that is the single most
consequential byte range in the library: it decides whether a failing assertion is
reported or stepped over silently, and (as 2.8.0.1+6 proved) whether the client
survives it at all.

Run standalone with `--assert-trace` to additionally check the assertion-argument
tracer hook and that its stub re-creates the _RMAssert prologue.
"""

from __future__ import annotations

import argparse
import struct
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIBRARY = ROOT / "local" / "legacy-analysis" / "patched" / "libnative_core-ui-ma-bypass.so"
ORIGINAL_LIBRARY = ROOT / "local" / "legacy-analysis" / "extracted" / "lib" / "armeabi-v7a" / "libnative_core.so"

# Every patch is expected to hold unless --keep-asserts asked for the two
# call-site assertion conditionals to stay live. So each entry carries the
# expected bytes for the normal case and, where it differs, for keep-asserts.
# (offset, expected normally, expected with --keep-asserts, description)
PATCHES: tuple[tuple[int, bytes, bytes, str], ...] = (
    (
        0x00784CFE,
        bytes.fromhex("0120"),
        bytes.fromhex("0020"),
        "GMLevelDB Put assert -> non-fatal",
    ),
    (
        0x0107FA10,
        bytes.fromhex("0120"),
        bytes.fromhex("0020"),
        "ParseRes2 animation assert -> non-fatal",
    ),
    (
        0x010DA690,
        bytes.fromhex("0020704700bf"),
        bytes.fromhex("0020704700bf"),
        "MakeAnim2FromVideo -> no-op (UI_MA_L1 BlueStacks fault)",
    ),
    (
        0x010DA4E8,
        bytes.fromhex("d5e0"),
        bytes.fromhex("d5e0"),
        "LoadAnim2 -> MN_CLOUD fallback cave",
    ),
    (
        0x00EECC00,
        bytes.fromhex("edf17ebd"),
        bytes.fromhex("edf17ebd"),
        "tutorial finger-animation guard entry -> cave",
    ),
    (
        0x01D5EC56,
        b"10.0.2.2:8080",
        b"10.0.2.2:8080",
        "bootstrap host literal -> 10.0.2.2:8080",
    ),
)

# Regions the patcher legitimately rewrites wholesale; used to keep the cave
# reachability scan honest about what is already patched.
PATCHER_RESERVED: tuple[tuple[int, int], ...] = (
    (0x00784CFE, 0x00784D00),
    (0x0107FA10, 0x0107FA12),
    (0x010DA4E8, 0x010DA4EA),
    (0x010DA690, 0x010DA6E0),
    (0x010DA700, 0x010DA718),
    (0x00EECC00, 0x00EECC04),
    (0x010B3ABC, 0x010B3AC4),
    (0x010B3B5C, 0x010B3B60),
)

TEXT_START = 0x00612CC0
TEXT_END = 0x01BD46F8

RM_ASSERT_OFFSET = 0x010B3ABC
RM_ASSERT_STUB = bytes.fromhex("0020704700bf")          # default build: no-op
RM_ASSERT_PROLOGUE = bytes.fromhex("f0b503af")          # live reporter
# The resume instruction at 0x10B3AC0, as raw file bytes: 2d e9 00 07, which is
# `push.w {r8, r9, r10}`.
#
# Do not be misled by the disassembly: objdump PRINTS this as "e92d 0700" because
# it renders each 16-bit halfword byte-swapped. The same trap applies to the
# prologue, which the file holds as f0 b5 03 af and objdump prints as "b5f0 af03".
# Reading these four bytes as one little-endian 32-bit word gives 0x07002DE9,
# which decodes to nothing - and misreading them that way is what produced the
# wrong resume address in 2.8.0.1+6.
RM_ASSERT_BODY_HALFWORDS = (0xE92D, 0x0700)
RM_ASSERT_BODY_INSTRUCTION = bytes.fromhex("2de90007")   # push.w {r8,r9,r10}
RM_ASSERT_TERM_STUB_LOGCONT = bytes.fromhex("f6e700bf")  # b.w epilogue
RM_ASSERT_TERM_BL_EXIT = bytes.fromhex("5df5becf")       # blx -> exit
ASSERT_TRACE_HOOK = bytes.fromhex("26f030be")            # b.w to the cave


def sign_extend(value: int, bits: int) -> int:
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def incoming_branch_targets(data: bytes, lo: int, hi: int) -> list[tuple[int, int]]:
    """Direct branches anywhere in .text whose target lands in [lo, hi).

    The 2.8.0.1+6 release chose a "dead" code cave inside
    CRMResourceMgr::MakeAnim2FromVideo and boot-broke the client, because twelve
    branches inside that function actually targeted the cave. This scan is how
    that must be caught before a build, never after.
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


def classify_rm_assert(data: bytes) -> tuple[str, str]:
    """Return (mode, human description) for the _RMAssert entry and terminator."""
    entry = bytes(data[RM_ASSERT_OFFSET : RM_ASSERT_OFFSET + 4])
    term = bytes(data[0x010B3B5C : 0x010B3B60])
    if entry == ASSERT_TRACE_HOOK:
        mode = "traced"
        note = "branches to the assertion-argument tracer stub"
    elif entry == RM_ASSERT_STUB[:4]:
        mode = "silenced"
        note = "stubbed to a no-op: a failing assertion is stepped over silently"
    elif entry == RM_ASSERT_PROLOGUE:
        mode = "log-continue" if term == RM_ASSERT_TERM_STUB_LOGCONT else "live"
        note = (
            "reporter live, terminator branches to the epilogue: process survives"
            if mode == "log-continue"
            else "reporter and exit both live: process dies on assertion"
        )
    else:
        mode = "unknown"
        note = f"unrecognised entry bytes {entry.hex()}"
    if term not in (RM_ASSERT_TERM_STUB_LOGCONT, RM_ASSERT_TERM_BL_EXIT):
        note += f" (terminator {term.hex()} is neither the expected blx nor the epilogue branch)"
    return mode, note


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY)
    parser.add_argument("--search-callback-guard", action="store_true", help="Require the scoped Search callback lifetime/null guards")
    parser.add_argument("--empty-partner-guide", action="store_true", help="Require fresh empty-helper tutorial deferral")
    parser.add_argument(
        "--assert-trace",
        action="store_true",
        help="also require the assertion-argument tracer hook and a safe cave",
    )
    parser.add_argument(
        "--require-live-asserts",
        action="store_true",
        help="fail if _RMAssert would be stubbed out, i.e. the build asked to keep the reporter",
    )
    args = parser.parse_args()

    if not args.library.exists():
        print(f"FAIL: library not found: {args.library}", file=sys.stderr)
        return 1
    data = args.library.read_bytes()
    failures: list[str] = []
    if args.empty_partner_guide:
        for address,size,digest in ((0xe1ffe4,12,"a8e20e2f03018df83b70fe20b59aec0e53e0fcba78802c051eee3072f0864087"),
            (0x210d404,204,"a0cb7af0799227edfd19713c4052215a30cfc760083fe9f264e196cda4a20b35")):
            if hashlib.sha256(data[address:address+size]).hexdigest()!=digest:
                failures.append(f"Empty Partner guide code {address:x} mismatch")
        print("  Fresh empty-helper Partner guide deferral checked")
    if args.search_callback_guard:
        for origin, target in ((0xe27420,0x612c9c),(0xe27456,0x612ca8),(0xe2749a,0x612cb4)):
            if decode_b_w(origin, data[origin:origin+4]) != target:
                failures.append(f"Search callback hook {origin:x} missing")
        for address,size,digest in ((0x612c9c,36,"ebe80b3c62f7215e83a659c3266c749a4e33c92bdb12d55a23b00ef47a16b2e3"),
            (0x210d380,132,"02abc826ef31bd002ffb506adcfffdce39b82fff72fecddcfd312f8a7be128f8")):
            if hashlib.sha256(data[address:address+size]).hexdigest()!=digest:
                failures.append(f"Search callback code {address:x} mismatch")
        print("  Search callback scoped guard checked (scene identity, parent/child null cleanup)")

    # Infer the intended assertion mode from the library itself, so every build
    # variant is checked against what it was actually asked to produce.
    mode, _ = classify_rm_assert(data)
    keep_asserts = mode == "live"

    print(f"verifying {args.library}")
    print(f"  assertion mode: {mode}" + (" (--keep-asserts semantics)" if keep_asserts else ""))
    for offset, expected_normal, expected_keep, description in PATCHES:
        expected = expected_keep if keep_asserts else expected_normal
        actual = bytes(data[offset : offset + len(expected)])
        if actual == expected:
            print(f"  OK  0x{offset:08X}  {description}: {actual.hex()}")
        else:
            print(f"  BAD 0x{offset:08X}  {description}: got {actual.hex()} want {expected.hex()}")
            failures.append(f"0x{offset:08X} {description}: got {actual.hex()} want {expected.hex()}")

    entry = bytes(data[RM_ASSERT_OFFSET : RM_ASSERT_OFFSET + 4])
    term = bytes(data[0x010B3B5C : 0x010B3B60])
    _, note = classify_rm_assert(data)
    print(f"  _RMAssert entry 0x{RM_ASSERT_OFFSET:08X}: {mode} ({entry.hex()}) - {note}")
    print(f"  _RMAssert term  0x010B3B5C: {term.hex()}")
    if mode == "unknown":
        failures.append(f"_RMAssert entry {entry.hex()} is unrecognised")
    elif mode == "silenced":
        # Legitimate for the default build, but it means a bad replica response is
        # indistinguishable from a hang, so say so loudly.
        print(
            "  WARNING _RMAssert is stubbed out: a failing assertion is stepped over "
            "silently and cannot be observed. Use --assert-log-continue if a failing "
            "assertion needs to be reported.",
            file=sys.stderr,
        )
    if args.require_live_asserts and mode not in {"live", "log-continue", "traced"}:
        failures.append(
            f"--assert-log-continue was requested but _RMAssert mode is {mode!r}: the "
            f"assertion reporter would be removed"
        )
    if mode == "traced" and not args.assert_trace:
        failures.append(
            "_RMAssert is traced but --assert-trace was not requested; pass it to check the cave"
        )
    if args.assert_trace and mode != "traced":
        failures.append(f"--assert-trace requested but _RMAssert mode is {mode!r}, not traced")

    if args.assert_trace and mode == "traced":
        # The resume address must be the first real body instruction. 2.8.0.1+6
        # branched into the middle of the prologue on a misreading of four bytes
        # as one 32-bit instruction.
        resume = 0x010B3AC0
        body = bytes(data[resume : resume + 4])
        halfwords = struct.unpack("<HH", body) if len(body) == 4 else (0, 0)
        if halfwords != RM_ASSERT_BODY_HALFWORDS:
            failures.append(
                f"resume instruction at 0x{resume:X} is {body.hex()} "
                f"(halfwords {halfwords[0]:04x} {halfwords[1]:04x}), expected halfwords "
                f"{RM_ASSERT_BODY_HALFWORDS[0]:04x} {RM_ASSERT_BODY_HALFWORDS[1]:04x} = "
                f"push.w {{r8, r9, r10}}"
            )
        else:
            print(f"  OK  0x{resume:08X}  resume instruction is push.w {{r8, r9, r10}}")

        # Locate the cave from the stub's own branch, then check nothing branches
        # into it. Without a real cave this tracer cannot be built.
        target = decode_b_w(RM_ASSERT_OFFSET, entry)
        if target is None:
            failures.append(
                f"_RMAssert entry {entry.hex()} is not a Thumb-2 B.W, so the tracer "
                f"destination cannot be located"
            )
            target = -1
        else:
            print(f"  tracer branch target 0x{target:08X}")
        if target < 0:
            print()
            for failure in failures:
                print(f"FAIL: {failure}", file=sys.stderr)
            print(f"{len(failures)} problem(s); the build must not ship", file=sys.stderr)
            return 1
        blob = (ROOT / "local" / "legacy-analysis" / "patched" / "assert-trace-blob.bin")
        if not blob.exists():
            failures.append(f"tracer hook present but {blob} is missing; cannot size the cave")
        else:
            size = len(blob.read_bytes())
            reachers = incoming_branch_targets(data, target, target + size)
            if reachers:
                shown = ", ".join(f"0x{o:08x}->0x{t:08x}" for o, t in reachers[:6])
                failures.append(
                    f"cave 0x{target:X}-0x{target + size:X} is targeted by {len(reachers)} "
                    f"direct branch(es) ({shown}); overwriting it corrupts live code. "
                    f"This is the bug that boot-broke 2.8.0.1+6."
                )
            else:
                print(f"  OK  0x{target:08X}  cave has no incoming direct branches")

    print()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        print(f"{len(failures)} problem(s); the build must not ship", file=sys.stderr)
        return 1
    print("all expected patches present")
    return 0


def decode_b_w(origin: int, encoded: bytes) -> int | None:
    """Decode a 32-bit Thumb-2 B.W. Returns None if the bytes are not one.

    Returning None rather than a sentinel keeps the caller honest: a garbage
    decode must fail the gate, not silently produce a nonsense cave address.
    """
    first, second = struct.unpack("<HH", encoded)
    # B.W (T3): first 0b11110 S imm10, second 0b10 J1 1 J2 imm11
    if (first & 0xF800) != 0xF000:
        return None
    if (second & 0xC000) != 0x8000 or (second & 0x1000) != 0x1000:
        return None
    s = (first >> 10) & 1
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    imm = (
        (s << 24)
        | (((~(j1 ^ s)) & 1) << 23)
        | (((~(j2 ^ s)) & 1) << 22)
        | ((first & 0x3FF) << 12)
        | ((second & 0x7FF) << 1)
    )
    return (origin + 4) + sign_extend(imm, 25)


if __name__ == "__main__":
    raise SystemExit(main())
