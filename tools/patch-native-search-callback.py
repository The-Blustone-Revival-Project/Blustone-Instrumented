"""Guard one Search Partner tutorial closure; instrumented copies only.
No guide flags, rewards, helper grants or scene transitions are synthesized.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
NEAR, CAVE = 0x612c9c, 0x210d380
HOOKS = ((0xe27420, "f0b503af", 0), (0xe27456, "211d02a8", 12), (0xe2749a, "02980121", 24))

def run(command):
    return subprocess.run(list(map(str, command)), check=True, text=True, capture_output=True).stdout

def apply(source, destination):
    original = ROOT / "analysis/extracted/lib/armeabi-v7a/libnative_core.so"
    if source.resolve() == original.resolve() or destination.resolve() == original.resolve():
        raise ValueError("Never modify the extracted original")
    data = bytearray(source.read_bytes())
    if data[:6] != b"\x7fELF\x01\x01": raise ValueError("Expected little-endian ELF32")
    phoff = struct.unpack_from("<I", data, 28)[0]
    phsize, count = struct.unpack_from("<HH", data, 42)
    loads = [(phoff+i*phsize, struct.unpack_from("<8I",data,phoff+i*phsize)) for i in range(count)]
    rx = [(off,p) for off,p in loads if p[0]==1 and p[1]==p[2]==0 and p[6]==5]
    if len(rx)!=1 or not 0x210d320 <= rx[0][1][4] <= CAVE: raise ValueError("Unexpected RX extent")
    for address, expected, _ in HOOKS:
        if data[address:address+4] != bytes.fromhex(expected): raise ValueError(f"Hook mismatch at {address:x}")
    out = ROOT / "analysis/patched/search-callback-guard"
    out.mkdir(parents=True, exist_ok=True)
    ndk = next((ROOT/"tools/android-sdk/ndk").glob("*/toolchains/llvm/prebuilt/windows-x86_64/bin"))
    obj = out/"guard.o"
    run([ndk/"clang.exe","--target=armv7a-linux-androideabi21","-mthumb","-fPIC","-nostdlib","-c",
         ROOT/"instrumentation/native/search-callback-guard.S","-o",obj])
    if run([ndk/"llvm-nm.exe","-u",obj]).strip() or "There are no relocations" not in run([ndk/"llvm-readelf.exe","-r",obj]):
        raise ValueError("Patch has unresolved symbols/relocations")
    symbols = run([ndk/"llvm-nm.exe","-n",obj])
    if "0000003c t guard_parent" not in symbols or "00000064 t guard_child" not in symbols:
        raise ValueError("Guard offsets changed; near literals require review")
    blobs=[]
    for section in ("search_near","search_guard"):
        file=out/(section+".bin")
        run([ndk/"llvm-objcopy.exe","-O","binary","--only-section=.text."+section,obj,file])
        blobs.append(file.read_bytes())
    near,cave=blobs
    if len(near)!=36 or not 0<len(cave)<=0x150: raise ValueError("Unexpected patch size")
    for offset, target in ((0,CAVE+1),(12,CAVE+0x3d),(24,CAVE+0x65)):
        actual = (NEAR+offset+8+struct.unpack_from("<I",near,offset+8)[0]) & 0xffffffff
        if actual != target: raise ValueError("Near pointer/Thumb state mismatch")
    spans=((NEAR,NEAR+len(near)),(CAVE,CAVE+len(cave)))
    shoff=struct.unpack_from("<I",data,32)[0]; shsize,shcount=struct.unpack_from("<HH",data,46)
    for lo,hi in spans:
        if any(data[lo:hi]): raise ValueError("Patch padding occupied")
        for i in range(shcount):
            section=struct.unpack_from("<10I",data,shoff+i*shsize)
            if section[1]!=8 and section[5] and max(lo,section[4])<min(hi,section[4]+section[5]):
                raise ValueError("Patch overlaps section")
        for off,p in loads:
            if p[0]==1 and off!=rx[0][0] and (max(lo,p[1])<min(hi,p[1]+p[4]) or max(lo,p[2])<min(hi,p[2]+p[5])):
                raise ValueError("Patch overlaps another load")
    spec=importlib.util.spec_from_file_location("patcher",ROOT/"tools/patch-native-ui-animation.py")
    patcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(patcher)
    for lo,hi in spans:
        if patcher.incoming_branch_targets(data,lo,hi): raise ValueError("Existing branch targets patch padding")
    for address,_,offset in HOOKS:
        branch=patcher.thumb_branch_w(address,NEAR+offset)
        if patcher.decode_thumb_branch_w(address,branch)!=NEAR+offset: raise ValueError("Hook branch mismatch")
        data[address:address+4]=branch
    data[NEAR:NEAR+len(near)]=near;data[CAVE:CAVE+len(cave)]=cave
    new_end=CAVE+len(cave)
    if (new_end+4095)//4096 != (rx[0][1][4]+4095)//4096: raise ValueError("RX mapping page changed")
    struct.pack_into("<II",data,rx[0][0]+16,new_end,new_end)
    destination.write_bytes(data)
    print(f"Search callback guard: near={len(near)} cave={len(cave)} RXend={new_end:x} sha256={hashlib.sha256(data).hexdigest()}")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path);parser.add_argument("destination",type=Path)
    args=parser.parse_args();apply(args.source,args.destination)
