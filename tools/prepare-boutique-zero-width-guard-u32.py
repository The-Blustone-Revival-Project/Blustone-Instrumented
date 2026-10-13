#!/usr/bin/env python3
"""Read-only24-byte Boutique proposal and bounded padding audit; no patch API."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import struct
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT_ARTIFACT_SHA256 = "759481add6592a6e46a692d37e263cef791151a4897a8f98d9eff5ba3f0b6a34"
CAVE, CAVE_END = 0x1D52928, 0x1D52940
HOOK, RESUME = 0x1041B50, 0x1041B54
spec = importlib.util.spec_from_file_location("boutique_generic_proposal", ROOT / "tools/prepare-boutique-zero-width-guard.py")
assert spec and spec.loader
generic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generic)

def signed(value, width):
    return value - (1 << width) if value & (1 << (width - 1)) else value

def sections(data):
    start = struct.unpack_from("<I", data, 32)[0]
    width, count, strings_index = struct.unpack_from("<HHH", data, 46)
    rows = [struct.unpack_from("<10I", data, start + index * width) for index in range(count)]
    names_row = rows[strings_index]
    names = data[names_row[4]:names_row[4] + names_row[5]]
    return {names[row[0]:names.find(b"\0", row[0])].decode(): row for row in rows}

def assemble_body():
    binary = ROOT / "local/toolchains/android-sdk/ndk/29.0.14206865/toolchains/llvm/prebuilt/windows-x86_64/bin"
    with tempfile.TemporaryDirectory(prefix="blustone-boutique-u32-") as directory:
        obj, output = Path(directory) / "guard.o", Path(directory) / "guard.bin"
        subprocess.run([str(binary / "clang.exe"), "--target=armv7a-none-eabi", "-mthumb", "-mfpu=neon", "-c",
                        str(ROOT / "tools/boutique-zero-width-guard-u32.s"), "-o", str(obj)], check=True, capture_output=True)
        subprocess.run([str(binary / "llvm-objcopy.exe"), "--only-section=.text", "-O", "binary", str(obj), str(output)], check=True, capture_output=True)
        return output.read_bytes()

def branch_references(data, table):
    """Overapproximate ARM/Thumb branches, including embedded literal words.
    Any hit rejects placement; no architecture-based exceptions are needed here.
    """
    hits = []
    for name in (".text", ".plt"):
        row = table[name]
        for offset in range(row[4], row[4] + row[5] - 3, 2):
            pc = row[3] + offset - row[4]
            first, second = struct.unpack_from("<HH", data, offset)
            target = None
            if first & 0xF800 == 0xF000:
                pattern = second & 0xD000
                if pattern in (0xD000, 0x9000):
                    s = first >> 10 & 1
                    i1, i2 = 1 ^ ((second >> 13 & 1) ^ s), 1 ^ ((second >> 11 & 1) ^ s)
                    target = pc + 4 + signed((s << 24) | (i1 << 23) | (i2 << 22) | ((first & 1023) << 12) | ((second & 2047) << 1), 25)
                elif pattern == 0xC000 and second & 1 == 0:
                    # Thumb BLX immediate aligns its PC base to a word and
                    # uses imm10L:00. Omitting it leaves a placement audit gap.
                    s = first >> 10 & 1
                    i1, i2 = 1 ^ ((second >> 13 & 1) ^ s), 1 ^ ((second >> 11 & 1) ^ s)
                    target = ((pc + 4) & ~3) + signed((s << 24) | (i1 << 23) | (i2 << 22) | ((first & 1023) << 12) | ((second & 2046) << 1), 25)
                elif pattern == 0x8000 and (first >> 6 & 15) < 14:
                    target = pc + 4 + signed(((first >> 10 & 1) << 20) | ((second >> 11 & 1) << 19) | ((second >> 13 & 1) << 18) | ((first & 63) << 12) | ((second & 2047) << 1), 21)
            elif first & 0xF800 == 0xE000:
                target = pc + 4 + signed((first & 2047) << 1, 12)
            elif first & 0xF000 == 0xD000 and (first >> 8 & 15) < 14:
                target = pc + 4 + signed((first & 255) << 1, 9)
            elif first & 0xF500 == 0xB100:
                target = pc + 4 + ((first >> 9 & 1) << 6) + ((first >> 3 & 31) << 1)
            if target is not None and CAVE <= target < CAVE_END:
                hits.append((pc, target, "Thumb"))
            if pc % 4 == 0:
                word = struct.unpack_from("<I", data, offset)[0]
                if word & 0x0E000000 == 0x0A000000:
                    h = ((word >> 24) & 1) << 1 if word >> 28 == 15 else 0
                    target = pc + 8 + signed(((word & 0xFFFFFF) << 2) | h, 26)
                    if CAVE <= target < CAVE_END:
                        hits.append((pc, target, "ARM"))
    return hits

def audit(data):
    if hashlib.sha256(data).hexdigest() != CURRENT_ARTIFACT_SHA256:
        raise ValueError("Current retained native artifact SHA256 mismatch")
    context = generic.elf_file_offset(data, generic.CONTEXT_ELF, len(generic.CONTEXT))
    if data[context:context + len(generic.CONTEXT)] != generic.CONTEXT:
        raise ValueError("Pinned UInt32-to-F32 denominator context changed")
    cave_offset = generic.elf_file_offset(data, CAVE, CAVE_END - CAVE)
    if data[cave_offset:cave_offset + 24] != b"\0" * 24:
        raise ValueError("Proposed linker padding is occupied")
    table = sections(data)
    extab, rodata = table[".ARM.extab"], table[".rodata"]
    if extab[3] + extab[5] != CAVE or rodata[3] != CAVE_END or rodata[8] != 32:
        raise ValueError("Expected extab-to-rodata alignment gap changed")
    for name, row in table.items():
        if row[1] != 8 and row[5] and max(cave_offset, row[4]) < min(cave_offset + 24, row[4] + row[5]):
            raise ValueError(f"Candidate overlaps section {name}")
    # All ELF symbols, including data and zero-sized symbols.
    symtab, strings_row = table[".dynsym"], table[".dynstr"]
    symbol_values = []
    for offset in range(symtab[4], symtab[4] + symtab[5], 16):
        _, value, size, _, _, _ = struct.unpack_from("<IIIBBH", data, offset)
        symbol_values.append(value)
        if (value & ~1) < CAVE_END and (value & ~1) + max(1, size) > CAVE:
            raise ValueError("Symbol overlaps candidate padding")
    # Every byte offset, not just aligned words, and both ARM/Thumb pointers.
    for address in range(CAVE, CAVE_END):
        if data.find(struct.pack("<I", address)) != -1:
            raise ValueError("Absolute data pointer references candidate padding")
    if branch_references(data, table):
        raise ValueError("Direct instruction reference targets candidate padding")
    # Raw PREL31 scan is conservative. Exactly one apparent hit is a verified
    # DWARF LSDA ULEB call-site tuple, not a pointer: ff ff 01 26 /00 4a 00 00.
    apparent = []
    for name in (".ARM.exidx", ".ARM.extab"):
        row = table[name]
        for offset in range(row[4], row[4] + row[5] - 3, 4):
            value = struct.unpack_from("<I", data, offset)[0]
            target = row[3] + offset - row[4] + signed(value & 0x7FFFFFFF, 31)
            if CAVE <= target < CAVE_END:
                apparent.append((name, offset, target))
    if apparent != [(".ARM.extab", 0x1D4DF30, 0x1D52930)] or data[0x1D4DF2C:0x1D4DF34] != bytes.fromhex("ffff0126004a0000"):
        raise ValueError("Unclassified relative data reference to candidate")
    phoff = struct.unpack_from("<I", data, 28)[0]
    phsize, phcount = struct.unpack_from("<HH", data, 42)
    loads = [struct.unpack_from("<8I", data, phoff + index * phsize) for index in range(phcount)]
    def addend_at(virtual):
        for kind, offset, start, _, size, _, _, _ in loads:
            if kind == 1 and start <= virtual and virtual + 4 <= start + size:
                return struct.unpack_from("<I", data, offset + virtual - start)[0]
        return None
    relocation_types = {}
    for name in (".rel.dyn", ".rel.plt"):
        row = table[name]
        for offset in range(row[4], row[4] + row[5], 8):
            location, info = struct.unpack_from("<II", data, offset)
            kind, symbol = info & 255, info >> 8
            relocation_types[kind] = relocation_types.get(kind, 0) + 1
            if kind not in (2, 21, 22, 23):
                raise ValueError("Unreviewed ARM relocation type")
            if CAVE <= location < CAVE_END:
                raise ValueError("Loader relocation would overwrite candidate")
            if symbol >= len(symbol_values):
                raise ValueError("Malformed relocation symbol index")
            addend = addend_at(location)
            if addend is not None:
                targets = [addend] if kind == 23 else [symbol_values[symbol], (symbol_values[symbol] + addend) & 0xFFFFFFFF]
                if any(CAVE <= target & ~1 < CAVE_END for target in targets):
                    raise ValueError("Resolved local relocation target references candidate")
    return {"artifact_sha256": CURRENT_ARTIFACT_SHA256, "rx_gap": [CAVE, CAVE_END],
            "section_overlap": False, "symbol_overlap": False, "absolute_pointer_refs": [],
            "direct_branch_refs": [], "classified_lsda_false_positive": {"word": 0x1D4DF30, "tuple": [0, 74, 0, 0]},
            "relocation_types": relocation_types, "loader_write_overlap": False,
            "fallthrough": "gap borders noncode extab/rodata sections; no sequential code neighbor",
            "current_patch_collision": False, "dynamic_indirect_execution_verified": False,
            "status": "BOUNDED_STATIC_PLACEMENT_CANDIDATE"}

def proposal(data):
    placement = audit(data)
    body = assemble_body()
    if len(body) != 20:
        raise ValueError("Context-specific guard body must be20 bytes")
    encode, decode = generic._branch_helpers()
    hook, back = encode(HOOK, CAVE), encode(CAVE + len(body), RESUME)
    if decode(HOOK, hook) != CAVE or decode(CAVE + len(body), back) != RESUME:
        raise ValueError("Relocated Thumb branch mismatch")
    return {"variant": "U32_DENOMINATOR_CONTEXT_ONLY", "placement": placement,
            "native_library_modified": False, "apk_built_or_installed": False, "cave_proven_for_live_execution": False,
            "hook_elf": HOOK, "resume_elf": RESUME, "cave_elf": CAVE,
            "denominator_proof": "unchanged vcvt.f32.u32 s4,s4 atELF1041b46; only+0 orpositive finite values reachable",
            "negative_zero_protection": False, "body_hex": body.hex(), "hook_branch_hex": hook.hex(),
            "resume_branch_hex": back.hex(), "candidate_stub_hex": (body + back).hex(),
            "future_release_required_if_apk_rebuilt": True}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(proposal(args.input.read_bytes()), indent=2))

if __name__ == "__main__":
    main()
