"""Statistics and confound checks for the approved A/B run. Free, local.

- Re-runs the hidden acceptance tests on the saved run directories (no model call).
- Reads per-request usage and timestamps from the session logs (dedup by message.id).
- Checks cache-state confound: gap since the previous run ended vs cache_creation.
- Counts tool use per run (Read calls, tool errors) as a proxy for re-reads and retries.
- Task-level paired comparison (6 units), bootstrap over tasks, sign test, run-level
  bootstrap shown only to illustrate overstated precision.
Writes results/stats_summary.json and prints tables.
"""

import glob
import json
import os
import random
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.abspath(os.path.join(HERE, "..", "..", "results"))
RUNS = os.path.abspath(
    os.path.join(
        "C:/Users/serge/AppData/Local/Temp/claude/597062ca1499700c/ee8180be-1b29-4147-b347-c85d90d9b421/scratchpad/ab/runs"
    )
)
PROJ = r"C:\Users\serge\.claude\projects"
TAG = "scratchpad-ab-runs"
TASKS = ["t1_paginate", "t2_duration", "t3_money", "t4_intervals", "t5_config", "t6_csv"]
rng = random.Random(7)


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def session_stats(arm, task, rep, cli_tot):
    tdir = glob.glob(os.path.join(PROJ, f"*{TAG}-{arm}-{task.replace('_', '-')}-r{rep}"))[0]
    chosen = None
    for jp in glob.glob(os.path.join(tdir, "*.jsonl")):
        recs = []
        with open(jp, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    recs.append(json.loads(line))
                except ValueError:
                    pass
        reqs = {}
        tools = Counter()
        tool_err = 0
        stamps = []
        for rec in recs:
            if rec.get("timestamp"):
                stamps.append(ts(rec["timestamp"]))
            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue
            if rec.get("type") == "assistant":
                for block in msg.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tools[block.get("name")] += 1
                u = msg.get("usage")
                if isinstance(u, dict) and msg.get("model") != "<synthetic>":
                    reqs.setdefault(msg.get("id") or rec.get("uuid"), u)
            if rec.get("type") == "user":
                content = msg.get("content")
                if isinstance(content, list):
                    for block in content:
                        if (
                            isinstance(block, dict)
                            and block.get("type") == "tool_result"
                            and block.get("is_error")
                        ):
                            tool_err += 1
        tot = (
            sum(int(u.get("input_tokens") or 0) for u in reqs.values()),
            sum(int(u.get("output_tokens") or 0) for u in reqs.values()),
            sum(int(u.get("cache_creation_input_tokens") or 0) for u in reqs.values()),
            sum(int(u.get("cache_read_input_tokens") or 0) for u in reqs.values()),
        )
        if tot == cli_tot:
            chosen = {
                "file": os.path.basename(jp),
                "start": min(stamps) if stamps else None,
                "end": max(stamps) if stamps else None,
                "requests": len(reqs),
                "tools": tools,
                "tool_errors": tool_err,
            }
            break
    return chosen


def main():
    rows = [json.loads(ln) for ln in open(os.path.join(RES, "ab_runs.jsonl"), encoding="utf-8")]
    full = [dict(r, order=i) for i, r in enumerate(rows) if not r.get("dry")]
    out = {"runs": len(full)}

    # 1) independent hidden-test re-run on saved run directories
    mismatch = []
    retest = {}
    for r in full:
        d = os.path.join(RUNS, r["arm"], r["task"], f"r{r['rep']}")
        f = os.path.join("tests", f"test_hidden_{r['task']}.py")
        p = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--tb=no", f],
            cwd=d,
            capture_output=True,
            text=True,
            timeout=120,
        )
        ok = p.returncode == 0
        retest[(r["arm"], r["task"], r["rep"])] = ok
        if ok != r["hidden_pass"]:
            mismatch.append((r["arm"], r["task"], r["rep"]))
    out["hidden_retest_pass"] = sum(retest.values())
    out["hidden_retest_mismatch_vs_log"] = mismatch

    # 2) session-level facts (timestamps, tools) using the CLI token totals to pick the file
    sess = {}
    for r in full:
        cli = (
            r["input_tokens"],
            r["output_tokens"],
            r["cache_creation_input_tokens"],
            r["cache_read_input_tokens"],
        )
        sess[(r["arm"], r["task"], r["rep"])] = session_stats(r["arm"], r["task"], r["rep"], cli)
    missing_sess = [k for k, v in sess.items() if v is None]
    out["session_match_missing"] = missing_sess

    # 3) cache-state confound: gap from the previous run's end to this run's start
    ordered = sorted(full, key=lambda r: r["order"])
    prev_end = None
    gap_rows = []
    for r in ordered:
        s = sess[(r["arm"], r["task"], r["rep"])]
        if s and s["start"] and prev_end:
            gap = (s["start"] - prev_end).total_seconds()
        else:
            gap = None
        gap_rows.append((r, gap))
        if s and s["end"]:
            prev_end = s["end"]
    warm = [r["cache_creation_input_tokens"] for r, g in gap_rows if g is not None and g < 300]
    cold = [r["cache_creation_input_tokens"] for r, g in gap_rows if g is not None and g >= 300]
    out["cache_warm_gap_lt_300s_runs"] = len(warm)
    out["cache_cold_gap_ge_300s_runs"] = len(cold)
    out["median_cache_create_warm"] = statistics.median(warm) if warm else None
    out["median_cache_create_cold"] = statistics.median(cold) if cold else None
    out["median_gap_s"] = statistics.median([g for _, g in gap_rows if g is not None])

    # 4) tool use per arm (re-reads and retries proxy)
    for arm in "AB":
        rs = [r for r in full if r["arm"] == arm]
        reads = [sess[(r["arm"], r["task"], r["rep"])]["tools"].get("Read", 0) for r in rs]
        errs = [sess[(r["arm"], r["task"], r["rep"])]["tool_errors"] for r in rs]
        out[f"arm_{arm}_median_reads"] = statistics.median(reads)
        out[f"arm_{arm}_tool_errors_total"] = sum(errs)
        out[f"arm_{arm}_requests_median"] = statistics.median(
            [sess[(r["arm"], r["task"], r["rep"])]["requests"] for r in rs]
        )

    # 5) task-level paired statistics
    by = defaultdict(lambda: defaultdict(list))
    for r in full:
        by[r["task"]][r["arm"]].append(r)
    task_diff = {}
    per_task = {}
    for t in TASKS:
        a = [r["total_cost_usd"] for r in by[t]["A"]]
        b = [r["total_cost_usd"] for r in by[t]["B"]]
        ma, mb = statistics.mean(a), statistics.mean(b)
        task_diff[t] = mb - ma
        per_task[t] = {
            "cost_A_mean": round(ma, 5),
            "cost_B_mean": round(mb, 5),
            "diff_B_minus_A": round(mb - ma, 5),
            "pct": round(100 * (mb - ma) / ma, 2),
            "pass_A": sum(r["hidden_pass"] for r in by[t]["A"]),
            "pass_B": sum(r["hidden_pass"] for r in by[t]["B"]),
            "turns_A_median": statistics.median([r["num_turns"] for r in by[t]["A"]]),
            "turns_B_median": statistics.median([r["num_turns"] for r in by[t]["B"]]),
        }
    diffs = list(task_diff.values())
    out["task_diff_mean"] = statistics.mean(diffs)
    boots = []
    for _ in range(20000):
        samp = [rng.choice(diffs) for _ in diffs]
        boots.append(statistics.mean(samp))
    boots.sort()
    out["task_bootstrap_ci95"] = [round(boots[500], 5), round(boots[19499], 5)]
    out["task_diffs_positive_count"] = sum(1 for d in diffs if d > 0)
    # sign test on 6 task-level differences (two-sided)
    n_pos = out["task_diffs_positive_count"]
    n_neg = sum(1 for d in diffs if d < 0)
    n = n_pos + n_neg
    from math import comb

    k = min(n_pos, n_neg)
    out["sign_test_p_two_sided"] = min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2**n)

    # run-level bootstrap, for contrast only (treats 36 runs as independent: overstates precision)
    ca = [r["total_cost_usd"] for r in full if r["arm"] == "A"]
    cb = [r["total_cost_usd"] for r in full if r["arm"] == "B"]
    rb = []
    for _ in range(20000):
        sa = [rng.choice(ca) for _ in ca]
        sb = [rng.choice(cb) for _ in cb]
        rb.append(statistics.mean(sb) - statistics.mean(sa))
    rb.sort()
    out["run_level_bootstrap_ci95_naive"] = [round(rb[500], 5), round(rb[19499], 5)]

    # 6) pass-rate bound: 0 failures in 18 per arm
    out["pass_rate_upper95_if_0_of_18_fail"] = round(1 - 0.025 ** (1 / 18), 4)

    out["per_task"] = per_task
    with open(os.path.join(RES, "stats_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False, default=str)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
