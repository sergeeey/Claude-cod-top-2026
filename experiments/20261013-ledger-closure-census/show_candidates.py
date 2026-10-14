"""Print the sentence around '#<n>' in each closure-candidate PR body, for hand judgement."""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
snap = {
    p["number"]: p
    for p in json.loads((HERE / "data" / "pr_snapshot.json").read_text(encoding="utf-8"))
}
res = json.loads((HERE / "data" / "results.json").read_text(encoding="utf-8"))
wanted = set(map(int, sys.argv[1:])) if len(sys.argv) > 1 else None
for d in res["declared_detail"]:
    if wanted and d["number"] not in wanted:
        continue
    print(f"##### ledger PR #{d['number']}  check_after={d['check_after']!r}  due={d['due']}")
    for c in d["candidates"]:
        if not c["where"].startswith("PR #"):
            print("  (own comment)", c)
            continue
        q = int(re.search(r"#(\d+)", c["where"]).group(1))
        body = snap[q].get("body") or ""
        for m in re.finditer(r"#" + str(d["number"]) + r"\b", body):
            s = max(0, m.start() - 220)
            e = min(len(body), m.end() + 260)
            print(f"  -- in PR #{q}: ...{body[s:e].replace(chr(10), ' ')}...")
            break
    print()
