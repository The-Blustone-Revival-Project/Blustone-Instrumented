"""Context-specific actual Thumb/VFP tests; proposal only, no library writes."""
import hashlib
import importlib.util
import struct
import unittest
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB
from unicorn.arm_const import *

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("boutique_u32", ROOT / "tools/prepare-boutique-zero-width-guard-u32.py")
assert spec and spec.loader
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

def bits(value):
    return struct.unpack("<I", struct.pack("<f", value))[0]

def emulate(guarded, count, target, fpscr=0, bias=0):
    machine = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    hook, cave, resume = tool.HOOK + bias, tool.CAVE + bias, tool.RESUME + bias
    begin = 0x1041B46 + bias
    machine.mem_map(hook & ~0xFFF, 0x1000)
    machine.mem_map(cave & ~0xFFF, 0x1000)
    machine.mem_map(0x4000000, 0x1000)
    stack = 0x4000800
    machine.mem_write(0x4000000, b"\xA5" * 0x1000)
    machine.reg_write(UC_ARM_REG_C1_C0_2, 0x00F00000)
    machine.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
    machine.reg_write(UC_ARM_REG_CPSR, 0xA0000030)
    for index in range(13):
        machine.reg_write(globals()[f"UC_ARM_REG_R{index}"], 0x12345670 + index)
    machine.reg_write(UC_ARM_REG_SP, stack)
    machine.reg_write(UC_ARM_REG_LR, 0x55667789)
    for index in range(32):
        machine.reg_write(globals()[f"UC_ARM_REG_S{index}"], bits(50 + index))
    machine.reg_write(UC_ARM_REG_S0, bits(count))
    machine.reg_write(UC_ARM_REG_S2, bits(600))
    machine.reg_write(UC_ARM_REG_S4, target)
    machine.reg_write(UC_ARM_REG_FPSCR, fpscr)
    # Original context: U32 conversion, unchanged drawable load and width*count.
    context = tool.generic.CONTEXT[0x1041B46 - tool.generic.CONTEXT_ELF:tool.HOOK - tool.generic.CONTEXT_ELF]
    machine.mem_write(begin, context)
    if guarded:
        body = tool.assemble_body()
        encode, _ = tool.generic._branch_helpers()
        machine.mem_write(hook, encode(hook, cave))
        machine.mem_write(cave, body + encode(cave + len(body), resume))
    else:
        machine.mem_write(hook, tool.generic.EXPECTED_DIVIDE)
    machine.emu_start(begin | 1, resume, count=50)
    return {"gpr": [machine.reg_read(globals()[f"UC_ARM_REG_R{i}"]) for i in range(13)],
            "sp": machine.reg_read(UC_ARM_REG_SP), "lr": machine.reg_read(UC_ARM_REG_LR),
            "fp": [machine.reg_read(globals()[f"UC_ARM_REG_S{i}"]) for i in range(32)],
            "fpscr": machine.reg_read(UC_ARM_REG_FPSCR), "cpsr": machine.reg_read(UC_ARM_REG_CPSR),
            "pc_relative": machine.reg_read(UC_ARM_REG_PC) - bias,
            "outside_scratch": bytes(machine.mem_read(0x4000000, 0x7FC)) + bytes(machine.mem_read(stack, 0x800))}

class BoutiqueU32GuardTests(unittest.TestCase):
    def test_20_byte_body_and_pinned_unsigned_context(self):
        body = tool.assemble_body()
        md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
        instructions = list(md.disasm(body, tool.CAVE))
        self.assertEqual(len(body), 20)
        self.assertEqual([i.mnemonic for i in instructions], ["push", "vmov", "cbnz", "vmov", "b", "vdiv.f32", "pop"])
        self.assertEqual(instructions[5].bytes, tool.generic.EXPECTED_DIVIDE)
        context = list(md.disasm(tool.generic.CONTEXT[12:16], 0x1041B46))
        self.assertEqual(context[0].mnemonic, "vcvt.f32.u32")
        self.assertEqual(context[0].op_str, "s4, s4")

    def test_reachable_positive_cases_exact_with_actual_conversion_and_aslr(self):
        for bias in [0, 0x10000000]:
            for fpscr in [0, 0x00400000, 0x01000000]:
                for count, target in [(0, 1), (1, 3), (3, 3), (7, 11), (5, 0x7FFFFFFF), (10, 0xFFFFFFFF)]:
                    with self.subTest(bias=bias, fpscr=fpscr, target=target):
                        self.assertEqual(emulate(True, count, target, fpscr, bias), emulate(False, count, target, fpscr, bias))

    def test_actual_unsigned_zero_is_finite_width_zero(self):
        for count in [0, 1, 8]:
            result = emulate(True, count, 0)
            baseline = emulate(False, count, 0)
            self.assertEqual(result["fp"][0], 0)
            self.assertEqual(result["fp"][4], 0, "actual UInt conversion cannot produce negative zero")
            self.assertEqual(result["gpr"], baseline["gpr"])
            self.assertEqual(result["sp"], baseline["sp"])
            self.assertEqual(result["lr"], baseline["lr"])
            self.assertEqual(result["cpsr"], baseline["cpsr"])
            self.assertEqual(result["fpscr"], 0)
            self.assertNotEqual(result["fp"][0], baseline["fp"][0])

    def test_current_artifact_static_padding_gates_no_mutation(self):
        source = ROOT / "local/legacy-analysis/patched/libnative_core-ui-ma-bypass.so"
        if not source.is_file():
            self.skipTest("Current retained native artifact is local evidence")
        data = source.read_bytes()
        before = hashlib.sha256(data).hexdigest()
        result = tool.proposal(data)
        self.assertEqual(before, tool.CURRENT_ARTIFACT_SHA256)
        self.assertFalse(result["native_library_modified"])
        self.assertFalse(result["cave_proven_for_live_execution"])
        self.assertFalse(result["negative_zero_protection"])
        self.assertEqual(len(bytes.fromhex(result["candidate_stub_hex"])), 24)
        self.assertEqual(result["placement"]["direct_branch_refs"], [])
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        wrong = bytearray(data)
        wrong[tool.CAVE] = 1
        with self.assertRaisesRegex(ValueError, "SHA256"):
            tool.proposal(bytes(wrong))

if __name__ == "__main__":
    unittest.main()
