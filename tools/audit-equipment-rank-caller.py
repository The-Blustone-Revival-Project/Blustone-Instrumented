"""Read-only, hash-pinned final ARM equipment rank-request caller audit.

Requires capstone. Run with the original armeabi-v7a libnative_core.so path.
The executable segment includes data; scanning every halfword is deliberately
over-inclusive. A match is a direct-branch candidate, not proof of reachability.
This does not resolve register-indirect calls or prove server eligibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

ORIGINAL_SHA256 = "c4646ac3817b0008b6ea387fde9c8279fd439343ccc272acdc5883fab9d00eec"
TARGET = 0xF4A0BC


def signed(value: int, bits: int) -> int:
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def thumb_call(address: int, first: int, second: int) -> tuple[str, int] | None:
    if first & 0xF800 != 0xF000:
        return None
    # Conditional B.W uses direct J bits and a smaller signed displacement.
    if second & 0xD000 == 0x8000 and (first >> 6) & 15 < 14:
        offset = (((first >> 10) & 1) << 20) | (((second >> 11) & 1) << 19) | (((second >> 13) & 1) << 18) | ((first & 63) << 12) | ((second & 2047) << 1)
        return "thumb-b.w-conditional", (address + 4 + signed(offset, 21)) & 0xFFFFFFFF
    if second & 0xD000 not in (0xD000, 0x9000) and second & 0xD001 != 0xC000:
        return None
    sign = (first >> 10) & 1
    i1 = (~(((second >> 13) & 1) ^ sign)) & 1
    i2 = (~(((second >> 11) & 1) ^ sign)) & 1
    offset = (sign << 24) | (i1 << 23) | (i2 << 22) | ((first & 1023) << 12) | ((second & 2047) << 1)
    exchange = second & 0xD001 == 0xC000
    base = (address + 4) & ~3 if exchange else address + 4
    mode = "thumb-blx" if exchange else ("thumb-bl" if second & 0x4000 else "thumb-b.w")
    return mode, (base + signed(offset, 25)) & 0xFFFFFFFF


def arm_call(address: int, word: int) -> tuple[str, int] | None:
    if word & 0x0E000000 == 0x0A000000 and word >> 28 != 15:
        mode = "arm-bl" if word & 0x01000000 else "arm-b"
        return mode, (address + 8 + signed((word & 0xFFFFFF) << 2, 26)) & 0xFFFFFFFF
    if word & 0xFE000000 == 0xFA000000:
        offset = ((word & 0xFFFFFF) << 2) | (((word >> 24) & 1) << 1)
        return "arm-blx", (address + 8 + signed(offset, 26)) & 0xFFFFFFFF
    return None


def audit(path: Path) -> dict:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != ORIGINAL_SHA256:
        raise ValueError("Requires the exact immutable final original ARM library")
    if data[:6] != b"\x7fELF\x01\x01":
        raise ValueError("Expected little-endian ELF32")
    phoff = struct.unpack_from("<I", data, 28)[0]
    phsize, phcount = struct.unpack_from("<HH", data, 42)
    segments = []
    candidates = []
    for n in range(phcount):
        kind, offset, address, _, length, _, flags, _ = struct.unpack_from("<8I", data, phoff + n * phsize)
        if kind != 1 or not flags & 1:
            continue
        segment = data[offset:offset + length]
        if len(segment) != length:
            raise ValueError("Truncated executable segment")
        segments.append({"file_offset": hex(offset), "elf_address": hex(address), "bytes": length})
        for i in range(0, length - 3, 2):
            first, second = struct.unpack_from("<HH", segment, i)
            decoded = thumb_call(address + i, first, second)
            if decoded and decoded[1] == TARGET:
                candidates.append({"elf_address": hex(address + i), "mode": decoded[0], "bytes": segment[i:i + 4].hex()})
        for i in range(0, length - 3, 4):
            decoded = arm_call(address + i, struct.unpack_from("<I", segment, i)[0])
            if decoded and decoded[1] == TARGET:
                candidates.append({"elf_address": hex(address + i), "mode": decoded[0], "bytes": segment[i:i + 4].hex()})

    expected = [{"elf_address": "0xbca1f2", "mode": "thumb-bl", "bytes": "7ff363ff"}]
    if candidates != expected:
        raise ValueError(f"Unexpected direct caller candidates: {candidates}")
    # This original ELF has identity mapping for these code addresses. Mapping
    # is checked against its actual PT_LOAD entries rather than assumed.
    def original_bytes(address: int, size: int) -> bytes:
        for seg in segments:
            start = int(seg["elf_address"], 16)
            if start <= address and address + size <= start + seg["bytes"]:
                offset = int(seg["file_offset"], 16) + address - start
                return data[offset:offset + size]
        raise ValueError("Evidence address outside executable PT_LOAD")

    disassembler = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    evidence = {}
    for label, start, end in [("zero_vector_and_submission", 0xBCA174, 0xBCA1F6), ("stored_rank_attr_and_card_qty", 0xBC6772, 0xBC677E)]:
        evidence[label] = [{"elf_address": hex(ins.address), "bytes": bytes(ins.bytes).hex(), "instruction": ins.mnemonic + " " + ins.op_str}
                           for ins in disassembler.disasm(original_bytes(start, end - start), start)]
    instructions = {row["elf_address"]: row["instruction"] for row in evidence["zero_vector_and_submission"]}
    required = {"0xbca174": "movs r0, #0", "0xbca176": "str r0, [sp, #0x2c]", "0xbca178": "strd r0, r0, [sp, #0x24]",
                "0xbca1e6": "movs r6, #2", "0xbca1e8": "add r1, sp, #0x24", "0xbca1f2": "bl #0xf4a0bc"}
    if any(instructions.get(address) != instruction for address, instruction in required.items()):
        raise ValueError("Original vector initialization or request argument evidence changed")
    return {"original_sha256": digest, "target_elf": hex(TARGET), "target_ghidra": hex(TARGET + 0x10000),
            "executable_segments": segments, "direct_call_candidates": candidates,
            "evidence": evidence, "conclusion": "Only direct caller candidate submits the initialized empty Hunter vector with gold PRICE_TYPE 2",
            "limits": ["Register-indirect and external calls are not resolved", "No original server sacrifice eligibility or numerical prices recovered", "Stored card_qty is not a demonstrated source selector"]}


def self_test() -> None:
    # Real final-original Thumb BL plus independently encoded backward branch.
    assert thumb_call(0xBCA1F2, 0xF37F, 0xFF63) == ("thumb-bl", TARGET)
    assert thumb_call(0x1000, 0xF7FF, 0xFFFC) == ("thumb-bl", 0xFFC)
    assert thumb_call(0x1000, 0x2000, 0xFFFC) is None
    assert arm_call(0x1000, 0xEBFFFFFC) == ("arm-bl", 0xFF8)
    assert arm_call(0x1000, 0xFA000000) == ("arm-blx", 0x1008)
    assert arm_call(0x1000, 0xEA000000) == ("arm-b", 0x1008)
    assert thumb_call(0x1000, 0xF000, 0xB800) == ("thumb-b.w", 0x1004)
    assert thumb_call(0x1000, 0xF000, 0x8000) == ("thumb-b.w-conditional", 0x1004)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    self_test()
    if args.original:
        print(json.dumps(audit(args.original), indent=2))
    elif not args.self_test:
        parser.error("original library path or --self-test required")
