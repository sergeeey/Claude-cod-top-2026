"""EXPLORATORY: first lines of loose prediction/ledger mentions in undeclared BC PRs."""

import json
import re
import sys
from pathlib import Path

snap = {
    p["number"]: p
    for p in json.loads(
        (Path(__file__).parent / "data" / "pr_snapshot.json").read_text(encoding="utf-8")
    )
}
for n in map(int, sys.argv[1:]):
    lines = (snap[n].get("body") or "").splitlines()
    hits = [
        ln.strip()[:200] for ln in lines if re.search(r"(?i)predict|falsif|ledger|check after", ln)
    ]
    print(f"#{n} {snap[n]['title'][:60]}: {len(hits)} hit(s)")
    for h in hits[:2]:
        print("    ", h)
