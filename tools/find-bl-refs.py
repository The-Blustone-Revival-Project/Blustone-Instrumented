from __future__ import annotations

import sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

path = sys.argv[1]
targets = {int(value, 0) for value in sys.argv[2:]}
data = open(path, "rb").read()
cs = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
cs.detail = True
for instruction in cs.disasm(data, 0):
    if instruction.mnemonic not in {"bl", "blx"} or not instruction.operands:
        continue
    operand = instruction.operands[0]
    if operand.type == 2 and operand.imm in targets:
        print(f"{instruction.address:08x} -> {operand.imm:08x}")
