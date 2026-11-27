"""Check that every hook command in an installed settings.json points to an existing file, and that
the file does not reference the real live directory.

Usage: python rc_wiring_check.py <installed .claude dir> [--live <real ~/.claude>]
Exit 1 if a referenced hook file is missing or the live directory is referenced.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("root", type=Path)
ap.add_argument("--live", default="")
a = ap.parse_args()
settings = json.loads((a.root / "settings.json").read_text(encoding="utf-8"))
total, missing = 0, []
for event, groups in settings.get("hooks", {}).items():
    for group in groups:
        for h in group.get("hooks", []):
            for m in re.findall(r"[\"']?([^\"'\s]+\.py)[\"']?", h.get("command", "")):
                total += 1
                p = Path(m)
                if not p.is_absolute():
                    p = a.root / m
                if not p.exists():
                    missing.append(f"{event}: {Path(m).name}")
print(f"hook script references: {total}; missing: {len(missing)}")
for x in missing:
    print("  MISSING", x)
text = json.dumps(settings).replace("\\\\", "/")
live = a.live.replace("\\", "/").rstrip("/")
leaked = bool(live) and live in text
print("settings reference the live dir:", leaked)
sys.exit(1 if missing or leaked else 0)
