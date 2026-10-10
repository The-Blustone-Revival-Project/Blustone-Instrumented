"""Resolve Thumb PC-relative string references in an ARM shared library, offline.

    resolve-thumb-strings.py <lib.so> <func-entry-hex> [...] [--dump-keys]

Why this exists
---------------
Reading the native function's JSON keys from a disassembly needs the value each
`ldr rX, [pc, #imm]` literal-pool slot holds *after* relocations. On disk those
slots are pre-relocation placeholders, which is why reading the .so directly
gives nonsense and why the Ghidra dumps show unresolvable `DAT_xxxx` labels.

Ghidra can do this, but it writes to the project and locks it, so only one
analysis can run at a time. This tool does the same job read-only and with no
shared state, so many analyses can run in parallel over one 35 MB library
instead of copying a 2 GB project per worker.

Method
------
1. Read PT_LOAD segments to build vaddr -> file-offset mapping.
2. Read the dynamic section (via vaddr mapping) for DT_REL/DT_RELA and apply
   R_ARM_RELATIVE relocations to the in-memory image.
3. Disassemble the Thumb instruction stream of the requested function: for each
   `ldr rX, [pc, #imm]`, compute the literal slot, read the relocated word, then
   if a following `add rX, pc` is present the string address is
   word + (address of the add) + 4.
4. Read the NUL-terminated string there and report it.

Only the subset needed to walk straight-line Thumb code is decoded, which is
sufficient for the constant-pool walks these functions perform.

STATUS: UNPROVEN - DO NOT TRUST THE OUTPUT
It applies ~128k R_ARM_RELATIVE relocations, but the literal-pool slots that
matter for `CSRGameStage::SetStage` (0xa27810 and neighbours) carry no
relocation entry, so they still read back as garbage here while Ghidra's
relocated memory returns the correct values. The mechanism Ghidra uses for
those slots was not identified, so this does not currently reproduce
Ghidra's results. It is kept because the approach is right and the gap is
narrow, but use the Ghidra scripts under analysis/ghidra-scripts/ until this
matches:
    ResolvePcRelativeStrings.java  (prints the JSON keys a function reads)
    DecompileAtAddress.java       (decompiles unnamed functions by address)
    ListCallers.java              (callers of a given entry)
    ListFunctionNames.java        (find functions by name fragment)

Ghidra writes to and locks analysis/ghidra-project/, so only one analysis can
run at a time. That is why the parallel research agents work from the
read-only tables (analysis/*.tsv) instead.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

R_ARM_RELATIVE = 23
DT_NULL, DT_RELA, DT_RELASZ, DT_REL, DT_RELSZ = 0, 7, 8, 17, 18


class Elf:
    def __init__(self, path: Path) -> None:
        d = bytearray(path.read_bytes())
        self.data = d
        if d[:4] != b"\x7fELF":
            raise SystemExit(f"{path} is not an ELF file")
        if d[4] != 1:
            raise SystemExit("expected a 32-bit ELF")
        self.phoff = struct.unpack_from("<I", d, 0x1C)[0]
        self.phentsize = struct.unpack_from("<H", d, 0x2A)[0]
        self.phnum = struct.unpack_from("<H", d, 0x2C)[0]
        self.segments: list[tuple[int, int, int]] = []  # vaddr, filesz, offset
        self.dyn_vaddr = self.dyn_size = 0
        for i in range(self.phnum):
            o = self.phoff + i * self.phentsize
            p_type, p_offset, p_vaddr, _p_paddr, p_filesz = struct.unpack_from("<5I", d, o)
            if p_type == 1:  # PT_LOAD
                self.segments.append((p_vaddr, p_filesz, p_offset))
            elif p_type == 2:  # PT_DYNAMIC
                self.dyn_vaddr, self.dyn_size = p_vaddr, p_filesz
        self.dyn = self._dynamic()

    def vaddr_to_offset(self, vaddr: int) -> int:
        for base, size, off in self.segments:
            if base <= vaddr < base + size:
                return off + (vaddr - base)
        # fall back: the segment list can omit a trailing read-only page
        for base, size, off in self.segments:
            if base <= vaddr < base + size + 0x1000:
                return off + (vaddr - base)
        raise SystemExit(f"vaddr 0x{vaddr:x} is outside every PT_LOAD segment")

    def _dynamic(self) -> dict[int, int]:
        base = self.vaddr_to_offset(self.dyn_vaddr)
        out: dict[int, int] = {}
        i = base
        while i < base + self.dyn_size:
            tag, val = struct.unpack_from("<iI", self.data, i)
            if tag == DT_NULL:
                break
            out.setdefault(tag, val)
            i += 8
        return out

    def apply_relocations(self) -> int:
        count = 0
        rela, relasz = self.dyn.get(DT_RELA), self.dyn.get(DT_RELASZ)
        if rela and relasz:
            base = self.vaddr_to_offset(rela)
            for k in range(relasz // 12):
                r_off, r_info, r_add = struct.unpack_from("<III", self.data, base + k * 12)
                if (r_info & 0xFF) == R_ARM_RELATIVE and r_off + 4 <= len(self.data):
                    struct.pack_into("<I", self.data, r_off, (r_add + r_off) & 0xFFFFFFFF)
                    count += 1
        # Section headers too: on this library the R_ARM_RELATIVE entries that
        # matter are in .rel.dyn, which the dynamic table alone does not cover.
        try:
            shoff = struct.unpack_from("<I", d, 0x20)[0]
            shentsize = struct.unpack_from("<H", d, 0x2E)[0]
            shnum = struct.unpack_from("<H", d, 0x30)[0]
            shstrndx = struct.unpack_from("<H", d, 0x32)[0]
            if shoff and shnum:
                names_off = struct.unpack_from("<I", d, shoff + shstrndx * shentsize + 16)[0]
                for i in range(shnum):
                    o = shoff + i * shentsize
                    sh_type = struct.unpack_from("<I", d, o + 4)[0]
                    sh_offset = struct.unpack_from("<I", d, o + 16)[0]
                    sh_size = struct.unpack_from("<I", d, o + 20)[0]
                    sh_link = struct.unpack_from("<I", d, o + 24)[0]
                    sh_info = struct.unpack_from("<I", d, o + 28)[0]
                    sh_entsize = struct.unpack_from("<I", d, o + 36)[0]
                    # ELF32: SHT_RELA == 4, SHT_REL == 9. (These were swapped
                    # in the first version, so no section relocation was ever
                    # applied and every literal read back as garbage.)
                    if sh_type == 9 and sh_entsize == 8:  # SHT_REL
                        for k in range(sh_size // 8):
                            r_off, r_info = struct.unpack_from("<II", d, sh_offset + k * 8)
                            if (r_info & 0xFF) == R_ARM_RELATIVE and r_off + 4 <= len(self.data):
                                struct.pack_into("<I", self.data, r_off, r_off & 0xFFFFFFFF)
                                count += 1
                    elif sh_type == 4 and sh_entsize == 12:  # SHT_RELA
                        for k in range(sh_size // 12):
                            r_off, r_info, r_add = struct.unpack_from("<III", d, sh_offset + k * 12)
                            if (r_info & 0xFF) == R_ARM_RELATIVE and r_off + 4 <= len(self.data):
                                struct.pack_into("<I", self.data, r_off, (r_add + r_off) & 0xFFFFFFFF)
                                count += 1
        except Exception:
            pass

        rel, relsz = self.dyn.get(DT_REL), self.dyn.get(DT_RELSZ)
        if rel and relsz:
            base = self.vaddr_to_offset(rel)
            for k in range(relsz // 8):
                r_off, r_info = struct.unpack_from("<II", self.data, base + k * 8)
                if (r_info & 0xFF) == R_ARM_RELATIVE and r_off + 4 <= len(self.data):
                    struct.pack_into("<I", self.data, r_off, r_off & 0xFFFFFFFF)
                    count += 1
        return count

    def word(self, vaddr: int) -> int:
        return struct.unpack_from("<I", self.data, self.vaddr_to_offset(vaddr))[0]

    def half(self, vaddr: int) -> int:
        return struct.unpack_from("<H", self.data, self.vaddr_to_offset(vaddr))[0]

    def cstring(self, vaddr: int, limit: int = 96) -> str | None:
        try:
            off = self.vaddr_to_offset(vaddr)
        except SystemExit:
            return None
        end = self.data.find(b"\x00", off, off + limit)
        if end < 0:
            return None
        raw = self.data[off:end]
        if not raw or not all(32 <= c < 127 for c in raw):
            return None
        try:
            return raw.decode("ascii")
        except UnicodeDecodeError:
            return None


def thumb_expand_first(insn: int) -> tuple[int, int] | None:
    """(bytes consumed, imm12 scale) for a 32-bit Thumb-2 LDR literal, else None."""
    if (insn & 0xF800) in (0xF800, 0xF000) and (insn & 0x8000):
        return 4, 4
    return None


def walk_strings(elf: Elf, start: int, end: int | None) -> list[tuple[int, int, str]]:
    """Return (ldr_addr, string_addr, text) for every resolvable PC-relative string."""
    found: list[tuple[int, int, str]] = []
    addr = start
    limit = end if end is not None else start + 0x600
    while addr < limit:
        try:
            hw = elf.half(addr)
        except SystemExit:
            break
        # 16-bit LDR literal: 0100 1 Rt[2] imm8 -> LDR Rt, [pc, #imm8*4]
        if (hw & 0xF800) == 0x4800:
            rt = (hw >> 8) & 0x7
            imm = (hw & 0xFF) * 4
            slot = ((addr + 4) & ~3) + imm
            try:
                word = elf.word(slot)
            except SystemExit:
                addr += 2
                continue
            for delta in (0, 2, 4, 6, 8, 10, 12):
                add_at = addr + 2 + delta
                try:
                    aw = elf.half(add_at)
                except SystemExit:
                    break
                # 16-bit ADD Rd, PC, #imm8*4 : 0100 1110 Rd imm8
                if (aw & 0xF800) == 0xA000 and ((aw >> 8) & 0x7) == rt:
                    imm8 = (aw & 0xFF) * 4
                    text = elf.cstring(word + (add_at + 4) + imm8)
                    if text:
                        found.append((addr, word + (add_at + 4) + imm8, text))
                    break
            addr += 2
            continue
        # 32-bit Thumb-2 LDR (literal): 1111 1000 x101 1111 Rt imm12
        hw2 = elf.half(addr + 2) if addr + 4 <= limit else 0
        if (hw & 0xFF7F) == 0xF85F and (hw & 0xF000) == 0xF000:
            pass
        if (hw & 0xFFF0) == 0xF8D0 and (hw & 0xF000) == 0xF000:
            pass
        # 32-bit LDR.W Rt, [pc, #imm12] is encoded F8DF t imm12 (T3) or F85F (T2)
        if (hw & 0xFF7F) in (0xF85F, 0xF8DF):
            rt = (hw >> 8) & 0xF
            imm12 = hw2 & 0xFFF
            slot = ((addr + 4) & ~3) + imm12
            try:
                word = elf.word(slot)
            except SystemExit:
                addr += 4
                continue
            for delta in (0, 2, 4, 6, 8, 10, 12):
                add_at = addr + 4 + delta
                try:
                    aw = elf.half(add_at)
                    aw2 = elf.half(add_at + 2)
                except SystemExit:
                    break
                # ADD.W Rd, PC, #imm12 = F8DF Rd imm12
                if (aw & 0xFFF0) == 0xF8DF and ((aw >> 8) & 0xF) == rt:
                    text = elf.cstring(word + (add_at + 4) + (aw2 & 0xFFF))
                    if text:
                        found.append((addr, word + (add_at + 4) + (aw2 & 0xFFF), text))
                    break
            addr += 4
            continue
        addr += 2
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("library", type=Path)
    ap.add_argument("functions", nargs="+", help="function entry addresses, hex")
    ap.add_argument("--span", type=lambda v: int(v, 0), default=0x800,
                    help="bytes to walk from each entry (default 0x800)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    elf = Elf(args.library)
    applied = elf.apply_relocations()

    results: dict[str, list[dict[str, object]]] = {}
    for raw in args.functions:
        entry = int(raw.replace("0x", ""), 16)
        hits = walk_strings(elf, entry, entry + args.span)
        seen: set[str] = set()
        rows = []
        for ldr_at, str_at, text in hits:
            if text in seen:
                continue
            seen.add(text)
            rows.append({"ldr": f"0x{ldr_at:08x}", "str": f"0x{str_at:08x}", "text": text})
        results[f"0x{entry:08x}"] = rows

    if args.json:
        import json
        print(json.dumps({"relocations_applied": applied, "functions": results}, indent=2))
        return 0

    print(f"relocations applied: {applied}")
    for name, rows in results.items():
        print(f"===== {name} =====")
        for row in rows:
            print(f"  {row['ldr']} -> {row['str']}  \"{row['text']}\"")
        if not rows:
            print("  (no PC-relative strings resolved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
