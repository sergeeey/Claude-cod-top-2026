#!/usr/bin/env python3
"""Compact summary of the two latency runs: percentiles, paired ratios, CPU and RSS per phase.

Reads the raw stand files (artifacts/latency/abg-c1-n100.json and abg-load4-n30.json) and writes
artifacts/latency/summary-2026-10-17.json without the per-sample arrays. The raw files stay the
source of truth; scripts/latency_compare.py prints the same ratios from them.

Usage: latency_summary.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import latency_stand as ls  # noqa: E402

RAW_DIR = REPO / "artifacts" / "latency"
GATED_HOOKS_POST_EDIT = [
    "plan_mode_guard.py",
    "activeContext_hygiene.py",
    "moc_autolink.py",
    "experiment_insight.py",
    "claim_entropy_tracker.py",
    "promotion_gate_guard.py",
    "reject_gate_guard.py",
    "submission_gate_guard.py",
    "null_retroscan.py",
    "hypothesis_router.py",
    "goal_stub_detector.py",
    "validation_theater_guard.py",
    "independence_scorer.py",
    "mutation_tracker.py",
]


def series(data: dict, arm: str, shape: str, metric: str) -> list[float]:
    rows = data["samples"][arm][shape]
    if metric == "phase":
        return [r["phase_ms"] for r in rows]
    return [r["phase_ms"] - max(h["spawned_ms"] for h in r["hooks"]) for r in rows]


def percentile(values: list[float], q: int) -> float:
    value = ls.pct(values, q)
    assert value is not None, "percentile of an empty series"
    return float(value)


def block(path: Path, base: str, others: list[str]) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, Any] = {
        "samples_per_shape_arm": {
            arm: len(data["samples"][arm][next(iter(data["samples"][arm]))])
            for arm in data["samples"]
        }
    }
    if data["mode"] == "load":
        out["sessions"] = data["sessions"]
        out["throughput"] = data["throughput"]
    shapes: dict[str, Any] = {}
    for shape in data["shapes"]:
        entry: dict[str, Any] = {}
        for metric in ("phase", "exec"):
            before = series(data, base, shape, metric)
            arms_stats: dict[str, Any] = {}
            for arm in [base, *others]:
                values = series(data, arm, shape, metric)
                stats: dict[str, Any] = {
                    f"p{q}_ms": round(percentile(values, q), 1) for q in (50, 95, 99)
                }
                if arm != base:
                    for q in (50, 95, 99):
                        r = ls.paired_ratio_ci(before, values, q)
                        stats[f"p{q}_ratio_vs_{base}"] = {
                            "ratio": round(r["ratio"], 3),
                            "ci95": [round(x, 3) for x in r["ci95"]],
                        }
                arms_stats[arm] = stats
            entry[metric] = arms_stats
        cpu_mean: dict[str, float] = {}
        rss_p95: dict[str, float] = {}
        for arm in [base, *others]:
            rows = data["samples"][arm][shape]
            cpu = [sum(h["cpu_ms"] or 0 for h in r["hooks"]) for r in rows]
            rss = [sum(h["peak_mb"] or 0 for h in r["hooks"]) for r in rows]
            cpu_mean[arm] = round(sum(cpu) / len(cpu), 1)
            rss_p95[arm] = round(percentile(rss, 95), 1)
        entry["cpu_ms_per_phase_mean"] = cpu_mean
        entry["rss_mb_sum_per_phase_p95"] = rss_p95
        shapes[shape] = entry
    out["shapes"] = shapes
    return out


def main() -> int:
    summary: dict[str, Any] = {
        "date": "2026-10-17",
        "machine": f"{sys.platform}, {os.cpu_count()} logical CPUs",
        "arms": {
            "before": "hooks/ snapshot before the latency changes (concurrency fixes included)",
            "after": "worktree hooks/: lazy imports and parallel git reads in post_commit_memory",
            "gated": "after without 14 no-op hooks on post_edit (what-if, manifest unchanged)",
        },
        "gated_hooks_post_edit": GATED_HOOKS_POST_EDIT,
        "sequential_n100": block(RAW_DIR / "abg-c1-n100.json", "before", ["after", "gated"]),
        "load_4_sessions_n30": block(RAW_DIR / "abg-load4-n30.json", "before", ["after", "gated"]),
    }
    out = RAW_DIR / "summary-2026-10-17.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out, out.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
