"""Cache-state check per arm: time since the previous run OF THE SAME ARM ended.

Prompt caches are keyed by prefix, and each arm has its own prefix, so the relevant gap is
to the previous request of the same arm, not to the previous run of any arm. Free, local.
Reads session logs via stats_audit.session_stats (dedup by message.id), no API calls.
"""

import csv
import json
import os
import statistics

from stats_audit import session_stats  # same folder

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.abspath(os.path.join(HERE, "..", "..", "results"))

rows = list(csv.DictReader(open(os.path.join(RES, "audit_per_run.csv"), encoding="utf-8")))
# execution order from the raw runner log (line index = run order)
raw = [ln for ln in open(os.path.join(RES, "ab_runs.jsonl"), encoding="utf-8")]

order = {}
for idx, line in enumerate(raw):
    d = json.loads(line)
    if d.get("dry"):
        continue
    order.setdefault((d["arm"], d["task"], int(d["rep"])), idx)

seq = sorted(rows, key=lambda r: order[(r["arm"], r["task"], int(r["rep"]))])
last_end = {"A": None, "B": None}
table = []
for r in seq:
    cli = (int(r["cli_in"]), int(r["cli_out"]), int(r["cli_cc"]), int(r["cli_cr"]))
    s = session_stats(r["arm"], r["task"], int(r["rep"]), cli)
    gap_same = None
    if s and s["start"] and last_end[r["arm"]]:
        gap_same = (s["start"] - last_end[r["arm"]]).total_seconds()
    table.append(
        (r["arm"], r["task"], int(r["rep"]), gap_same, int(r["cli_cc"]), float(r["cli_cost"]))
    )
    if s and s["end"]:
        last_end[r["arm"]] = s["end"]

print("arm task rep  gap_same_arm_s  cache_creation  cost")
for arm, task, rep, gap, cc, cost in table:
    g = f"{gap:9.0f}" if gap is not None else "      n/a"
    print(f"{arm}   {task:<12} {rep}  {g}   {cc:>9}   {cost:.4f}")

withg = [(g, cc) for a, t, rp, g, cc, c in table if g is not None]
cold_gap = [g for g, cc in withg if cc > 100_000]
warm_gap = [g for g, cc in withg if cc <= 100_000]
print(f"cold runs same-arm gap (s): {sorted(round(x) for x in cold_gap)}")
print(f"warm runs same-arm gap median (s): {statistics.median(warm_gap) if warm_gap else None}")
print(f"warm runs same-arm gap min (s): {min(warm_gap) if warm_gap else None}")
