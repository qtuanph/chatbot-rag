#!/usr/bin/env python3
"""Update requirements.txt to latest versions from PyPI.

Usage: python scripts/update_requirements.py

Creates a timestamped backup and replaces pinned versions with the
latest release from PyPI for each package listed in `requirements.txt`.
Preserves blank lines and comments.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


ROOT = Path(__file__).resolve().parents[1]
REQ_FILE = ROOT / "requirements.txt"


def parse_requirement_line(line: str) -> tuple[str, Optional[str]]:
    s = line.strip()
    if not s or s.startswith("#"):
        return line, None

    # Handle lines like 'package==1.2.3' or 'package[extra]==1.2.3' or 'package'
    if "==" in s:
        name_part = s.split("==", 1)[0].strip()
    else:
        name_part = s

    display = name_part
    lookup = name_part.split("[")[0].replace("_", "-").lower()
    return display, lookup


def get_latest(package: str) -> Optional[str]:
    url = f"https://pypi.org/pypi/{package}/json"
    req = Request(url, headers={"User-Agent": "update-requirements-script/1.0"})
    try:
        with urlopen(req, timeout=30) as fh:
            data = json.load(fh)
            return data.get("info", {}).get("version")
    except HTTPError as e:
        print(f"HTTP error for {package}: {e.code} {e.reason}")
    except URLError as e:
        print(f"Network error for {package}: {e}")
    except Exception as e:
        print(f"Error fetching {package}: {e}")
    return None


def main() -> int:
    if not REQ_FILE.exists():
        print("requirements.txt not found in project root")
        return 2

    ts = time.strftime("%Y%m%d%H%M%S")
    backup = REQ_FILE.with_name(f"requirements.txt.bak.{ts}")
    shutil.copy2(REQ_FILE, backup)
    print(f"Created backup: {backup.name}")

    out_lines: list[str] = []
    for raw in REQ_FILE.read_text(encoding="utf-8").splitlines():
        display, lookup = parse_requirement_line(raw)
        if lookup is None:
            out_lines.append(raw)
            continue

        latest = get_latest(lookup)
        if latest:
            new_line = f"{display}=={latest}"
            print(f"{display} -> {latest}")
            out_lines.append(new_line)
        else:
            print(f"Keep original (no data): {raw}")
            out_lines.append(raw)

    REQ_FILE.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print("requirements.txt updated. Please run tests/install to verify.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
