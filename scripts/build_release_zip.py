#!/usr/bin/env python3
"""Build dist/slce_videolock.zip for HACS/Marketplace zip_release.

Files must be at the ZIP root (manifest.json, __init__.py, ...).
Do NOT nest under slce_videolock/ — HACS extracts into
custom_components/slce_videolock/ already.
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "custom_components" / "slce_videolock"
OUT = ROOT / "dist" / "slce_videolock.zip"
HACS = ROOT / "hacs.json"
SKIP_PARTS = {"__pycache__"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def main() -> int:
    if not SRC.is_dir():
        print("FAIL: missing", SRC)
        return 1

    hacs = json.loads(HACS.read_text(encoding="utf-8"))
    if not hacs.get("zip_release"):
        print("FAIL: hacs.json must set zip_release: true")
        return 1
    if hacs.get("filename") != "slce_videolock.zip":
        print("FAIL: hacs.json filename must be slce_videolock.zip")
        return 1

    manifest = json.loads((SRC / "manifest.json").read_text(encoding="utf-8"))
    version = manifest.get("version")
    if not version:
        print("FAIL: manifest.json missing version")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()

    count = 0
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(SRC.rglob("*")):
            if not path.is_file():
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            if path.suffix in SKIP_SUFFIXES:
                continue
            arcname = path.relative_to(SRC).as_posix()
            if arcname.startswith("slce_videolock/"):
                print("FAIL: refusing nested path", arcname)
                return 1
            zf.write(path, arcname)
            count += 1

    names = zipfile.ZipFile(OUT).namelist()
    if "manifest.json" not in names:
        print("FAIL: manifest.json not at ZIP root")
        return 1
    if any(n.startswith("slce_videolock/") for n in names):
        print("FAIL: ZIP contains nested slce_videolock/ folder")
        return 1

    print(f"OK {OUT} version={version} files={count} bytes={OUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
