#!/usr/bin/env python3
"""Routing-floor trace replay — compare BASELINE (raw regex, no suppression)
against CANDIDATE (hooks/routing_floor_classifier.py's real classify(), which
includes the is_likely_quoted_occurrence pasted-document suppression added
2026-09-12) on a curated, ground-truth-labelled case set.

WHY this exists (P0b of the routing-telemetry work, 2026-09-12 session):
routing_events.jsonl (lib/state.py's log_route_decision()) records what the
live classifier actually decided on real prompts, but a log alone cannot
answer "would a candidate change make things better or worse overall" --
that needs the SAME prompts run through both the old and new logic side by
side, against a labelled expectation. This script is that harness.

BASELINE is defined here as "no suppression at all" (i.e. the classifier's
own behavior before this session added is_likely_quoted_occurrence) rather
than re-importing an actual old git revision -- the whole point of the
regression cases in routing_replay_cases.jsonl is that BASELINE gets them
wrong (false positive) and CANDIDATE gets them right, while the true-positive
cases must still agree between the two. If a future candidate change needs
comparing against something other than "no suppression", swap out
`classify_baseline()` below -- the harness/metrics code does not care what
BASELINE actually is.

Usage:
    python scripts/routing_replay.py                                  # default case file
    python scripts/routing_replay.py --cases path/to/cases.jsonl
    python scripts/routing_replay.py --json                           # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from lib.classification_signals import (  # noqa: E402
    match_destructive_signal,
    match_research_signal,
    match_security_signal,
)
from routing_floor_classifier import classify as classify_candidate_raw  # noqa: E402

DEFAULT_CASES = Path(__file__).resolve().parent / "routing_replay_cases.jsonl"

_BASELINE_MATCHERS = {
    "SECURITY": match_security_signal,
    "DESTRUCTIVE": match_destructive_signal,
    "RESEARCH": match_research_signal,
}


def classify_baseline(prompt: str) -> list[str]:
    """BASELINE: every tier whose raw regex matches anywhere in the prompt,
    no suppression of any kind -- the classifier's behavior before the
    2026-09-12 quoted-document suppression was added."""
    return [name for name, matcher in _BASELINE_MATCHERS.items() if matcher(prompt)]


def classify_candidate(prompt: str) -> list[str]:
    """CANDIDATE: the real, current hooks/routing_floor_classifier.py logic,
    imported directly so this harness can never silently drift from what the
    live hook actually does."""
    result = classify_candidate_raw(prompt)
    return list(result["injected_tiers"])


def load_cases(path: Path) -> list[dict]:
    cases = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{line_no}: malformed JSON: {e}") from e
    return cases


def verdict_for(expected: set[str], actual: set[str]) -> list[str]:
    """Return the verdict label(s) for one case: any of 'false_positive',
    'false_negative', or exactly one of 'correct'/'abstain' when neither
    applies. A case can carry both false_positive and false_negative labels
    at once (partial tier mismatch) -- none of the cases in the default set
    do, but the harness does not assume singleton tier sets."""
    labels = []
    if actual - expected:
        labels.append("false_positive")
    if expected - actual:
        labels.append("false_negative")
    if not labels:
        labels.append("abstain" if not expected else "correct")
    return labels


def run_replay(cases: list[dict]) -> dict:
    per_case = []
    counts = {
        "baseline": {"correct": 0, "abstain": 0, "false_positive": 0, "false_negative": 0},
        "candidate": {"correct": 0, "abstain": 0, "false_positive": 0, "false_negative": 0},
    }
    regressions = []
    improvements = []

    for case in cases:
        prompt = case["prompt"]
        expected = set(case.get("expected_tiers", []))

        baseline_actual = set(classify_baseline(prompt))
        candidate_actual = set(classify_candidate(prompt))

        baseline_verdict = verdict_for(expected, baseline_actual)
        candidate_verdict = verdict_for(expected, candidate_actual)

        for label in baseline_verdict:
            counts["baseline"][label] += 1
        for label in candidate_verdict:
            counts["candidate"][label] += 1

        baseline_ok = baseline_verdict in (["correct"], ["abstain"])
        candidate_ok = candidate_verdict in (["correct"], ["abstain"])

        record = {
            "id": case.get("id", "?"),
            "expected_tiers": sorted(expected),
            "baseline_tiers": sorted(baseline_actual),
            "baseline_verdict": baseline_verdict,
            "candidate_tiers": sorted(candidate_actual),
            "candidate_verdict": candidate_verdict,
            "tags": case.get("tags", []),
            "note": case.get("note", ""),
        }
        per_case.append(record)

        if baseline_ok and not candidate_ok:
            regressions.append(record)
        elif candidate_ok and not baseline_ok:
            improvements.append(record)

    return {
        "per_case": per_case,
        "counts": counts,
        "regressions": regressions,
        "improvements": improvements,
        "total": len(cases),
    }


def print_report(result: dict) -> None:
    total = result["total"]
    print(f"# Routing Replay Report — {total} case(s)\n")

    for variant in ("baseline", "candidate"):
        c = result["counts"][variant]
        print(f"## {variant.upper()}")
        print(f"  correct:         {c['correct']}")
        print(f"  abstain:         {c['abstain']}")
        print(f"  false_positive:  {c['false_positive']}")
        print(f"  false_negative:  {c['false_negative']}")
        print()

    print(f"## Regressions (baseline right, candidate wrong): {len(result['regressions'])}")
    for r in result["regressions"]:
        print(
            f"  - [{r['id']}] expected={r['expected_tiers']} candidate={r['candidate_tiers']} "
            f"verdict={r['candidate_verdict']} -- {r['note']}"
        )
    print()

    print(f"## Improvements (candidate right, baseline wrong): {len(result['improvements'])}")
    for r in result["improvements"]:
        print(
            f"  - [{r['id']}] expected={r['expected_tiers']} baseline={r['baseline_tiers']} "
            f"verdict={r['baseline_verdict']} -- {r['note']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    result = run_replay(cases)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_report(result)

    # Non-zero exit iff the CANDIDATE has any regression against baseline --
    # this is what would gate a future CI check, not enforced yet.
    return 1 if result["regressions"] else 0


if __name__ == "__main__":
    sys.exit(main())
