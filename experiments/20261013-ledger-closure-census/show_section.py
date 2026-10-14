"""EXPLORATORY: print N lines after a heading text in a PR body."""

import json
import sys
from pathlib import Path

snap = {
    p["number"]: p
    for p in json.loads(
        (Path(__file__).parent / "data" / "pr_snapshot.json").read_text(encoding="utf-8")
    )
}
num, needle, count = int(sys.argv[1]), sys.argv[2], int(sys.argv[3])
lines = (snap[num].get("body") or "").splitlines()
for i, line in enumerate(lines):
    if needle in line:
        print("\n".join(lines[i : i + count]))
        break
