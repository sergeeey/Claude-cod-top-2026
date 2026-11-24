"""Aggregate the ten blind grades into the frozen claim.md decision rules.

Scores are transcribed from the ten grader reports (one per task). Labels map to runs through
keys_SECRET/tNN.json; arms come from plan_SECRET.json. Nothing here changes a grade.
"""

from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

HERE = Path(__file__).parent
ITEMS = ["P1", "P2", "P3", "P4", "P5", "P6"]
LABELS = ["R1", "R2", "R3", "R4", "R5", "R6"]


def uniform(value: float = 1.0) -> dict[str, float]:
    return {label: value for label in LABELS}


def with_overrides(**changes: float) -> dict[str, float]:
    row = uniform()
    row.update(changes)
    return row


# item -> label -> score (1 / 0.5 / 0), one block per task, as reported by the grader
SCORES: dict[str, dict[str, dict[str, float]]] = {
    "t01": {i: uniform() for i in ITEMS},
    "t02": {i: with_overrides(R3=0.0) for i in ITEMS},
    "t03": {i: with_overrides(R1=0.0) for i in ITEMS},
    "t04": {i: uniform() for i in ITEMS},
    "t05": {**{i: uniform() for i in ITEMS[:5]}, "P6": with_overrides(R3=0.5)},
    "t06": {i: uniform() for i in ITEMS},
    "t07": {**{i: uniform() for i in ITEMS[1:]}, "P1": with_overrides(R1=0.5, R6=0.5)},
    "t08": {i: uniform() for i in ITEMS},
    "t09": {i: uniform() for i in ITEMS},
    "t10": {i: uniform() for i in ITEMS},
}

# false findings per report, from the grader NOTES / FALSE lines
FALSE: dict[str, dict[str, int]] = {
    "t01": {label: 0 for label in LABELS},
    "t02": {label: 0 for label in LABELS},
    "t03": {label: 0 for label in LABELS},
    "t04": {label: 0 for label in LABELS},
    "t05": {label: 0 for label in LABELS},
    "t06": {label: 0 for label in LABELS},
    "t07": {label: 0 for label in LABELS},
    "t08": {**{label: 0 for label in LABELS}, "R6": 1},
    "t09": {label: 0 for label in LABELS},
    "t10": {label: 0 for label in LABELS},
}

plan = json.load(open(HERE / "plan_SECRET.json", encoding="utf-8"))
metrics = json.load(open(HERE / "metrics_runs.json", encoding="utf-8"))
run_meta = {p["run"]: p for p in plan}


def counted_items(task: str) -> list[str]:
    rubric = json.load(open(HERE / "_r" / f"r{task[1:]}.json", encoding="utf-8"))
    return [p["id"] for p in rubric["planted"] if p.get("counted", True)]


rows = []  # one row per graded run
for task in sorted(SCORES):
    keymap = json.load(open(HERE / "keys_SECRET" / f"{task}.json", encoding="utf-8"))
    items = counted_items(task)
    for label, run_id in keymap.items():
        meta = run_meta[run_id]
        found = statistics.fmean(SCORES[task][i][label] for i in items)
        m = metrics[run_id]
        rows.append(
            {
                "task": task,
                "arm": meta["arm"],
                "rep": meta["rep"],
                "run": run_id,
                "found": found,
                "false": FALSE[task][label],
                "tokens": m["tokens_in"] + m["tokens_cache_create"] + m["tokens_out"],
                "tokens_out": m["tokens_out"],
                "seconds": m["seconds"],
                "items": len(items),
            }
        )

assert len(rows) == 60, len(rows)


def slot_mean(task: str, arm: str, key: str) -> float:
    vals = [r[key] for r in rows if r["task"] == task and r["arm"] == arm]
    return statistics.fmean(vals) if vals else float("nan")


import os  # noqa: E402

if os.environ.get("SENSITIVITY_EXCLUDE_SHORT"):
    # the two final messages that are replies to notifications, not reports (claim.md amendment)
    rows = [r for r in rows if r["run"] not in {"x63c3", "x0803"}]
    print("SENSITIVITY: excluding x63c3 and x0803; runs left:", len(rows))

import re as _re  # noqa: E402

if os.environ.get("EXCLUDE_CONTRACT_MENTIONS"):
    # blinding check: reports that mention the contract or hints may reveal the arm to a grader
    _pat = _re.compile(r"контракт|contract|подсказк|hint", _re.IGNORECASE)
    rows = [
        r
        for r in rows
        if not _pat.search((HERE / "reports" / f"{r['run']}.md").read_text(encoding="utf-8", errors="replace"))
    ]
    print("BLINDING SENSITIVITY: reports mentioning contract or hints removed; runs left:", len(rows))

tasks = sorted(SCORES)
DELTA_RUNS = {}
for arm in ("F", "H", "W"):
    deltas = [slot_mean(t, arm, "found") - slot_mean(t, "C", "found") for t in tasks]
    DELTA_RUNS[arm] = [d for d in deltas if d == d]  # drop tasks where a pair is empty


def boot_ci(
    values: list[float], n: int = 10000, seed: int = 20261014
) -> tuple[float, float, float]:
    rnd = random.Random(seed)
    point = statistics.fmean(values)
    means = []
    for _ in range(n):
        sample = [values[rnd.randrange(len(values))] for _ in values]
        means.append(statistics.fmean(sample))
    means.sort()
    return point, means[int(0.025 * n)], means[int(0.975 * n)]


print("Per-task found share (mean of reps), arms C F H W:")
for t in tasks:
    print(
        t,
        {a: round(slot_mean(t, a, "found"), 3) for a in ("C", "F", "H", "W")},
        "false C/F:",
        round(slot_mean(t, "C", "false"), 2),
        round(slot_mean(t, "F", "false"), 2),
    )

print()
for arm in ("F", "H", "W"):
    point, lo, hi = boot_ci(DELTA_RUNS[arm])
    print(f"Delta_{arm} = {point:+.3f}  95% task-bootstrap CI [{lo:+.3f}, {hi:+.3f}]")
    print("   per task:", [round(x, 3) for x in DELTA_RUNS[arm]])

fp_f = statistics.fmean(slot_mean(t, "F", "false") - slot_mean(t, "C", "false") for t in tasks)
print(f"\nFalse findings per task, F minus C (mean over tasks): {fp_f:+.2f}")

c_runs = [r for r in rows if r["arm"] == "C"]
f_runs = [r for r in rows if r["arm"] == "F"]
h_runs = [r for r in rows if r["arm"] == "H"]
w_runs = [r for r in rows if r["arm"] == "W"]
tok = lambda rs: statistics.fmean(r["tokens"] for r in rs)  # noqa: E731
tok_out = lambda rs: statistics.fmean(r["tokens_out"] for r in rs)  # noqa: E731
sec = lambda rs: statistics.fmean(r["seconds"] for r in rs)  # noqa: E731
print(
    f"\nTokens (in + cache_create + out) mean: C {tok(c_runs):,.0f}  F {tok(f_runs):,.0f}  "
    f"H {tok(h_runs):,.0f}  W {tok(w_runs):,.0f}  ratio F/C {tok(f_runs) / tok(c_runs):.2f}"
)
print(
    f"Output tokens mean: C {tok_out(c_runs):,.0f}  F {tok_out(f_runs):,.0f}  ratio {tok_out(f_runs) / tok_out(c_runs):.2f}"
)
print(
    f"Wall-clock seconds mean: C {sec(c_runs):.0f}  F {sec(f_runs):.0f}  ratio {sec(f_runs) / sec(c_runs):.2f}"
)

# ceiling check: the largest gain any arm can show is bounded by 1 minus the control share
ceiling = [1 - slot_mean(t, "C", "found") for t in tasks]
print(
    f"\nCeiling: mean headroom above control = {statistics.fmean(ceiling):.3f} (max possible Delta_F)"
)
