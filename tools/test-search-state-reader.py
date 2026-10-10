"""Host-only reader bounds/compile and fixed public-resource fingerprint checks.
No app launch, live memory, state file or account data access.
"""
from pathlib import Path
import hashlib
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sdk = ROOT / "tools/android-sdk"
android = sorted((sdk / "platforms").glob("*/android.jar"))[-1]
jdk = next((ROOT / "tools/jdk").glob("jdk-*/bin"))
source = ROOT / "instrumentation/src/EpisodeResourceSnapshot.java"
assets = ROOT / "recovered-assets/phone-2026-09-18/extracted/split_PADResource/assets"
rows = re.findall(r'\{"([A-Za-z0-9_.-]+\.jet)","(\d+)","([0-9a-f]{64})"\}', source.read_text())
expected = {"R_EPISODE.jet", "EPISODE.jet", "DIAL-EN.jet", "N001_BG.jet", "ST099.jet", "SND1.jet", "SND_CDN.jet",
            "VOICE_CDN2.jet", "VOICE_CDN6.jet", "C009.jet", "C009_Q.jet", "C009_EFT.jet", "C009_SND.jet"}
assert len(rows) == 13 and {row[0] for row in rows} == expected
for name, size, digest in rows:
    original = assets / name
    assert original.stat().st_size == int(size), name
    with original.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == digest, name

harness = '''package com.vshower.instrumented;
import java.lang.reflect.*;
public class SearchReaderBounds {
  static Method count;
  static void valid(long[] range,int stride,int limit,int expected) throws Exception {
    if(((Integer)count.invoke(null,new Object[]{range,stride,limit})).intValue()!=expected)throw new AssertionError();
  }
  static void invalid(long[] range,int stride,int limit) throws Exception {
    try {count.invoke(null,new Object[]{range,stride,limit});throw new AssertionError("Accepted malformed range");}
    catch(InvocationTargetException failure){if(!(failure.getCause() instanceof IllegalStateException))throw failure;}
  }
  public static void main(String[] args) throws Exception {
    count=NativeGymSnapshot.class.getDeclaredMethod("vectorCount",long[].class,int.class,int.class);count.setAccessible(true);
    valid(new long[]{0,0},28,8,0);valid(new long[]{4096,4096+28},28,8,1);
    valid(new long[]{4096,4096+8*28},28,8,8);valid(new long[]{4096,4096+32*56},56,32,32);
    invalid(new long[]{4097,4097+28},28,8);invalid(new long[]{4096,4092},28,8);
    invalid(new long[]{4096,4096+29},28,8);invalid(new long[]{4096,4096+9*28},28,8);
    invalid(new long[]{0,28},28,8);invalid(new long[]{4096,4096+33*56},56,32);
    invalid(new long[]{4096},28,8);invalid(new long[]{4096,4096,4096},28,8);
    System.out.println("Reader compile, four valid ranges and eight malformed-range refusals passed; no runtime/memory claim.");
  }
}'''
with tempfile.TemporaryDirectory(prefix="search-reader-check-", dir=ROOT / "local" / "legacy-analysis") as temporary:
    folder = Path(temporary).resolve()
    assert folder.is_relative_to((ROOT / "local" / "legacy-analysis").resolve())
    java = folder / "SearchReaderBounds.java"
    java.write_text(harness)
    sources = [ROOT / "instrumentation/src/NativeGymSnapshot.java", source, java]
    subprocess.run([str(jdk / "javac.exe"), "-cp", str(android), "-d", str(folder), *map(str, sources)], check=True)
    subprocess.run([str(jdk / "java.exe"), "-cp", f"{folder};{android}", "com.vshower.instrumented.SearchReaderBounds"], check=True)
print("All 13 fixed Episode resource size/SHA256 pins match original local public JETs.")
