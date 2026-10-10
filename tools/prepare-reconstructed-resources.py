"""Prepare a local compatibility resource tree from preserved phone assets.

This tool only reads the preserved phone copy and writes a new local output
tree. It never opens the live phone. The UI_XML builder deliberately excludes
KO/DEFINE_COLOR because aliasing that locale-specific engine table under EN
caused the native BuildColorTable assertion.

The UI package is emitted as a LevelDB delta: the APK/initial download already
contains the base table, so the package adds a new SSTable plus a new
MANIFEST/CURRENT instead of trying to overwrite the live 000005.ldb while the
database is open.  The delta also republishes the preserved EN catalog so
records that live in the phone's later SSTable (notably NEW/SR_MISSION) are
present on the emulator even when the native downloader leaves that SSTable
behind.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ui-source",
        type=Path,
        default=ROOT / "recovered-assets/phone-evidence-2026-09-19/diagnostics/files/local/UI_XML_RO.db",
        help="preserved UI_XML_RO LevelDB directory",
    )
    parser.add_argument(
        "--package-source",
        type=Path,
        default=ROOT / "recovered-assets/phone-2026-09-18/private/files/local",
        help="preserved directory containing E_NEW.jet and E_MIDAGE.jet",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "analysis/reconstructed-resources",
        help="new output resource tree; must not already exist",
    )
    args = parser.parse_args()

    ui_source = args.ui_source.resolve()
    package_source = args.package_source.resolve()
    destination = args.out.resolve()
    if not ui_source.is_dir():
        raise SystemExit(f"UI source directory does not exist: {ui_source}")
    if not package_source.is_dir():
        raise SystemExit(f"package source directory does not exist: {package_source}")
    if destination.exists():
        raise SystemExit(f"refusing to overwrite existing output: {destination}")

    destination.mkdir(parents=True)
    for package_name in ("E_NEW.jet", "E_MIDAGE.jet"):
        source = package_source / package_name
        if not source.is_file():
            raise SystemExit(f"required package is missing: {source}")
        shutil.copy2(source, destination / package_name)

    ui_destination = destination / "UI_XML_RO.db"
    source_tables = {item.name for item in ui_source.glob("*.ldb")}
    patcher = ROOT / "tools/patch-ui-leveldb.py"
    subprocess.run(
        [
            sys.executable,
            str(patcher),
            str(ui_source),
        str(ui_destination),
        "--compact",
        "--force-prefix",
        "EN/",
    ],
        cwd=ROOT,
        check=True,
    )

    # Keep only the newly-created alias table and the manifest/current files.
    # The old 000005.ldb remains in the app's installed base resource and must
    # not be sent again: the native unpacker cannot safely replace that live
    # LevelDB table during the download callback.
    new_tables = sorted(
        item for item in ui_destination.glob("*.ldb") if item.name not in source_tables
    )
    if not new_tables:
        raise SystemExit("delta UI build did not create a new SSTable")
    current_name = (ui_destination / "CURRENT").read_text(encoding="utf-8").strip()
    keep = {"CURRENT", current_name, *(item.name for item in new_tables)}
    for item in ui_destination.iterdir():
        if item.name not in keep:
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

    # The native downloader identifies the logical package by this filename;
    # pkgi1-tree packaging supplies the sibling database files as its payload.
    (destination / "UI_XML_RO.db.jet").write_text(
        "UI_XML_RO reconstructed package marker; payload is packed from the sibling UI_XML_RO.db tree.\n",
        encoding="utf-8",
    )
    print(f"prepared={destination}")
    print("package_names=E_NEW.jet,E_MIDAGE.jet,UI_XML_RO.db.jet")
    print("package_mode=pkgi1-tree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
