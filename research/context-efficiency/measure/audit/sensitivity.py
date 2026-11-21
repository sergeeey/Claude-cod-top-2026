"""Sensitivity of the A/B cost comparison to cache-cold outliers. Free, local.

Pre-specified rule (fixed before looking at the effect): a run is a cache-cold outlier
if cli_cc (cache_creation_input_tokens of the whole session) > 100,000.
Reports the comparison with and without these runs, both as run means/medians and as
task-level paired means. Reads results/audit_per_run.csv only.
"""

import csv
import os
import random
import statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.abspath(os.path.join(HERE, "..", "..", "results"))
CUT = 100_000
rng = random.Random(11)

rows = list(csv.DictReader(open(os.path.join(RES, "audit_per_run.csv"), encoding="utf-8")))
for r in rows:
    r["cost"] = float(r["cli_cost"])
    r["cc"] = int(r["cli_cc"])
    r["cold"] = r["cc"] > CUT


def summarise(label, rs):
    a = [r["cost"] for r in rs if r["arm"] == "A"]
    b = [r["cost"] for r in rs if r["arm"] == "B"]
    d_mean = statistics.mean(b) - statistics.mean(a)
    d_med = statistics.median(b) - statistics.median(a)
    boots = []
    for _ in range(10000):
        sa = [rng.choice(a) for _ in a]
        sb = [rng.choice(b) for _ in b]
        boots.append(statistics.mean(sb) - statistics.mean(sa))
    boots.sort()
    print(
        f"{label}: nA={len(a)} nB={len(b)} "
        f"meanA={statistics.mean(a):.4f} meanB={statistics.mean(b):.4f} diffMean={d_mean:+.4f} "
        f"({100 * d_mean / statistics.mean(a):+.1f}%) | medA={statistics.median(a):.4f} "
        f"medB={statistics.median(b):.4f} diffMed={d_med:+.4f} "
        f"({100 * d_med / statistics.median(a):+.1f}%) "
        f"| run-level bootstrap 95% CI of mean diff (naive) [{boots[250]:+.4f}, {boots[9749]:+.4f}]"
    )


def task_paired(label, rs):
    by = defaultdict(lambda: defaultdict(list))
    for r in rs:
        by[r["task"]][r["arm"]].append(r["cost"])
    diffs = []
    for t in sorted(by):
        if by[t]["A"] and by[t]["B"]:
            d = statistics.mean(by[t]["B"]) - statistics.mean(by[t]["A"])
            diffs.append(d)
            print(f"  {label} {t}: nA={len(by[t]['A'])} nB={len(by[t]['B'])} diff={d:+.4f}")
    boots = []
    for _ in range(10000):
        boots.append(statistics.mean([rng.choice(diffs) for _ in diffs]))
    boots.sort()
    print(
        f"{label} task-level: mean diff={statistics.mean(diffs):+.4f} "
        f"bootstrap-over-6-tasks 95% CI [{boots[250]:+.4f}, {boots[9749]:+.4f}] "
        f"B cheaper in {sum(1 for d in diffs if d < 0)}/{len(diffs)} tasks"
    )


cold_list = [(r["arm"], r["task"], r["rep"], r["cc"]) for r in rows if r["cold"]]
print(f"cache-cold outliers (cc > {CUT}): {cold_list}")
print(
    f"cold by arm: A={sum(1 for r in rows if r['cold'] and r['arm'] == 'A')} "
    f"B={sum(1 for r in rows if r['cold'] and r['arm'] == 'B')}"
)
summarise("ALL runs", rows)
summarise("WARM-only (cc<=100k)", [r for r in rows if not r["cold"]])
task_paired("WARM-only", [r for r in rows if not r["cold"]])
task_paired("ALL", rows)
