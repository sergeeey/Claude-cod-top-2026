"""EXPLORATORY (not pre-registered): timeline of BC PRs and loose mentions of a prediction/ledger.

Purpose: check whether a lower M1 after the rule's first days comes from drift in the wording
(parser misses a variant) or from the ledger really not being written.
"""

import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).parent
snap = json.loads((HERE / "data" / "pr_snapshot.json").read_text(encoding="utf-8"))
res = json.loads((HERE / "data" / "results.json").read_text(encoding="utf-8"))
declared = {d["number"] for d in res["declared_detail"]}
BC = [
    r"^hooks/(?!CLAUDE\.md$)",
    r"^rules/",
    r"^agents/",
    r"^commands/",
    r"^skills/.+/SKILL\.md$",
    r"^skills/registry\.yaml$",
    r"^scripts/.+\.py$",
    r"^claude-md/CLAUDE\.md$",
    r"^install\.sh$",
    r"^\.github/workflows/",
]
start = datetime(2026, 9, 10, tzinfo=UTC)
rows = []
for p in snap:
    m = datetime.fromisoformat(p["mergedAt"].replace("Z", "+00:00"))
    if m < start:
        continue
    files = [f["path"] for f in p.get("files", [])]
    bc = any(re.search(x, f) for f in files for x in BC)
    body = p.get("body") or ""
    rows.append(
        {
            "n": p["number"],
            "day": m.date().isoformat(),
            "bc": bc,
            "declared": p["number"] in declared,
            "loose": bool(re.search(r"(?i)predict|falsif|ledger|check after", body)),
        }
    )
by_week: Counter = Counter()
for r in rows:
    if r["bc"]:
        wk = datetime.fromisoformat(r["day"]).isocalendar()[1]
        by_week[(wk, "bc")] += 1
        by_week[(wk, "declared")] += r["declared"]
        by_week[(wk, "loose_not_declared")] += r["loose"] and not r["declared"]
for wk in sorted({k[0] for k in by_week}):
    print(
        f"ISO week {wk}: BC={by_week[(wk, 'bc')]} declared={by_week[(wk, 'declared')]} "
        f"loose-mention-but-not-declared={by_week[(wk, 'loose_not_declared')]}"
    )
print(
    "loose-not-declared PRs:",
    [r["n"] for r in rows if r["bc"] and r["loose"] and not r["declared"]],
)
print(
    "BC after 2026-09-12 with no loose mention:",
    sum(1 for r in rows if r["bc"] and r["day"] > "2026-09-12" and not r["loose"]),
)
