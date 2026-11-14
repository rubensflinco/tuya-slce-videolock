#!/usr/bin/env python3
"""Validate basic integration packaging."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "slce_videolock" / "manifest.json"
REQUIRED = [
    "domain",
    "name",
    "version",
    "config_flow",
    "documentation",
    "codeowners",
]


def main() -> int:
    if not MANIFEST.is_file():
        print("FAIL: missing", MANIFEST)
        return 1
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        print("FAIL: missing keys", missing)
        return 1
    if data["domain"] != "slce_videolock":
        print("FAIL: domain mismatch", data["domain"])
        return 1
    for name in ("__init__.py", "config_flow.py", "lock.py", "const.py"):
        p = MANIFEST.parent / name
        if not p.is_file():
            print("FAIL: missing", p.name)
            return 1
    print("OK", data["name"], data["version"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
