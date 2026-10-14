"""Print the ledger lines (and 2 lines of context) from selected PR bodies for hand reading."""

import json
import re
import sys
from pathlib import Path

snap = json.loads((Path(__file__).parent / "data" / "pr_snapshot.json").read_text(encoding="utf-8"))
by_num = {p["number"]: p for p in snap}
for n in map(int, sys.argv[1:]):
    body = by_num[n].get("body") or ""
    lines = body.splitlines()
    print(f"=== PR #{n}: {by_num[n]['title'][:80]}")
    shown = set()
    for i, line in enumerate(lines):
        if re.search(
            r"(?i)falsified\s+if|prediction\W{0,3}:|check\s+after|^\W*change\W{0,3}:", line
        ):
            for j in range(max(0, i - 1), min(len(lines), i + 2)):
                if j not in shown:
                    shown.add(j)
                    print("  ", lines[j][:260])
    print()
