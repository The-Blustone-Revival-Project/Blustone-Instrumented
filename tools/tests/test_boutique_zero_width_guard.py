"""Actual Thumb/VFP execution in Unicorn; no native library mutation or APK."""
import hashlib
import importlib.util
import math
import struct
import unittest
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB
from unicorn.arm_const import *

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("boutique_proposal", ROOT / "tools/prepare-boutique-zero-width-guard.py")
tool = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(tool)

def bits(value):
    return struct.unpack("<I", struct.pack("<f", value))[0]

def run(original, numerator, denominator, fpscr=0, cpsr=0xA0000030):
    machine = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    site_page = tool.HOOK_ELF & ~0xFFF
    machine.mem_map(site_page, 0x1000)
    machine.mem_map(tool.SIMULATION_CAVE, 0x1000)
    stack_base, stack_top = 0x3000000, 0x3000800
    machine.mem_map(stack_base, 0x1000)
    machine.mem_write(stack_base, b"\xA5" * 0x1000)
    machine.reg_write(UC_ARM_REG_C1_C0_2, 0x00F00000)
    machine.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
    machine.reg_write(UC_ARM_REG_CPSR, cpsr)
    registers = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
                 UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                 UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11, UC_ARM_REG_R12]
    for i, register in enumerate(registers):
        machine.reg_write(register, 0x12345670 + i)
    machine.reg_write(UC_ARM_REG_SP, stack_top)
    machine.reg_write(UC_ARM_REG_LR, 0x55667789)
    for i in range(32):
        machine.reg_write(globals()[f"UC_ARM_REG_S{i}"], bits(100.0 + i))
    machine.reg_write(UC_ARM_REG_S0, numerator)
    machine.reg_write(UC_ARM_REG_S4, denominator)
    machine.reg_write(UC_ARM_REG_FPSCR, fpscr)
    before = [machine.reg_read(register) for register in registers] + [machine.reg_read(UC_ARM_REG_SP), machine.reg_read(UC_ARM_REG_LR)]
    if original:
        machine.mem_write(tool.HOOK_ELF, tool.EXPECTED_DIVIDE)
    else:
        body = tool.assemble_body()
        encode, _ = tool._branch_helpers()
        machine.mem_write(tool.HOOK_ELF, encode(tool.HOOK_ELF, tool.SIMULATION_CAVE))
        machine.mem_write(tool.SIMULATION_CAVE, body + encode(tool.SIMULATION_CAVE + len(body), tool.RESUME_ELF))
    machine.emu_start(tool.HOOK_ELF | 1, tool.RESUME_ELF, count=50)
    after = [machine.reg_read(register) for register in registers] + [machine.reg_read(UC_ARM_REG_SP), machine.reg_read(UC_ARM_REG_LR)]
    assert after == before, "guard changed general registers/SP/LR"
    return {
        "float_registers": [machine.reg_read(globals()[f"UC_ARM_REG_S{i}"]) for i in range(32)],
        "fpscr": machine.reg_read(UC_ARM_REG_FPSCR), "cpsr": machine.reg_read(UC_ARM_REG_CPSR),
        "pc": machine.reg_read(UC_ARM_REG_PC),
        "outside_scratch": bytes(machine.mem_read(stack_base, stack_top - stack_base - 4)) + bytes(machine.mem_read(stack_top, 0x800)),
    }

class BoutiqueGuardTests(unittest.TestCase):
    def test_assembled_instruction_context_and_flag_free_guard(self):
        body = tool.assemble_body()
        md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
        md.detail = True
        instructions = list(md.disasm(body, tool.SIMULATION_CAVE))
        self.assertEqual([i.mnemonic for i in instructions], ["push", "vmov", "lsl.w", "cbnz", "vmov", "b", "vdiv.f32", "pop"])
        self.assertFalse(instructions[2].update_flags)
        self.assertEqual(instructions[6].bytes, tool.EXPECTED_DIVIDE)
        self.assertEqual(instructions[6].op_str, "s0, s0, s4")
        self.assertEqual(len(body), 24)

    def test_positive_denominator_bit_exact_original_and_register_flags(self):
        for fpscr in [0, 0x00400000, 0x01000000]:
            for numerator, denominator in [(0, 1), (300, 3), (1, 3), (65536, 7), (-35, 5), (123456, 0xffffffff)]:
                with self.subTest(numerator=numerator, denominator=denominator, fpscr=fpscr):
                    original = run(True, bits(numerator), bits(denominator), fpscr)
                    guarded = run(False, bits(numerator), bits(denominator), fpscr)
                    self.assertEqual(guarded, original, "positive case must preserve all float regs/FPSCR/APSR/PC and outside-scratch memory")

    def test_signed_zero_denominator_is_finite_positive_zero(self):
        for denominator in [0, 0x80000000]:
            for numerator in [0, bits(1), bits(-7), 0x7FC00000]:
                guarded = run(False, numerator, denominator)
                self.assertEqual(guarded["float_registers"][0], 0)
                self.assertTrue(math.isfinite(struct.unpack("<f", struct.pack("<I", guarded["float_registers"][0]))[0]))
                self.assertEqual(guarded["float_registers"][4], denominator)
                self.assertEqual(guarded["fpscr"], 0, "guard introduces no invalid/divide-by-zero exception")
                self.assertEqual(guarded["cpsr"], 0xA0000030)
                self.assertEqual(guarded["pc"], tool.RESUME_ELF)
        original = run(True, 0, 0)
        self.assertNotEqual(original["float_registers"][0], 0, "positive control executes original0/0 as NaN")

    def test_original_pins_plan_only_and_no_input_mutation(self):
        source = ROOT.parent / "Blustone-DataDump/local/inputs/extracted/lib/armeabi-v7a/libnative_core.so"
        if not source.is_file():
            self.skipTest("Immutable original binary is local evidence, not a public CI input")
        data = source.read_bytes()
        before = hashlib.sha256(data).hexdigest()
        result = tool.proposal(data)
        self.assertEqual(before, tool.ORIGINAL_SHA256)
        self.assertFalse(result["native_library_modified"])
        self.assertFalse(result["cave_proven"])
        self.assertEqual(result["status"], "PROPOSAL_ONLY_NO_CAVE_APPROVED")
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        changed = bytearray(data)
        changed[result["input"]["hook_file_offset"]] ^= 1
        with self.assertRaisesRegex(ValueError, "SHA256"):
            tool.proposal(bytes(changed))
        for address in [tool.HOOK_ELF, tool.CONTEXT_ELF - 2]:
            with self.assertRaisesRegex(ValueError, "overlaps"):
                tool.proposal(data, address)
        with self.assertRaisesRegex(ValueError, "aligned"):
            tool.proposal(data, tool.SIMULATION_CAVE + 1)

if __name__ == "__main__":
    unittest.main()
