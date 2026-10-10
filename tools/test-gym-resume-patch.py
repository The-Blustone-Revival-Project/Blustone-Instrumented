"""Offline ARM/Thumb execution of the real patched bytes; no game/device writes."""
from pathlib import Path
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parents[1]
data=(ROOT/"analysis/patched/libnative_core-gym-resume-prototype.so").read_bytes()
HOOK,NEAR,CAVE,GET=0xea25f0,0x612c90,0x210d320,0xf8a956
FIRST,ORDINARY,TUTORIAL=0xea25f6,0xea2726,0xea27f8
REGS=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,
      UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,
      UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12,UC_ARM_REG_LR]

def case(state0,tu,next_scene,state1,bias=0):
    vm=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    vm.mem_map(0x600000+bias,0x1c00000)
    for address,size in [(HOOK,6),(NEAR,12),(CAVE,92)]: vm.mem_write(address+bias,data[address:address+size])
    vm.mem_map(0x30000000,0x10000);vm.mem_map(0x31000000,0x10000)
    values=[state0&0xffffffff,tu,0,0x33333333,0x44444444,0x55555555,
            0x30001000,0x77777777,next_scene,0x99999999,tu,0xbbbbbbbb,0xcccccccc,HOOK+bias+1]
    for register,value in zip(REGS,values):vm.reg_write(register,value)
    sp=0x3100f000;vm.reg_write(UC_ARM_REG_SP,sp)
    vm.mem_write(0x30001024,struct.pack("<I",0x30002000))
    result=[];calls=[]
    def intercept(uc,address,size,unused):
        relative=address-bias
        if relative in (FIRST,ORDINARY,TUTORIAL):
            result.append(relative);uc.emu_stop()
        elif relative==GET:
            assert uc.reg_read(UC_ARM_REG_SP)%8==0
            assert [uc.reg_read(r) for r in REGS[:3]]==[0x30002000,8,1]
            calls.append(1)
            for reg in [UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R12]:uc.reg_write(reg,0xdeadbeef)
            uc.reg_write(UC_ARM_REG_R0,state1&0xffffffff)
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    vm.hook_add(UC_HOOK_CODE,intercept)
    vm.emu_start(HOOK+bias+1,0x2200000+bias,count=150)
    expected=FIRST if state0<=1 else TUTORIAL if tu==8 and next_scene==0xa8 and state1 in (0,1) else ORDINARY
    assert result==[expected],(state0,tu,next_scene,state1,bias,result,expected)
    assert bool(calls)==(state0>1 and tu==8 and next_scene==0xa8)
    assert vm.reg_read(UC_ARM_REG_SP)==sp
    # r12 is AAPCS scratch for the far tail jump. All remaining registers and
    # the original LR must be unchanged, including caller-saved R0-R3.
    for register,value in zip(REGS,values):
        if register!=UC_ARM_REG_R12:assert vm.reg_read(register)==value,(register,hex(vm.reg_read(register)),hex(value))

count=0
for bias in (0,0x10000000):
    for state0 in (-1,0,1,2,3):
        for tu in (2,8,9):
            for next_scene in (0xa7,0xa8):
                for state1 in (-1,0,1,2,3):case(state0,tu,next_scene,state1,bias);count+=1
print(f"Gym resume: {count} Thumb/ASLR predicate paths, original fallbacks, call ABI, preserved registers and stack passed")
