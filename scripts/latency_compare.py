#!/usr/bin/env python3
"""Paired comparison of arms in a latency stand JSON, with 95 % bootstrap intervals.

Usage: latency_compare.py <run.json> <base_arm> [<other_arm> ...]

Two metrics per shape: phase (first process start to last exit) and exec (last Popen returning
to last exit, so harness spawn serialization is left out). Each other arm is reported as a ratio
to the base arm, with the 95 % interval from paired resampling of samples (see latency_stand).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import latency_stand as ls  # noqa: E402


def series(data: dict, arm: str, shape: str, metric: str) -> list[float]:
    rows = data["samples"][arm][shape]
    if metric == "phase":
        return [r["phase_ms"] for r in rows]
    return [r["phase_ms"] - max(h["spawned_ms"] for h in r["hooks"]) for r in rows]


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    base, others = sys.argv[2], sys.argv[3:]
    for metric in ("phase", "exec"):
        print(f"== {metric} (ms) ==")
        header = f"{'shape':<12}{'arm':<9}{'p50':>7}{'p95':>7}{'p99':>7}"
        print(f"{header}   ratio to {base}: p50 | p95 | p99")
        for shape in data["shapes"]:
            before = series(data, base, shape, metric)
            for arm in [base, *others]:
                values = series(data, arm, shape, metric)
                p50, p95, p99 = (ls.pct(values, q) for q in (50, 95, 99))
                parts = []
                if arm != base:
                    for q in (50, 95, 99):
                        r = ls.paired_ratio_ci(before, values, q)
                        lo, hi = r["ci95"]
                        parts.append(f"{r['ratio']:.2f} [{lo:.2f};{hi:.2f}]")
                print(f"{shape:<12}{arm:<9}{p50:7.0f}{p95:7.0f}{p99:7.0f}   {' | '.join(parts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
