"""Guarded interrupted-Gym recovery, applied ONLY to an instrumented .so copy.

No original bytes/files are changed. The original branch remains equivalent
unless TU8/nextA8 and completed8/0 have pending8/1. Reuses TutorialNPC constructor
without clearing flags or jumping to selection. ELF constants are VA=file
offset in the first RX PT_LOAD; Ghidra addresses are VA+0x10000.
"""
from pathlib import Path
import argparse
import hashlib
import struct
import subprocess
import sys
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
HOOK, NEAR, CAVE = 0xea25f0, 0x612c90, 0x210d320
EXPECTED = bytes.fromhex("012800f39880")

def run(command):
    return subprocess.run(list(map(str, command)), check=True, text=True, capture_output=True).stdout

def apply(source: Path, destination: Path):
    original = ROOT / "analysis/extracted/lib/armeabi-v7a/libnative_core.so"
    if source.resolve() == original.resolve() or destination.resolve() == original.resolve():
        raise ValueError("Input/output must be instrumented copies, never extracted original")
    data = bytearray(source.read_bytes())
    if data[:5] != b"\x7fELF\x01" or data[5] != 1: raise ValueError("Expected ELF32 little endian")
    phoff = struct.unpack_from("<I", data, 28)[0]
    phsize, phcount = struct.unpack_from("<HH", data, 42)
    loads = [(phoff+i*phsize, struct.unpack_from("<8I", data, phoff+i*phsize)) for i in range(phcount)]
    rx = [(off, p) for off, p in loads if p[0] == 1 and p[1] == p[2] == 0 and p[6] == 5]
    if len(rx) != 1 or rx[0][1][4:6] != (CAVE, CAVE): raise ValueError("Unexpected RX segment extent")
    if bytes(data[HOOK:HOOK+6]) != EXPECTED: raise ValueError("Original CMP/BGT does not match")
    if any(data[NEAR:0x612cc0]) or any(data[CAVE:0x210d550]): raise ValueError("Padding is not empty")
    # Neither chosen padding span belongs to a section or overlaps another load.
    shoff = struct.unpack_from("<I",data,32)[0]
    shsize, shcount = struct.unpack_from("<HH",data,46)
    for i in range(shcount):
        s = struct.unpack_from("<10I",data,shoff+i*shsize)
        if s[1] == 8 or s[5] == 0: continue
        for lo,hi in [(NEAR,0x612cc0),(CAVE,0x210d550)]:
            if max(lo,s[4]) < min(hi,s[4]+s[5]): raise ValueError("Padding overlaps an ELF section")
    out = ROOT / "analysis/patched/gym-resume"
    out.mkdir(parents=True, exist_ok=True)
    ndk = next((ROOT / "tools/android-sdk/ndk").glob("*/toolchains/llvm/prebuilt/windows-x86_64/bin"))
    obj = out / "gym-resume.o"
    run([ndk/"clang.exe", "--target=armv7a-linux-androideabi21", "-mthumb", "-fPIC", "-nostdlib", "-c",
         ROOT/"instrumentation/native/gym-resume.S", "-o", obj])
    if run([ndk/"llvm-nm.exe", "-u", obj]).strip(): raise ValueError("Undefined assembly symbols")
    reloc = run([ndk/"llvm-readelf.exe", "-r", obj])
    if "There are no relocations" not in reloc: raise ValueError("Assembly contains relocations")
    blobs=[]
    for section in ["gym_near", "gym_resume"]:
        path=out/(section+".bin")
        run([ndk/"llvm-objcopy.exe", "-O", "binary", "--only-section=.text."+section, obj, path])
        blobs.append(path.read_bytes())
    near,cave=blobs
    if not (0<len(near)<=0x30 and 0<len(cave)<=0x230): raise ValueError("Patch exceeds verified padding")
    spec=importlib.util.spec_from_file_location("native_ui_patcher", ROOT/"tools/patch-native-ui-animation.py")
    patcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(patcher)
    if patcher.incoming_branch_targets(data,NEAR,NEAR+len(near)) or patcher.incoming_branch_targets(data,CAVE,CAVE+len(cave)):
        raise ValueError("Existing direct text branch targets new code padding")
    hook=patcher.thumb_branch_w(HOOK,NEAR)
    if patcher.decode_thumb_branch_w(HOOK,hook)!=NEAR: raise ValueError("Invalid near branch")
    # Expanding RX within its already mapped final page leaves RW addresses,
    # relocations and section offsets untouched; next RW VA starts0x210e550.
    new_end=CAVE+len(cave)
    if ((new_end+0xfff)&~0xfff) != ((CAVE+0xfff)&~0xfff): raise ValueError("RX page mapping changes")
    for off,p in loads:
        if p[0]!=1 or off==rx[0][0]: continue
        for lo,hi in [(NEAR,NEAR+len(near)),(CAVE,new_end)]:
            if max(lo,p[1])<min(hi,p[1]+p[4]) or max(lo,p[2])<min(hi,p[2]+p[5]):
                raise ValueError("New code overlaps another PT_LOAD file/VA span")
    data[HOOK:HOOK+6]=hook+b"\x00\xbf"
    data[NEAR:NEAR+len(near)]=near;data[CAVE:new_end]=cave
    struct.pack_into("<II",data,rx[0][0]+16,new_end,new_end)
    destination.write_bytes(data)
    print(f"Gym recovery copy: hook={HOOK:x}, near={len(near)}, cave={len(cave)}, RXend={new_end:x}, sha256={hashlib.sha256(data).hexdigest()}")

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path);parser.add_argument("destination",type=Path)
    args=parser.parse_args();apply(args.source,args.destination)
