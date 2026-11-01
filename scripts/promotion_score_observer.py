#!/usr/bin/env python3
"""OBSERVE-only shadow logger for the Adaptive Promotion Score heuristic.

WHY this exists, and why it does NOT compute anything automatically: the ТЗ that
motivated this file names its own formula (expected_value x falsifiability x
information_gain x evidence_independence / expected_cost) an UNVALIDATED
HEURISTIC and requires an OBSERVE-only phase -- log the proposed priority, do
NOT change allocation, compare prediction to real outcome later -- before any
part of it may move to WARN/PREVENT/AUTHORITY.

Reuses the exact discipline this repo already dogfoods for a DIFFERENT signal:
hooks/verdict_logger.py appends a JSONL record per event; scripts/
false_pass_rate.py replays that log later against real outcomes, anchored to
the record's own timestamp, never datetime.now(). This script mirrors that
shape: append-only JSONL, never mutates graph.yaml, never blocks or reorders
anything. The actual formula factors (experiments/_template/graph.yaml's
`priority_factors`) are HUMAN-FILLED 0-1 estimates, never auto-computed here --
Cycle 1 (2026-09-12) ships only this logging infrastructure. Operationalizing
the factors is explicitly deferred to a later cycle, once real records justify it
(see docs/experiment-dependency-graph.md).

This script does NOT replay/score yet -- that is also deferred (needs real
records to accumulate first, same as false_pass_rate.py needed real verdict_log
history before its own MIN_RECORDS_FOR_RATE threshold could ever be reached).

Usage:
    python scripts/promotion_score_observer.py            # human report
    python scripts/promotion_score_observer.py --json      # machine-readable
    python scripts/promotion_score_observer.py --dry-run    # compute, do not append to the log
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - PyYAML is a pinned CI dep
    print("ERROR: PyYAML is required (pip install -r requirements.txt)", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTS_DIR = ROOT / "experiments"
LOG_PATH = ROOT / ".claude" / "memory" / "promotion_priority_shadow.jsonl"
_FACTOR_KEYS = (
    "expected_value",
    "falsifiability",
    "information_gain",
    "evidence_independence",
    "expected_cost",
)


def discover_graph_files() -> list[Path]:
    if not EXPERIMENTS_DIR.exists():
        return []
    return sorted(p for p in EXPERIMENTS_DIR.glob("*/graph.yaml") if p.parent.name != "_template")


def compute_proposed_priority(factors: dict[str, float]) -> float | None:
    """Naive product/ratio of the 5 factors -- deliberately NOT tuned, NOT
    validated, exactly what the ТЗ calls an UNVALIDATED HEURISTIC. Returns
    None if expected_cost is 0 (undefined), any factor is missing, or a
    factor value isn't actually numeric (sec-auditor-found, 2026-09-12: a
    malformed graph.yaml with a string in a factor field previously raised
    TypeError uncaught at the multiply/divide below -- robustness, not a
    security issue for a CLI script, but worth failing gracefully rather
    than crashing on bad input)."""
    if not isinstance(factors, dict):
        return None
    raw = {k: factors.get(k) for k in _FACTOR_KEYS}
    if any(
        v is None or isinstance(v, bool) or not isinstance(v, (int, float)) for v in raw.values()
    ):
        return None
    # WHY cast here, not earlier: the isinstance check above is the actual
    # runtime guard: mypy cannot narrow a dict comprehension's value type
    # from that check alone, so this makes explicit what's already been
    # verified -- every value is a real, non-bool int/float at this point.
    values = {k: cast(float, v) for k, v in raw.items()}
    cost = values["expected_cost"]
    if cost == 0:
        return None
    return (
        values["expected_value"]
        * values["falsifiability"]
        * values["information_gain"]
        * values["evidence_independence"]
        / cost
    )


def collect_observations(now: datetime | None = None) -> list[dict[str, Any]]:
    """Read every graph.yaml with a FULLY filled priority_factors block, compute
    the shadow score, and return one record per experiment. Does not append to
    the log -- see append_observations for that."""
    ts = (now or datetime.now(UTC)).isoformat()
    observations: list[dict[str, Any]] = []
    for gf in discover_graph_files():
        try:
            data = yaml.safe_load(gf.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        factors = data.get("priority_factors") or {}
        proposed = compute_proposed_priority(factors)
        if proposed is None:
            continue  # not fully filled -- nothing to observe yet for this experiment
        observations.append(
            {
                "ts": ts,
                "experiment_id": data.get("id") or gf.parent.name,
                "mode": data.get("mode"),
                "status": data.get("status"),
                "factors": {k: factors.get(k) for k in _FACTOR_KEYS},
                "proposed_priority": round(proposed, 4),
                # WHY recorded but never acted on: the eventual replay pass compares
                # this against the REAL outcome once one exists (updated_at/status
                # change) -- same anchored-to-own-timestamp discipline as
                # scripts/false_pass_rate.py, applied to a different signal.
                "actual_outcome": None,
            }
        )
    return observations


def append_observations(observations: list[dict[str, Any]]) -> None:
    if not observations:
        return
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        for obs in observations:
            f.write(json.dumps(obs, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--dry-run", action="store_true", help="compute and print, do not append to the log"
    )
    args = parser.parse_args(argv)

    observations = collect_observations()

    if not args.dry_run:
        append_observations(observations)

    if args.json:
        print(json.dumps(observations, indent=2, ensure_ascii=False))
        return 0

    print(
        f"[promotion-score-observer] {len(observations)} experiment(s) with filled "
        "priority_factors observed this run."
    )
    if not args.dry_run and observations:
        print(f"  appended to {LOG_PATH}")
    for obs in observations:
        print(
            f"  - {obs['experiment_id']}: proposed_priority={obs['proposed_priority']} "
            f"(mode={obs['mode']}, status={obs['status']})"
        )
    if not observations:
        print(
            "  (no experiment currently has all 5 priority_factors filled -- this is "
            "expected and fine; the score is UNVALIDATED and optional, per the ТЗ's own "
            "OBSERVE-only requirement)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
