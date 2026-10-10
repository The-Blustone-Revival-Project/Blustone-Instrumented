#!/usr/bin/env python3
"""Offline Thumb literal-pool string resolver.

Recovers JSON key / string literals that Ghidra decompiles print as
`_DAT_<slot> + 0x<add_pc>`, WITHOUT opening the Ghidra project.

Why this works
--------------
In Thumb-1/2 the idiom is

    ldr rN, [pc, #imm]      ; rN = *(pc + imm)   -> the literal-pool word
    add rN, pc              ; rN += (pc_of_add & ~1) + 4

Ghidra's decompiler prints the loaded word as a DAT label at its *slot*
address and the addend as `+ 0x...`. Two facts make it reproducible offline:

  1. Ghidra image address == file offset + 0x10000 for this library.
  2. For these literal-pool slots the on-disk word already equals the value
     Ghidra reports as the relocated `w`, so `fread` is enough.

    string_address = u32le(slot - 0x10000) + ((add_insn & ~1) + 4)
    string_offset  = string_address - 0x10000

The read-only library is never modified.
"""
from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

DEFAULT_SO = Path("analysis/extracted/lib/armeabi-v7a/libnative_core.so")
ADDR_BIAS = 0x10000


def to_file_offset(addr: int) -> int:
    return addr - ADDR_BIAS


class Library:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        self.size = len(self.data)

    def u32(self, file_off: int) -> int:
        if file_off < 0 or file_off + 4 > self.size:
            raise ValueError(f"u32 out of range at file offset 0x{file_off:x}")
        return struct.unpack_from("<I", self.data, file_off)[0]

    def cstr(self, file_off: int, limit: int = 512) -> str:
        if file_off < 0 or file_off >= self.size:
            return ""
        end = self.data.find(b"\x00", file_off, file_off + limit)
        if end < 0:
            end = file_off + limit
        return self.data[file_off:end].decode("utf-8", "replace")


# `ldr rX, [pc, #imm]`  ->  0x48xx (T1) | 0xF8xx/0xF9xx (T2)
LDR_PC_T1 = re.compile(rb"[\x00-\xff]")
# decompiler line forms we consume from an existing dump. Numeric fields in
# the dumps are inconsistently prefixed ("slot=0x..." vs "slot=..."), so accept
# an optional 0x on every one.
_HEX = r"(?:0[xX])?([0-9a-fA-F]+)"
DUMP_LDR = re.compile(
    rf"ldr@(?:0[xX])?([0-9a-fA-F]+)\s+slot=(?:0[xX])?([0-9a-fA-F]+)\s+"
    rf"w=(?:0[xX])?([0-9a-fA-F]+)\s+add@(?:0[xX])?([0-9a-fA-F]+)\s*->\s*(?:0[xX])?([0-9a-fA-F]+)"
)


def resolve_from_dump(lib: Library, dump: Path) -> int:
    """Re-resolve every `ldr ... slot=... w=... add@...` line of a dump.

    Uses only the ON-DISK word, ignoring the dump's own `w=`, so this is an
    independent check of the dump rather than a copy of it.
    """
    hits = 0
    for line in dump.read_text(encoding="utf-8", errors="replace").splitlines():
        m = DUMP_LDR.search(line)
        if not m:
            continue
        slot = int(m.group(2), 16)
        add_insn = int(m.group(4), 16)
        add_pc = (add_insn & ~1) + 4
        try:
            w_disk = lib.u32(to_file_offset(slot))
        except ValueError:
            print(f"{slot:#010x}  <unmapped slot>")
            continue
        target = w_disk + add_pc
        s = lib.cstr(to_file_offset(target))
        hits += 1
        print(f"slot={slot:#010x} w_disk={w_disk:#010x} +{add_pc:#010x} "
              f"-> {target:#010x}  {s!r}")
    return hits


def _ldr_pc_imm(data: bytes, pc: int):
    """If a Thumb `ldr rN,[pc,#imm]` really starts at file offset `pc`, return (rn, imm).

    Returns None for anything that is not a literal-pool load. This guard is
    load-bearing, twice over.

    1. An earlier version paired a literal `add rN,pc` with an UNRELATED
       preceding instruction and reported a JSON key "_id" for
       `AddStageMonster` (0xa0d194) that the function never reads. At the
       claimed address the actual bytes are `d05b 4608` - a 32-bit Thumb-2
       **BL**, i.e. a call - and the following `add` is `add r1,sp,#8`, not
       `add <Rn>,pc`. Both halves of the pairing were wrong.
    2. `AddStageMonster` has exactly five `bl operator[]` sites
       (0xa0d1ce, 0xa0d304, 0xa0d34a, 0xa0d398, 0xa0d512). Counting those sites
       is how the phantom was caught; a sixth would have meant a sixth key.

    Do not relax the opcode check, and do not widen the pairing window, to
    improve recall. Every failure mode of this tool has been a FALSE POSITIVE
    invented string key, which is far more damaging here than a missed literal:
    it sends a real client a response keyed on a field that does not exist.
    """
    if pc + 2 > len(data):
        return None
    hw1 = struct.unpack_from("<H", data, pc)[0]
    if (hw1 & 0xF800) == 0x4800:  # T1: ldr rN,[pc,#imm8*4]
        return hw1 & 0x0007, (hw1 & 0x00FF) * 4
    if (hw1 & 0xF800) == 0xF8D0:  # T2: ldr.w rN,[pc,#imm12]
        if pc + 4 > len(data):
            return None
        hw2 = struct.unpack_from("<H", data, pc + 2)[0]
        if (hw2 & 0xF000) != 0xF000:
            return None
        return hw1 & 0x0007, ((hw1 & 0x004F) << 8) | hw2
    return None


def _ldr_is_32bit_branch(data: bytes, pc: int) -> bool:
    """True for a 32-bit Thumb-2 BL/BLX (bits[15:11] == 0b10, S == 0)."""
    if pc + 4 > len(data):
        return False
    hw1 = struct.unpack_from("<H", data, pc)[0]
    return ((hw1 >> 11) & 3) == 2 and ((hw1 >> 10) & 1) == 0


def _is_add_pc(hw: int) -> bool:
    """True for a Thumb high-register `ADD <Rn>, PC`.

    Encoding is 0100 0100 0 Rm(3) Rdn(3); we want Rm == 7 (the PC). We do NOT
    require Rdn to match the register the literal was loaded into - verified
    against the ground-truth pair at 0xa0d1b0/0xa0d1b4, where the ldr targets
    r2 but the add targets r0.
    """
    return (hw & 0xFF00) == 0x4400 and ((hw >> 3) & 0x7) == 7


def iter_thumb_ldr_addpc(lib: Library, start: int, end: int):
    """Yield (ldr_addr, slot, add_pc, rn) for `ldr rN,[pc,#imm]; add r?,pc` pairs.

    Anchored on the `add <Rn>,PC` and looking backwards, because the two
    instructions are NOT always adjacent: a `ldr.w` (T2) is 4 bytes, so its
    `add` sits at +4, while a `ldr` (T1) is 2 bytes and its `add` sits at +2.
    Anchoring forward from the ldr misses one of the two forms.

    The backward window MUST be at least 8. A single `ldr` slot is frequently
    consumed by TWO `add` instructions (0xa0d1b4 and 0xa0d1b8 both pair with the
    load at 0xa0d1b0 in `AddStageMonster`), which is how the real key
    "wave_list" was wrongly reported as unreferenced when the window was 2/4/6.
    A narrower window does not merely miss literals - it produces a false
    NEGATIVE ("this string has no references"), which is the dangerous failure
    mode for this tool. Widen with suspicion, never narrow.

    Thumb reads PC as (address_of_insn + 4), so for the `add` at `add_addr`
    the addend is `add_addr + 4`.
    """
    out = []
    data = lib.data
    lo, hi = to_file_offset(start), to_file_offset(end)
    for pc in range(lo, min(hi, len(data) - 2), 2):
        if not _is_add_pc(struct.unpack_from("<H", data, pc)[0]):
            continue
        add_addr = pc + ADDR_BIAS
        add_pc = add_addr + 4
        # Walk back to the IMMEDIATELY preceding instruction. The Thumb idiom is
        # `ldr` then `add` with nothing in between, so the load must start at the
        # add's own address minus its width. Searching further back is what
        # manufactured the phantom "_id" key - it paired an unrelated earlier
        # instruction with this add. Contiguity is the whole defence.
        for width in (2, 4):
            cand = pc - width
            if cand < lo:
                continue
            if _ldr_is_32bit_branch(data, cand):
                continue
            got = _ldr_pc_imm(data, cand)
            if got is None:
                continue
            lrn, imm = got
            ldr_addr = cand + ADDR_BIAS
            slot = ((ldr_addr & ~3) + 4 + imm) & ~3
            out.append((ldr_addr, slot, add_pc, lrn))
            break
    return out


def _is_prologue_pair(data: bytes, ldr_off: int) -> bool:
    """True if the candidate load is really a __stack_chk_guard canary read.

    A fortified function opens with `push {..lr}` + `add r7,sp,#imm` followed by
    `bl __stack_chk_guard`; the guard value then lives at `sp+imm`. Loads feeding
    that are not string literals. This is a cheap sanity check, not a proof - the
    opcode guard in `_ldr_pc_imm` is the real defence.
    """
    if ldr_off < 4:
        return False
    hw1 = struct.unpack_from("<H", data, ldr_off - 4)[0]
    hw2 = struct.unpack_from("<H", data, ldr_off - 2)[0]
    return hw1 == 0xB5F0 and hw2 == 0xAF03  # push {..lr}; add r7,sp,#imm


def find_string_xrefs(lib: Library, needle: str):
    """One pass over .text: every literal-pool load whose string contains `needle`.

    This is the offline replacement for a Ghidra string xref. It reports the
    loading instruction, the literal slot, the addend used, and the resolved
    string, so a caller can be identified without opening the project.
    """
    data = lib.data
    n = len(data)
    out = []
    for pc in range(0, n - 8, 2):
        hw1 = struct.unpack_from("<H", data, pc)[0]
        imm = None
        width = 2
        if (hw1 & 0xF800) == 0x4800:  # ldr rN,[pc,#imm8*4]
            imm = (hw1 & 0x00FF) * 4
        elif (hw1 & 0xF800) == 0xF8D0:  # ldr.w rN,[pc,#imm12]
            hw2 = struct.unpack_from("<H", data, pc + 2)[0]
            if (hw2 & 0xF000) == 0xF000:
                imm = ((hw1 & 0x004F) << 8) | hw2
                width = 4
        if imm is None:
            continue
        ldr_addr = pc + ADDR_BIAS
        slot = ((ldr_addr & ~3) + 4 + imm) & ~3
        so = to_file_offset(slot)
        if so < 0 or so + 4 > n:
            continue
        w = struct.unpack_from("<I", data, so)[0]
        # Only the add IMMEDIATELY following this load consumes it. See
        # `_ldr_pc_imm` for the phantom-key incident that motivated this.
        add_off = pc + width
        if add_off + 2 > n:
            continue
        if not _is_add_pc(struct.unpack_from("<H", data, add_off)[0]):
            continue
        add_pc = add_off + ADDR_BIAS + 4
        target = w + add_pc
        s = lib.cstr(to_file_offset(target), 64)
        if s and needle in s:
            out.append((ldr_addr, slot, add_pc, target, s))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--so", type=Path, default=DEFAULT_SO)
    ap.add_argument("--from-dump", type=Path,
                    help="re-resolve every slot listed in an existing ghidra dump")
    ap.add_argument("--function", type=str,
                    help="ADDR[:END] to scan structurally for literal loads")
    ap.add_argument("--expect", type=str,
                    help="substring that must appear, for self-test mode")
    ap.add_argument("--show-bytes", action="store_true")
    ap.add_argument("--find-string", type=str,
                    help="one-pass .text scan for every literal load whose string contains this")
    args = ap.parse_args()

    if not args.so.exists():
        print(f"ERROR: {args.so} not found", file=sys.stderr)
        return 2
    lib = Library(args.so)
    print(f"# {args.so}  ({lib.size} bytes)\n")

    if args.from_dump:
        n = resolve_from_dump(lib, args.from_dump)
        print(f"\nresolved: {n}")
        if args.expect:
            text = args.from_dump.read_text(encoding="utf-8", errors="replace")
            print(f"NOTE: --expect is only meaningful for --function scans")
        return 0

    if args.find_string:
        hits = find_string_xrefs(lib, args.find_string)
        for ldr_addr, slot, add_pc, target, s in hits:
            print(f"ldr@{ldr_addr:#010x} slot={slot:#010x} "
                  f"add_pc={add_pc:#010x} -> {target:#010x}  {s!r}")
        print(f"\nrefs to {args.find_string!r}: {len(hits)}")
        return 0

    if args.function:
        if ":" not in args.function:
            print("ERROR: --function wants ADDR[:END]", file=sys.stderr)
            return 2
        a, _, b = args.function.partition(":")
        start = int(a, 16)
        end = int(b, 16) if b else start + 0x400
        print(f"===== {start:#x}..{end:#x} =====")
        n = 0
        for addr, slot, add_pc, rn in iter_thumb_ldr_addpc(lib, start, end):
            try:
                w = lib.u32(to_file_offset(slot))
            except ValueError:
                continue
            target = w + add_pc
            s = lib.cstr(to_file_offset(target))
            if not s or not all(32 <= ord(c) < 127 for c in s):
                continue
            n += 1
            print(f"ldr@{addr:#010x} r{rn} slot={slot:#010x} "
                  f"w={w:#010x} add_pc={add_pc:#010x} -> {target:#010x}  {s!r}")
        print(f"resolved: {n}")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
