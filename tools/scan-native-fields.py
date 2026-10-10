"""Candidate PIC strings in one ARM Thumb symbol, including past literal pools.

Scanning each halfword can also decode data as instructions. Output is a lead;
verify a field in its surrounding instructions/parser before implementing it.
"""
import struct
import sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from capstone.arm import ARM_OP_MEM, ARM_REG_PC
from elftools.elf.elffile import ELFFile

path = Path("analysis/extracted/lib/armeabi-v7a/libnative_core.so")
with path.open("rb") as stream:
    elf = ELFFile(stream)
    symbols = [s for s in elf.get_section_by_name(".dynsym").iter_symbols() if sys.argv[1] in s.name]
data = path.read_bytes()
decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
decoder.detail = True
for symbol in symbols:
    start = symbol["st_value"] & ~1
    print(f"SYMBOL {symbol.name} start={start:x} size={symbol['st_size']:x}")
    for at in range(start, start + symbol["st_size"], 2):
        sequence = list(decoder.disasm(data[at:at + 18], at, count=5))
        if not sequence:
            continue
        first = sequence[0]
        if not first.mnemonic.startswith("ldr") or len(first.operands) != 2:
            continue
        register, memory = first.operands
        if memory.type != ARM_OP_MEM or memory.mem.base != ARM_REG_PC:
            continue
        literal = ((at + 4) & ~3) + memory.mem.disp
        if not 0 <= literal <= len(data) - 4:
            continue
        delta = struct.unpack_from("<I", data, literal)[0]
        for following in sequence[1:]:
            if following.mnemonic.startswith("add") and following.operands[0].reg == register.reg and "pc" in following.op_str:
                target = (following.address + 4 + delta) & 0xffffffff
                raw = data[target:target + 150].split(b"\0", 1)[0]
                if raw and all(32 <= byte < 127 for byte in raw) and chr(raw[0]).isalnum():
                    print(f"{at:08x} add={following.address:08x} literal={literal:08x} string={target:08x} {raw.decode()}")
                break
