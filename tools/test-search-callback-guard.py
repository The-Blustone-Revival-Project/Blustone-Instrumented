"""Execute emitted ARM/Thumb guard paths against synthetic memory, never a game process."""
from pathlib import Path
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parents[1]
BASE=0x10000000; HEAP=0x30000000; SP=0x40008000; RET=BASE+0xe28000
DATA=(ROOT/"analysis/patched/libnative_core-search-guard-candidate-v2.so").read_bytes()
REGS=(UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,
      UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11)

def word(vm,address,value): vm.mem_write(address,struct.pack("<I",value))
def read(vm,address): return struct.unpack("<I",vm.mem_read(address,4))[0]
def machine():
    vm=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    vm.mem_map(BASE,0x2400000);vm.mem_write(BASE,DATA)
    vm.mem_map(HEAP,0x10000);vm.mem_map(0x40000000,0x10000)
    for i,reg in enumerate(REGS): vm.reg_write(reg,HEAP+0x1000+i*16)
    vm.reg_write(UC_ARM_REG_SP,SP);vm.reg_write(UC_ARM_REG_LR,RET|1)
    return vm
def execute(vm,start,stop):
    hit=[]
    def hook(vm,address,size,_):
        if address==stop: hit.append(address);vm.emu_stop()
    vm.hook_add(UC_HOOK_CODE,hook)
    vm.emu_start((BASE+start)|1,BASE+0x2400000,count=500)
    assert hit, f"Did not reach expected endpoint {stop:x}"

for case in ("valid","stale","nullapp","nullmanager","nullcurrent","nullcapture"):
    vm=machine(); callback=HEAP+0x100; app=HEAP+0x200; manager=HEAP+0x300; scene=HEAP+0x400
    vm.reg_write(UC_ARM_REG_R0,callback)
    word(vm,callback+0x40,0 if case=="nullcapture" else scene)
    word(vm,BASE+0x21ef1e0,0 if case=="nullapp" else app)
    word(vm,app+8,0 if case=="nullmanager" else manager)
    word(vm,manager+0x34,0 if case=="nullcurrent" else scene+16 if case=="stale" else scene)
    before=[vm.reg_read(r) for r in REGS]
    execute(vm,0xe27420,BASE+0xe27424 if case=="valid" else RET)
    if case=="valid":
        assert vm.reg_read(UC_ARM_REG_SP)==SP-20
        assert vm.reg_read(UC_ARM_REG_R7)==SP-8
        assert vm.reg_read(UC_ARM_REG_R0)==callback
    else:
        assert vm.reg_read(UC_ARM_REG_SP)==SP
        assert [vm.reg_read(r) for r in REGS]==before

vm=machine();parent=HEAP+0x600;vm.reg_write(UC_ARM_REG_R4,parent)
execute(vm,0xe27456,BASE+0xe2745a)
assert vm.reg_read(UC_ARM_REG_R1)==parent+4 and vm.reg_read(UC_ARM_REG_R0)==SP+8

def frame(vm):
    cookie=HEAP+0x800;word(vm,cookie,0xfeedbeef);word(vm,SP+0x2c,0xfeedbeef)
    vm.reg_write(UC_ARM_REG_R8,cookie)
    word(vm,SP+4,0);word(vm,SP+12,0);word(vm,SP+16,0)
    vm.mem_write(SP+0x30,struct.pack("<8I",*[0x11110000+i for i in range(7)],RET|1))

vm=machine();frame(vm);vm.reg_write(UC_ARM_REG_R4,0);word(vm,SP+8,0xabcdef01)
execute(vm,0xe27456,RET)
assert read(vm,SP+8)==0 and read(vm,SP+12)==0 and vm.reg_read(UC_ARM_REG_SP)==SP+80

vm=machine();frame(vm);word(vm,SP+8,0)
execute(vm,0xe2749a,RET)
assert vm.reg_read(UC_ARM_REG_SP)==SP+80

vm=machine();target=HEAP+0x900;word(vm,SP+8,target)
execute(vm,0xe2749a,BASE+0xe2749e)
assert vm.reg_read(UC_ARM_REG_R0)==target and vm.reg_read(UC_ARM_REG_R1)==1
print("10 emitted Thumb paths passed: scene identities, register/stack preservation, parent/child cleanup and valid original-call replay. No native game execution claimed.")
