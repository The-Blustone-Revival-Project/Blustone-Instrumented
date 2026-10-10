from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB


def printable(data: bytes) -> bool:
    return len(data) > 2 and sum(byte in (9, 10, 13) or 32 <= byte < 127 for byte in data[:80]) >= min(8, len(data[:80]))


path = Path(sys.argv[1])
start = int(sys.argv[2], 0)
end = int(sys.argv[3], 0)
data = path.read_bytes()
disassembler = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
disassembler.detail = True
instructions = list(disassembler.disasm(data[start:end], start))
for index, instruction in enumerate(instructions):
    if instruction.mnemonic != "ldr" or "pc" not in instruction.op_str or "#" not in instruction.op_str:
        continue
    match = re.search(r"#(0x[0-9a-f]+|[0-9]+)", instruction.op_str)
    if not match:
        continue
    immediate = int(match.group(1), 0)
    literal_address = ((instruction.address + 4) & ~3) + immediate
    if literal_address + 4 > len(data):
        continue
    value = struct.unpack_from("<I", data, literal_address)[0]
    for following in instructions[index + 1:index + 4]:
        if following.mnemonic != "add" or "pc" not in following.op_str:
            continue
        target = following.address + 4 + value
        if target >= len(data):
            continue
        text = data[target:target + 160].split(b"\0", 1)[0]
        if printable(text):
            print(f"{instruction.address:08x} literal={literal_address:08x} target={target:08x} {text!r}")
