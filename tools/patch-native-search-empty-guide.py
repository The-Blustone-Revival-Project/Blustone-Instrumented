"""Candidate-only fresh empty-helper guide deferral; never edits original ELF.
No guide flags, helper usage, rewards or scene transitions are written.
"""
from pathlib import Path
import hashlib
import importlib.util
import struct
import subprocess
import argparse
import re

ROOT = Path(__file__).resolve().parents[1]
ENTRY, CAVE, LIMIT = 0xe1ffe4, 0x210d404, 0x210d550
EXPECTED = bytes.fromhex("f0b503af2de9000fafb00546")

def run(command):
    return subprocess.run(list(map(str, command)), check=True, capture_output=True, text=True).stdout

def apply(source, destination):
    original = ROOT / "analysis/extracted/lib/armeabi-v7a/libnative_core.so"
    if original.resolve() in (source.resolve(), destination.resolve()):
        raise ValueError("Never modify the extracted original")
    data = bytearray(source.read_bytes())
    if data[:6] != b"\x7fELF\x01\x01" or data[ENTRY:ENTRY+12] != EXPECTED:
        raise ValueError("Original entry/ELF mismatch")
    phoff=struct.unpack_from("<I",data,28)[0]; phsize, count=struct.unpack_from("<HH",data,42)
    loads=[(phoff+i*phsize,struct.unpack_from("<8I",data,phoff+i*phsize)) for i in range(count)]
    rx=[(off,p) for off,p in loads if p[0]==1 and p[1]==p[2]==0 and p[6]==5]
    if len(rx)!=1 or rx[0][1][4]!=CAVE or rx[0][1][5]!=CAVE:
        raise ValueError("Requires reviewed prior Search guard extent")
    ndk=next((ROOT/"tools/android-sdk/ndk").glob("*/toolchains/llvm/prebuilt/windows-x86_64/bin"))
    folder=ROOT/"analysis/patched/search-empty-guide"; folder.mkdir(parents=True,exist_ok=True)
    obj=folder/"guard.o"
    run([ndk/"clang.exe","--target=armv7a-linux-androideabi21","-mthumb","-fPIC","-nostdlib","-c",
         ROOT/"instrumentation/native/search-empty-guide-guard.S","-o",obj])
    if run([ndk/"llvm-nm.exe","-u",obj]).strip() or "There are no relocations" not in run([ndk/"llvm-readelf.exe","-r",obj]):
        raise ValueError("Unresolved symbols/relocations")
    blobs=[]
    for section in ("empty_guide_entry","empty_guide_guard"):
        file=folder/(section+".bin")
        run([ndk/"llvm-objcopy.exe","-O","binary","--only-section=.text."+section,obj,file]); blobs.append(file.read_bytes())
    veneer,cave=blobs
    if len(veneer)!=12 or not 0<len(cave)<=LIMIT-CAVE: raise ValueError("Patch size")
    if (ENTRY+8+struct.unpack_from("<I",veneer,8)[0])&0xffffffff != CAVE+1:
        raise ValueError("Entry Thumb/PIC target")
    end=CAVE+len(cave)
    if any(data[CAVE:end]): raise ValueError("Padding occupied")
    shoff=struct.unpack_from("<I",data,32)[0]; shsize,shcount=struct.unpack_from("<HH",data,46)
    for i in range(shcount):
        s=struct.unpack_from("<10I",data,shoff+i*shsize)
        if s[1]!=8 and s[5] and max(CAVE,s[4])<min(end,s[4]+s[5]): raise ValueError("Section overlap")
    for off,p in loads:
        if p[0]==1 and off!=rx[0][0] and (max(CAVE,p[1])<min(end,p[1]+p[4]) or max(CAVE,p[2])<min(end,p[2]+p[5])):
            raise ValueError("Load overlap")
    spec=importlib.util.spec_from_file_location("ui_patcher",ROOT/"tools/patch-native-ui-animation.py")
    helper=importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    interior=helper.incoming_branch_targets(data,ENTRY+2,ENTRY+12)
    # The legacy halfword scan decodes D20C at e1ffca as a 16-bit branch.
    # It is actually the SECOND halfword of the proven 32-bit BL at e1ffc8.
    # Require exact source bytes AND independent decoder confirmation; refuse
    # every other interior hit. No executable incoming branch is exempted.
    false_halfword=(0xe1ffca,0xe1ffe6)
    if false_halfword in interior:
        listing=run([ndk/"llvm-objdump.exe","-d","--triple=thumbv7-linux-android",
                     "--start-address=14811080","--stop-address=14811084",source])
        if data[0xe1ffc8:0xe1ffcc]!=bytes.fromhex("b1f10cd2") or not re.search(r"e1ffc8:\s+f1b1\s+d20c\s+bl\s+0x1bd13e4",listing):
            raise ValueError("Unproved scanner halfword classification")
        interior.remove(false_halfword)
    if helper.incoming_branch_targets(data,CAVE,end) or interior:
        raise ValueError("Incoming branch into overwritten interior/padding")
    if (end+4095)//4096 != (CAVE+4095)//4096: raise ValueError("RX page count changed")
    data[ENTRY:ENTRY+12]=veneer;data[CAVE:end]=cave
    struct.pack_into("<II",data,rx[0][0]+16,end,end)
    destination.write_bytes(data)
    print(f"Fresh empty-guide candidate: cave={len(cave)} RXend={end:x} sha256={hashlib.sha256(data).hexdigest()}")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("source",type=Path);parser.add_argument("destination",type=Path)
    args=parser.parse_args();apply(args.source,args.destination)
