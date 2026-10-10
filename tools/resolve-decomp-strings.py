"""Print literal strings used by a Ghidra export (project image base 0x10000)."""
import re
import struct
import sys
from pathlib import Path

native = Path('analysis/extracted/lib/armeabi-v7a/libnative_core.so').read_bytes()
source = Path(sys.argv[1]).read_text(encoding='utf-8')
aliases = {}
for line_no, line in enumerate(source.splitlines(), 1):
    assignment = re.search(r'(\w+) = (_(?:DAT|LAB|FUN)_[0-9a-f]{8});', line)
    if assignment:
        aliases[assignment[1]] = assignment[2]
    for variable, literal in aliases.items():
        line = re.sub(r'\b' + variable + r'(?= \+ 0x)', literal, line)
    for match in re.finditer(r'_(?:DAT|LAB|FUN)_([0-9a-f]{8}) \+ 0x([0-9a-f]+)', line):
        slot, pc = (int(x, 16) - 0x10000 for x in match.groups())
        target = (struct.unpack_from('<I', native, slot)[0] + pc) & 0xffffffff
        if target >= len(native):
            continue
        value = native[target:target+250].split(b'\0')[0]
        if value and all(32 <= x < 127 or x in (9,10,13) for x in value):
            print(f'{line_no}: {match.group(0)} => {value.decode()!r}')
