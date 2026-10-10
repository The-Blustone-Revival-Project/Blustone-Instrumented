"""Execute candidate instructions against synthetic memory only, not a game."""
from pathlib import Path
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parents[1]
DATA=(ROOT/"analysis/patched/libnative_core-empty-guide-candidate.so").read_bytes()
ENTRY=0xe1ffe4; HEAP=0x30000000; SP=0x40008000
REGS=(UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,
      UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11)

def word(vm,address,value): vm.mem_write(address,struct.pack("<I",value))

cases=("unavailable","emptyvirtual","max_unavailable","available","last_available","wrongclass","existingguide",
       "controlonly","nogroups","friendonly","badflag","partialrows","longrows","reversedrows",
       "misalignedrows","partialgroups","longgroups","unknowngroup","nullscene")
deferred={"unavailable","emptyvirtual","max_unavailable"}
for base in (0x10000000,0x13000000):
    for case in cases:
        vm=Uc(UC_ARCH_ARM,UC_MODE_THUMB);vm.mem_map(base,0x2400000);vm.mem_write(base,DATA)
        vm.mem_map(HEAP,0x10000);vm.mem_map(0x40000000,0x10000)
        scene=HEAP+0x1000;groups=HEAP+0x2000;rows=HEAP+0x3000;ret=base+0xe28000
        for i,register in enumerate(REGS): vm.reg_write(register,0x11110000+i*16)
        vm.reg_write(UC_ARM_REG_R0,0 if case=="nullscene" else scene)
        vm.reg_write(UC_ARM_REG_SP,SP);vm.reg_write(UC_ARM_REG_LR,ret|1)
        word(vm,scene,base+0x216f2ec+(4 if case=="wrongclass" else 0))
        word(vm,scene+0x6ac,HEAP+0x5000 if case=="existingguide" else 0)
        word(vm,scene+0x6b0,HEAP+0x5100 if case in ("existingguide","controlonly") else 0)
        word(vm,scene+0x678,0 if case=="nogroups" else groups)
        word(vm,scene+0x67c,0 if case=="nogroups" else groups+(29 if case=="partialgroups" else 252 if case=="longgroups" else 28))
        word(vm,groups,1 if case=="friendonly" else 4 if case=="unknowngroup" else 2)
        count=32 if case in ("max_unavailable","last_available") else 33 if case=="longrows" else 1
        begin=0 if case=="emptyvirtual" else rows+(1 if case=="misalignedrows" else 0)
        end=0 if case=="emptyvirtual" else begin+count*56+(1 if case=="partialrows" else 0)
        if case=="reversedrows":end=begin-4
        word(vm,groups+0x10,begin);word(vm,groups+0x14,end)
        if case in ("available","badflag"):vm.mem_write(rows+0x28,bytes([1 if case=="available" else 2]))
        if case=="last_available":vm.mem_write(rows+31*56+0x28,b"\x01")
        word(vm,scene+0x2c,0);word(vm,HEAP+0x6000,8) # untouched input/guide-marker sentinels
        before=[vm.reg_read(r) for r in REGS];heap_before=bytes(vm.mem_read(HEAP,0x10000))
        stop=ret if case in deferred else base+ENTRY+12;hit=[]
        def hook(machine,address,size,_):
            if address==stop:hit.append(address);machine.emu_stop()
        vm.hook_add(UC_HOOK_CODE,hook);vm.emu_start((base+ENTRY)|1,base+0x2400000,count=3000)
        assert hit,(hex(base),case,"endpoint not reached")
        assert bytes(vm.mem_read(HEAP,0x10000))==heap_before,(case,"heap changed")
        after=[vm.reg_read(r) for r in REGS]
        if case in deferred:
            assert after==before and vm.reg_read(UC_ARM_REG_SP)==SP,(case,"return ABI")
        else:
            expected=before[:];expected[5]=before[0];expected[7]=SP-8
            assert after==expected and vm.reg_read(UC_ARM_REG_SP)==SP-224,(case,"prologue ABI")
        assert vm.reg_read(UC_ARM_REG_LR)==ret|1,(case,"LR")
print("38 emitted-code paths passed across two load biases: fresh deferral, available/existing/unknown fallback, original prologue and unchanged heap. No native/runtime navigation claim.")
