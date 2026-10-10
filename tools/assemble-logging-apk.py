"""Preserve the known-working APK; replace only classes.dex from the logging build."""
from pathlib import Path
from zipfile import ZipFile
import sys

base = Path("analysis/patched")
source = base / "blustone-local-replica-debug-copy-signed.apk"
compiled = base / "blustone-local-logging-unsigned.apk"
probe = "--probe" in sys.argv
target = base / ("blustone-local-probe-unsigned.apk" if probe else "blustone-local-logging-preserved-unsigned.apk")
with ZipFile(source) as original, ZipFile(compiled) as rebuilt, ZipFile(target, "w") as output:
    for entry in original.infolist():
        if entry.filename.startswith("META-INF/") and entry.filename.endswith((".SF", ".RSA", ".MF")):
            continue
        archive = rebuilt if entry.filename == "classes.dex" else original
        output.writestr(entry, archive.read(entry.filename))
    if probe:
        output.write(base / "libblustone_trace.so", "lib/armeabi-v7a/libblustone_trace.so")
with ZipFile(source) as original, ZipFile(target) as result:
    changed = [entry.filename for entry in result.infolist()
               if entry.filename in original.namelist() and original.getinfo(entry.filename).CRC != entry.CRC]
    assert changed == ["classes.dex"], changed
    assert set(result.namelist()) - set(original.namelist()) == ({"lib/armeabi-v7a/libblustone_trace.so"} if probe else set())
print(target)
