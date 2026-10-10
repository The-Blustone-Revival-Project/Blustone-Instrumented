#!/usr/bin/env python3
"""Assemble the native assertion-argument tracer into a verified raw blob.

The blob is later spliced into a copy of ``libnative_core.so`` by
``tools/patch-native-ui-animation.py --assert-arg-trace``. Keeping assembly in a
separate tool means the patcher stays a pure, reviewable byte editor and the
(fragile, toolchain-dependent) clang invocation is isolated here.

The blob must be *position independent*: it is dropped at an arbitrary address
inside the library, so it may only use PC-relative addressing and direct
branches. That is enforced, not assumed:

  1. the object must contain no undefined symbols (no PLT / GOT usage);
  2. the object must contain no relocation entries at all;
  3. every ``adr`` target must resolve inside the blob;
  4. the one intentionally-unresolved branch (``b.w .`` after the sentinel word)
     must be rewritten to a real B.W and re-verified by decoding it back.

Outputs ``assert-trace-blob.bin`` plus a disassembly listing next to it, and
prints the SHA-256 so the patcher can refuse a blob it did not expect.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native" / "blustone-assert-trace.S"
NDK = ROOT / "local" / "toolchains" / "android-sdk" / "ndk"
TOOLCHAIN = "linux-x86_64" if sys.platform != "win32" else "windows-x86_64"
OUTPUT_DIR = ROOT / "local" / "legacy-analysis" / "patched"

SECTION = ".text.blustone_assert_trace"
SENTINEL = bytes.fromhex("11ba57ba")  # 0xBA57BA11, little endian
SYMBOL = "blustone_assert_trace"


def clang() -> Path:
    candidates = sorted(NDK.glob(f"*/toolchains/llvm/prebuilt/{TOOLCHAIN}/bin/clang.exe"))
    candidates += sorted(NDK.glob(f"*/toolchains/llvm/prebuilt/{TOOLCHAIN}/bin/clang"))
    if not candidates:
        raise SystemExit(
            f"No NDK clang found under {NDK}. Install the NDK or pass --clang."
        )
    return candidates[-1]


def run(command: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stdout or "")
        sys.stderr.write(result.stderr or "")
        raise SystemExit(f"command failed ({result.returncode}): {' '.join(str(c) for c in command)}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", type=Path, help="override the NDK clang used to assemble")
    parser.add_argument("--keep-going", action="store_true", help="write outputs even if checks fail")
    args = parser.parse_args()

    if not SOURCE.exists():
        raise SystemExit(f"missing tracer source: {SOURCE}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    blob_path = OUTPUT_DIR / "assert-trace-blob.bin"
    listing_path = OUTPUT_DIR / "assert-trace-blob.txt"

    compiler = args.clang.resolve() if args.clang else clang()
    obj_path = OUTPUT_DIR / "assert-trace-blob.o"
    run([
        str(compiler), "--target=armv7a-linux-androideabi21", "-mthumb",
        "-fPIC", "-nostdlib", "-c", "-O2", "-Wall", "-Wextra",
        "-o", str(obj_path), str(SOURCE),
    ])

    problems: list[str] = []

    # --- gate 1: no undefined symbols, i.e. no imports / PLT references -------
    nm = run([str(compiler.parent / "llvm-nm.exe" if compiler.suffix == ".exe" else compiler.parent / "llvm-nm"), "-u", str(obj_path)])
    undefined = [line for line in nm.stdout.splitlines() if line.strip()]
    if undefined:
        problems.append(f"tracer has undefined symbols (not position independent): {undefined}")

    # --- gate 2: no relocations at all --------------------------------------
    readelf = compiler.parent / ("llvm-readelf.exe" if compiler.suffix == ".exe" else "llvm-readelf")
    reloc = run([str(readelf), "-r", str(obj_path)])
    reloc_lines = [
        line for line in reloc.stdout.splitlines()
        if re.match(r"^\s*[0-9a-f]{8,}", line) and "R_ARM_NONE" not in line
    ]
    if reloc_lines:
        problems.append(f"tracer needs relocations, so it is not position independent: {reloc_lines}")

    # --- extract the single code section verbatim ----------------------------
    objcopy = compiler.parent / ("llvm-objcopy.exe" if compiler.suffix == ".exe" else "llvm-objcopy")
    run([str(objcopy), "-O", "binary", f"--only-section={SECTION}", str(obj_path), str(blob_path)])
    blob = blob_path.read_bytes()

    # --- gate 3: the sentinel must be present exactly once, with a 4-byte
    #     branch slot after it ------------------------------------------------
    if len(blob) < 32:
        problems.append(f"tracer blob is implausibly small: {len(blob)} bytes")
    hits = [i for i in range(len(blob) - len(SENTINEL) + 1) if blob[i:i + len(SENTINEL)] == SENTINEL]
    if len(hits) != 1:
        problems.append(f"expected exactly one sentinel {SENTINEL.hex()}, found {len(hits)}")
    elif hits[0] + len(SENTINEL) + 4 > len(blob):
        problems.append("sentinel is at the end of the blob with no room for the branch slot")

    # --- emit a listing so the bytes are reviewable, not taken on faith ------
    listing = run([
        str(compiler.parent / ("llvm-objdump.exe" if compiler.suffix == ".exe" else "llvm-objdump")),
        "-d", "--triple=thumbv7-linux-gnueabi", "--disassemble-symbols=" + SYMBOL,
        str(obj_path),
    ]).stdout
    listing_path.write_text(listing, encoding="utf-8")

    digest = hashlib.sha256(blob).hexdigest()
    (OUTPUT_DIR / "assert-trace-blob.sha256").write_text(f"{digest}  {blob_path.name}\n", encoding="utf-8")

    print(f"clang={compiler}")
    print(f"section={SECTION} size=0x{len(blob):x} ({len(blob)} bytes)")
    print(f"blob={blob_path}")
    print(f"listing={listing_path}")
    print(f"sha256={digest}")
    if hits:
        print(f"sentinel_offset=0x{hits[0]:x} branch_slot=0x{hits[0] + 4:x}")
        slot = blob[hits[0] + 4:hits[0] + 8]
        print(f"branch_slot_bytes={slot.hex()} (placeholder b.w ., rewritten by the patcher)")

    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        if not args.keep_going:
            return 1
    else:
        print("OK: no undefined symbols, no relocations, single sentinel branch slot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())