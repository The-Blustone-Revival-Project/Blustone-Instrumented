"""Build the side-by-side BLUSTONE - Instrumented APK.

The preserved working APK remains the source of native code and assets. Only
the diagnostic manifest, diagnostic dex, secondary telemetry dex, and local
crash-probe library are selected into the new package.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
PATCHED = ROOT / "local" / "legacy-analysis" / "patched"
DEBUG_SMALI = PATCHED / "debug-smali"
BASE_APK = PATCHED / "blustone-local-replica-debug-copy-signed.apk"
TRACE_SO = PATCHED / "libblustone_trace.so"
NATIVE_CORE_OVERRIDE = PATCHED / "libnative_core-ui-ma-bypass.so"
APKTOOL = ROOT / "local" / "toolchains" / "apktool" / "apktool_3.0.3.jar"
AAPT2 = ROOT / "local" / "toolchains" / "android-sdk" / "build-tools" / "37.0.0" / "aapt2.exe"
ZIPALIGN = ROOT / "local" / "toolchains" / "android-sdk" / "build-tools" / "37.0.0" / "zipalign.exe"
APKSIGNER = ROOT / "local" / "toolchains" / "android-sdk" / "build-tools" / "37.0.0" / "apksigner.bat"
ANDROID_JAR = ROOT / "local" / "toolchains" / "android-sdk" / "platforms" / "android-33" / "android.jar"
JAVAC = ROOT / "local" / "toolchains" / "jdk" / "jdk-21.0.12.1+1" / "bin" / "javac.exe"
JAVA = ROOT / "local" / "toolchains" / "jdk" / "jdk-21.0.12.1+1" / "bin" / "java.exe"
D8 = ROOT / "local" / "toolchains" / "android-sdk" / "build-tools" / "37.0.0" / "d8.bat"
SOURCES = ROOT / "src"
STUBS = ROOT / "stubs"
EXTRA_ASSETS = ROOT / "assets"
OUTPUT_DIR = ROOT / "local" / "build" / "instrumented-apk"
BUILD_DIR = OUTPUT_DIR / "build"
KEYSTORE = Path(os.environ.get("BLUSTONE_SIGNING_KEY", str(ROOT / "local" / "private" / "blustone-instrumented.jks")))
KEY_ALIAS = "blustone-instrumented"
KEY_PASSWORD = "blustone-instrumented"


def run(command: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(str(part) for part in command))
    if command[0].lower().endswith((".bat", ".cmd")):
        command = ["cmd.exe", "/d", "/s", "/c", *command]
    subprocess.run(command, cwd=cwd or ROOT, check=True)


def require(paths: list[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing build inputs:\n" + "\n".join(missing))


def assemble_apk(rebuilt: Path, telemetry_dex: Path, unsigned: Path) -> None:
    with ZipFile(BASE_APK, "r") as original, ZipFile(rebuilt, "r") as rebuilt_zip, ZipFile(unsigned, "w") as output:
        replacement_manifest = rebuilt_zip.read("AndroidManifest.xml")
        replacement_game_dex = rebuilt_zip.read("classes.dex")
        for entry in original.infolist():
            if entry.filename.startswith("META-INF/") and entry.filename.endswith((".SF", ".RSA", ".MF")):
                continue
            if entry.filename == "AndroidManifest.xml":
                output.writestr(entry, replacement_manifest)
            elif entry.filename == "classes.dex":
                output.writestr(entry, replacement_game_dex)
            elif entry.filename in {"classes2.dex", "lib/armeabi-v7a/libblustone_trace.so"}:
                continue
            elif entry.filename == "lib/armeabi-v7a/libnative_core.so" and NATIVE_CORE_OVERRIDE.exists():
                # Instrumented-only fallback for the BlueStacks UI_MA_L1 video
                # animation crash. The original APK and native library remain
                # unchanged; the override is a separately generated copy.
                output.writestr(entry, NATIVE_CORE_OVERRIDE.read_bytes())
            else:
                output.writestr(entry, original.read(entry.filename))
        classes2 = ZipInfo("classes2.dex")
        classes2.compress_type = ZIP_DEFLATED
        output.writestr(classes2, telemetry_dex.read_bytes())
        trace = ZipInfo("lib/armeabi-v7a/libblustone_trace.so")
        trace.compress_type = ZIP_DEFLATED
        output.writestr(trace, TRACE_SO.read_bytes())
        if EXTRA_ASSETS.exists():
            for asset in sorted(EXTRA_ASSETS.rglob("*")):
                if not asset.is_file():
                    continue
                archive_name = "assets/" + asset.relative_to(EXTRA_ASSETS).as_posix()
                if archive_name in output.namelist():
                    raise RuntimeError(f"Diagnostic asset collides with APK entry: {archive_name}")
                extra = ZipInfo(archive_name)
                extra.compress_type = ZIP_DEFLATED
                contents = asset.read_bytes()
                if asset.name == "CURRENT":
                    match = re.fullmatch(rb"(MANIFEST-[0-9]+)\r?\n", contents)
                    if match is None or not (asset.parent / match[1].decode("ascii")).is_file():
                        raise RuntimeError(f"Invalid LevelDB CURRENT or missing manifest: {asset}")
                    contents = match[1] + b"\n"
                output.writestr(extra, contents)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true", help="install only the instrumented package on 127.0.0.1:5555")
    parser.add_argument("--resume-interrupted-gym", action="store_true",
        help="Instrumented-only guarded original TutorialNPC reentry for completed8/0 with pending8/1; no state or direct-scene change")
    parser.add_argument(
        "--restore-pre-repair-cdn",
        action="store_true",
        help=(
            "A/B diagnostic: on every launch, replace files/local/CDN.db with the "
            "pre-repair snapshot instead of letting the native CDN manager keep "
            "the index it wrote last session. Off by default because the fixed "
            "snapshot can pin the client in a mid-download state."
        ),
    )
    parser.add_argument(
        '--keep-asserts',
        action='store_true',
        help='Rebuild the native library with the game assertion machinery left live.',
    )
    parser.add_argument(
        '--assert-log-continue',
        action='store_true',
        help='Keep the native assertion reporter but do not exit on failure.',
    )
    parser.add_argument(
        '--assert-arg-trace',
        action='store_true',
        help=(
            'Plant a freestanding Thumb stub at the entry of _RMAssert that prints the '
            'failing call site and the assertion argument words to stderr before '
            're-entering the untouched reporter. Requires --assert-log-continue or '
            '--keep-asserts.'
        ),
    )
    args = parser.parse_args()

    # The native library is produced by the patcher, not by this script. Run it
    # here so the build flags below produce a coherent library instead of
    # silently reusing whatever was left over from a previous build.
    native_source = ROOT / 'local' / 'legacy-analysis' / 'extracted' / 'lib' / 'armeabi-v7a' / 'libnative_core.so'
    if args.assert_arg_trace:
        # The tracer stub is assembled separately so the patcher stays a pure byte
        # editor; the blob builder is what enforces "no imports, no relocations".
        run([sys.executable, str(ROOT / 'tools' / 'build-assert-trace-blob.py')])
    if native_source.exists():
        patcher = ROOT / 'tools' / 'patch-native-ui-animation.py'
        cmd = [sys.executable, str(patcher), str(native_source), str(NATIVE_CORE_OVERRIDE)]
        if args.keep_asserts:
            cmd.append('--keep-asserts')
        if args.assert_log_continue:
            cmd.append('--assert-log-continue')
        if args.assert_arg_trace:
            cmd.append('--assert-arg-trace')
        run(cmd)
        if args.resume_interrupted_gym:
            run([sys.executable, str(ROOT / 'tools' / 'patch-native-gym-resume.py'),
                 str(NATIVE_CORE_OVERRIDE), str(NATIVE_CORE_OVERRIDE)])
        run([sys.executable, str(ROOT / 'tools' / 'patch-native-search-callback.py'),
             str(NATIVE_CORE_OVERRIDE), str(NATIVE_CORE_OVERRIDE)])
        run([sys.executable, str(ROOT / 'tools' / 'patch-native-search-empty-guide.py'),
             str(NATIVE_CORE_OVERRIDE), str(NATIVE_CORE_OVERRIDE)])
        # Hard gate. Release 2.8.0.1+6 shipped with a patch lost and the device
        # crashed on 5 of 5 launches, because that build verified its own new
        # stub and never re-checked the patches that were already there. Never
        # ship a library that has not passed this.
        verify = [sys.executable, str(ROOT / 'tools' / 'verify-native-patches.py'), '--search-callback-guard', '--empty-partner-guide']
        if args.assert_arg_trace:
            verify.append('--assert-trace')
        if args.keep_asserts or args.assert_log_continue:
            # The reporter was asked to stay live, so a library that stubbed it
            # out would be a silent downgrade rather than a valid variant.
            verify.append('--require-live-asserts')
        run(verify)

    require([BASE_APK, TRACE_SO, APKTOOL, AAPT2, ZIPALIGN, APKSIGNER, ANDROID_JAR, JAVAC, JAVA, D8])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)

    stub_classes = BUILD_DIR / "stub-classes"
    app_classes = BUILD_DIR / "app-classes"
    dex_dir = BUILD_DIR / "telemetry-dex"
    for directory in (stub_classes, app_classes, dex_dir):
        directory.mkdir(parents=True)

    stub_sources = sorted(STUBS.rglob("*.java"))
    app_sources = sorted(SOURCES.rglob("*.java"))
    require(stub_sources + app_sources)

    # Generated, not checked in: the APK's own resources are not part of this
    # build, so aapt is unavailable as a BuildConfig generator. Writing the
    # class directly keeps the switch explicit and reviewable in the build log.
    build_config = BUILD_DIR / "generated" / "com" / "vshower" / "instrumented"
    build_config.mkdir(parents=True, exist_ok=True)
    (build_config / "BuildConfig.java").write_text(
        "package com.vshower.instrumented;\n"
        "\n"
        "/** Generated by tools/build-instrumented-apk.py. Do not edit. */\n"
        "public final class BuildConfig {\n"
        f"    public static final boolean RESTORE_PRE_REPAIR_CDN = {'true' if args.restore_pre_repair_cdn else 'false'};\n"
        "}\n",
        encoding="utf-8",
    )
    app_sources = sorted(SOURCES.rglob("*.java")) + [build_config / "BuildConfig.java"]

    run([str(JAVAC), "-source", "8", "-target", "8", "-cp", str(ANDROID_JAR), "-d", str(stub_classes), *map(str, stub_sources)])
    run([
        str(JAVAC), "-source", "8", "-target", "8",
        "-cp", os.pathsep.join((str(ANDROID_JAR), str(stub_classes))),
        "-d", str(app_classes), *map(str, app_sources),
    ])
    app_class_files = sorted(app_classes.rglob("*.class"))
    run([str(D8), "--lib", str(ANDROID_JAR), "--min-api", "20", "--output", str(dex_dir), *map(str, app_class_files)])
    telemetry_dex = dex_dir / "classes.dex"
    if not telemetry_dex.exists():
        raise FileNotFoundError(telemetry_dex)

    rebuilt = BUILD_DIR / "apktool-rebuilt.apk"
    run([str(JAVA), "-jar", str(APKTOOL), "b", "-f", "--aapt", str(AAPT2), "-o", str(rebuilt), str(DEBUG_SMALI)])

    unsigned = BUILD_DIR / "BLUSTONE-Instrumented-unsigned.apk"
    assemble_apk(rebuilt, telemetry_dex, unsigned)

    aligned = OUTPUT_DIR / "BLUSTONE-Instrumented-aligned.apk"
    run([str(ZIPALIGN), "-f", "-p", "4", str(unsigned), str(aligned)])

    if not KEYSTORE.exists():
        run([
            str(ROOT / "local" / "toolchains" / "jdk" / "jdk-21.0.12.1+1" / "bin" / "keytool.exe"),
            "-genkeypair", "-noprompt", "-keystore", str(KEYSTORE),
            "-storepass", KEY_PASSWORD, "-keypass", KEY_PASSWORD,
            "-alias", KEY_ALIAS, "-keyalg", "RSA", "-keysize", "2048",
            "-validity", "10000", "-dname", "CN=BLUSTONE - Instrumented, O=Local Research",
        ])

    output_apk = OUTPUT_DIR / "BLUSTONE-Instrumented.apk"
    run([
        str(APKSIGNER), "sign", "--ks", str(KEYSTORE),
        "--ks-key-alias", KEY_ALIAS, "--ks-pass", f"pass:{KEY_PASSWORD}",
        "--key-pass", f"pass:{KEY_PASSWORD}", "--out", str(output_apk), str(aligned),
    ])
    run([str(APKSIGNER), "verify", "--verbose", str(output_apk)])

    metadata = {
        "label": "BLUSTONE - Instrumented",
        "package": "com.vshower.prd_sr.instrumented",
        "source_apk": str(BASE_APK.relative_to(ROOT)),
        "output_apk": str(output_apk.relative_to(ROOT)),
        "collector_endpoint": "http://10.0.2.2:8099/v1/events",
        "signing_keystore": str(KEYSTORE.relative_to(ROOT)),
        "signing_alias": KEY_ALIAS,
        "telemetry_fallback": "files/instrumentation/events.ndjson",
        "native_db_trace": "BLUSTONE_DB_TRACE hooks for CGMLevelDB JSON/string getters",
        "native_bootstrap_redirect": "pv-prd.vshower.com -> 10.0.2.2:8080 in the instrumented-only native library",
        "native_gym_observer": "version28010 self-memory read-only snapshots: exact scene guards, bounded IDs/vectors, double-read stability; no debugger/native calls/writes/account fields",
        "native_search_observer": "version28010 read-only Partner group counts/availability, scene input and scene-owned guide/focus flags; exact vptrs, bounded begin/end reads and internal pointer/header rereads; not a top-modal or callback-execution proof",
        "episode_resource_observer": "13 fixed public JET filenames, original size/SHA256 pins, 16KiB streaming hashes after two metadata samples; hashes cached by size/mtime and labeled; no contents/account reads or writes",
        "interrupted_gym_resume": args.resume_interrupted_gym,
        "search_partner_callback_guard": "scoped current-scene and parent/SET_CK guards; invalid callbacks return/clean up before helper or tutorial writes",
        "fresh_empty_partner_guide": "defer before allocation only for exact Partner class, no existing guide owner/control, bounded valid virtual group and no available row; no guide flags, usage, rewards, scene jumps or existing-modal cleanup",
        "leveldb_current_packaging": "CURRENT filenames validated against existing manifests and packaged with exactly one LF; Windows CRLF is rejected/normalized without opening seed databases",
        "native_ui_animation_fallback": "CRMResourceMgr::MakeAnim2FromVideo returns null for the BlueStacks UI_MA_L1 fault",
        "ui_xml_seed": "instrumented-seed-episode-ui-delta-v1/UI_XML_RO.db (preserved working seed plus six native-proved English Episode layouts)",
        "restore_pre_repair_cdn": args.restore_pre_repair_cdn,
        "cdn_compression_migration": "pre-native exact snapshot hash gate including orphan compaction output; preserve entire original cache, replace only already-released bootstrap table and manifest file-size edit; stage validation/rename recovery; no live encrypted values bundled",
        "keep_asserts": args.keep_asserts,
        "assert_log_continue": args.assert_log_continue,
        "assert_arg_trace": args.assert_arg_trace,
        "assert_arg_trace_detail": (
            "_RMAssert entry branches to a freestanding Thumb stub that writes one "
            "BLUSTONE_ASSERT line (site, cond, line, first four variadic words) to "
            "stderr via a raw write syscall, then re-enters the untouched reporter at "
            "0x10B3AC0. No imports, no relocations, no dereference of argument values."
            if args.assert_arg_trace else None
        ),
        "logcat_noise_filter": (
            "source-side drop of native RANN [RSM] render/resource spam plus "
            "shape-based repeat suppression, so BLUSTONE_* / assertion / "
            "LevelDB lines are not evicted from the bounded collector ring"
        ),
    }
    (OUTPUT_DIR / "BUILD-METADATA.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Built {output_apk}")

    if args.install:
        adb = ROOT / "local" / "toolchains" / "android-sdk" / "platform-tools" / "adb.exe"
        require([adb])
        run([str(adb), "connect", "127.0.0.1:5555"])
        run([str(adb), "-s", "127.0.0.1:5555", "install", "-r", str(output_apk)])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
