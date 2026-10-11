#!/usr/bin/env python3
"""Prepare a bounded Thumb guard proposal; NEVER write a native library.

The original Boutique progress width divides by the next bonus target, which
can be zero for an unrecovered empty bonus catalogue. A proposal replaces only
that VDIV with B.W into an UNPROVEN cave and returns after it. Neither this tool
nor its tests approves a cave, integrates a patch, rebuilds an APK or installs it.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_SHA256 = "c4646ac3817b0008b6ea387fde9c8279fd439343ccc272acdc5883fab9d00eec"
KNOWN_RETAINED_COPY_SHA256 = "df49f1af3a4fdf3da5167446d9c6ffc19b3c7143588911cf92cbf6e24b3fdc16"
HOOK_ELF = 0x1041B50
RESUME_ELF = HOOK_ELF + 4
CONTEXT_ELF = 0x1041B3A
CONTEXT = bytes.fromhex("0a99039891ed1e1a02ee100ab8ee422a089821ee000a80ee020a8ded100ac96f11910168")
EXPECTED_DIVIDE = bytes.fromhex("80ee020a")
SIMULATION_CAVE = 0x200000  # Arbitrary emulator address; NOT a native cave.

def _branch_helpers():
    spec = importlib.util.spec_from_file_location("native_ui_branch_encoder", ROOT / "tools/patch-native-ui-animation.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.thumb_branch_w, module.decode_thumb_branch_w

def elf_file_offset(data: bytes, virtual: int, length: int) -> int:
    if data[:7] != b"\x7fELF\x01\x01\x01" or len(data) < 52:
        raise ValueError("Expected original little-endian ELF32 input")
    if struct.unpack_from("<H", data, 18)[0] != 40:
        raise ValueError("Expected original ARM library")
    phoff = struct.unpack_from("<I", data, 28)[0]
    entry_size, count = struct.unpack_from("<HH", data, 42)
    if entry_size < 32 or phoff + entry_size * count > len(data):
        raise ValueError("Malformed ELF program header table")
    for index in range(count):
        kind, offset, start, _, size, _, flags, _ = struct.unpack_from("<8I", data, phoff + index * entry_size)
        if kind == 1 and flags & 1 and start <= virtual and virtual + length <= start + size:
            result = offset + virtual - start
            if result + length > len(data):
                raise ValueError("Truncated original executable segment")
            return result
    raise ValueError("Hook context is outside original executable file bytes")

def inspect_input(data: bytes) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    if digest not in (ORIGINAL_SHA256, KNOWN_RETAINED_COPY_SHA256):
        raise ValueError("Unrecognized original/instrumented copy SHA256; do not relax the input pin")
    offset = elf_file_offset(data, CONTEXT_ELF, len(CONTEXT))
    if data[offset:offset + len(CONTEXT)] != CONTEXT:
        raise ValueError("Original Boutique register/context bytes changed")
    hook_offset = elf_file_offset(data, HOOK_ELF, 4)
    if data[hook_offset:hook_offset + 4] != EXPECTED_DIVIDE:
        raise ValueError("Original Boutique VDIV changed")
    return {"sha256": digest, "hook_file_offset": hook_offset, "context_file_offset": offset,
            "source_kind": "immutable_original" if digest == ORIGINAL_SHA256 else "retained_instrumented_copy",
            "installed_library_identity_verified": False}

def assemble_body() -> bytes:
    binary_dir = ROOT / "local/toolchains/android-sdk/ndk/29.0.14206865/toolchains/llvm/prebuilt/windows-x86_64/bin"
    clang, objcopy = binary_dir / "clang.exe", binary_dir / "llvm-objcopy.exe"
    if not clang.is_file() or not objcopy.is_file():
        raise ValueError("Pinned bundled ARM assembler unavailable")
    with tempfile.TemporaryDirectory(prefix="blustone-boutique-proposal-") as temporary:
        obj, output = Path(temporary) / "guard.o", Path(temporary) / "guard.bin"
        subprocess.run([str(clang), "--target=armv7a-none-eabi", "-mthumb", "-mfpu=neon", "-c",
                        str(ROOT / "tools/boutique-zero-width-guard.s"), "-o", str(obj)], check=True, capture_output=True)
        subprocess.run([str(objcopy), "--only-section=.text", "-O", "binary", str(obj), str(output)], check=True, capture_output=True)
        return output.read_bytes()

def proposal(data: bytes, cave: int = SIMULATION_CAVE) -> dict:
    source = inspect_input(data)
    if not isinstance(cave, int) or isinstance(cave, bool) or cave <= 0 or cave & 1:
        raise ValueError("Thumb proposal address must be a positive aligned integer")
    encode, decode = _branch_helpers()
    body = assemble_body()
    if cave < CONTEXT_ELF + len(CONTEXT) and cave + len(body) + 4 > CONTEXT_ELF:
        raise ValueError("Proposal cave overlaps original hook context")
    hook = encode(HOOK_ELF, cave)
    back = encode(cave + len(body), RESUME_ELF)
    if decode(HOOK_ELF, hook) != cave or decode(cave + len(body), back) != RESUME_ELF:
        raise ValueError("Proposal branch round-trip mismatch")
    return {"status": "PROPOSAL_ONLY_NO_CAVE_APPROVED", "native_library_modified": False,
            "apk_built_or_installed": False, "release_required_after_future_apk_rebuild": True,
            "input": source, "hook_elf": HOOK_ELF, "resume_elf": RESUME_ELF,
            "original_instruction_hex": EXPECTED_DIVIDE.hex(), "context_elf": CONTEXT_ELF,
            "context_hex": CONTEXT.hex(), "simulation_cave_elf": cave, "cave_proven": False,
            "hook_branch_hex": hook.hex(), "body_hex": body.hex(), "resume_branch_hex": back.hex(),
            "candidate_stub_hex": (body + back).hex(),
            "runtime_scratch": "temporary push/pop r2; no calls; SP/r2 restored",
            "guard": "signed-zero denominator -> positive finite0; otherwise exact original VDIV",
            "positive_case": "preserve GPRs, SP, LR, APSR, denominator/other VFP registers and original VDIV FPSCR behavior"}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Read-only pinned original or retained diagnostic copy")
    parser.add_argument("--simulation-cave", type=lambda value: int(value, 0), default=SIMULATION_CAVE)
    args = parser.parse_args()
    # stdout metadata only. No output-library argument or mutation API exists.
    print(json.dumps(proposal(args.input.read_bytes(), args.simulation_cave), indent=2))

if __name__ == "__main__":
    main()
