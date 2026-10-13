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


# Badness ranking used to compare two verdicts on the SAME case (baseline vs
# candidate) and decide whether the candidate got strictly better, strictly
# worse, or changed sideways. Fixed 2026-09-12 (skeptic-found): an earlier
# version returned a LIST of labels per case (e.g. both "false_positive" AND
# "false_negative" when expected/actual are disjoint non-empty sets) and
# incremented a counter per label -- for any case hitting that shape,
# sum(counts.values()) > total, so a reader computing accuracy from the
# printed counts got a silently wrong denominator. A single-label verdict
# with an explicit "mixed" bucket keeps sum(counts.values()) == total always.
_BADNESS = {"correct": 0, "abstain": 0, "false_positive": 1, "false_negative": 1, "mixed": 2}


def verdict_for(expected: set[str], actual: set[str]) -> str:
    """Return exactly ONE verdict label for one case: 'correct', 'abstain',
    'false_positive', 'false_negative', or 'mixed' (both a spurious tier AND
    a missing tier at once). Always exactly one label -- see _BADNESS above
    for why this replaced an earlier list-returning version."""
    fp = bool(actual - expected)
    fn = bool(expected - actual)
    if fp and fn:
        return "mixed"
    if fp:
        return "false_positive"
    if fn:
        return "false_negative"
    return "abstain" if not expected else "correct"


def run_replay(cases: list[dict]) -> dict:
    per_case = []
    counts = {
        "baseline": dict.fromkeys(_BADNESS, 0),
        "candidate": dict.fromkeys(_BADNESS, 0),
    }
    regressions = []
    improvements = []
    lateral_changes = []

    for case in cases:
        prompt = case["prompt"]
        expected = set(case.get("expected_tiers", []))

        baseline_actual = set(classify_baseline(prompt))
        candidate_actual = set(classify_candidate(prompt))

        baseline_verdict = verdict_for(expected, baseline_actual)
        candidate_verdict = verdict_for(expected, candidate_actual)

        counts["baseline"][baseline_verdict] += 1
        counts["candidate"][candidate_verdict] += 1

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

        # WHY compare by BADNESS rank rather than a binary ok/not-ok flag
        # (fixed 2026-09-12, skeptic-found): the earlier binary version only
        # ever compared "fully correct" against "anything else," so a
        # transition between two DIFFERENT wrong verdicts (e.g. baseline
        # "mixed" -> candidate "false_positive", a real partial improvement;
        # or the reverse, a real partial regression) fell into neither the
        # regressions nor improvements list and was silently invisible in the
        # report -- including to `main()`'s own exit code, which is meant to
        # gate a future CI check on "did the candidate regress at all."
        baseline_badness = _BADNESS[baseline_verdict]
        candidate_badness = _BADNESS[candidate_verdict]
        if candidate_badness > baseline_badness:
            regressions.append(record)
        elif candidate_badness < baseline_badness:
            improvements.append(record)
        elif baseline_verdict != candidate_verdict:
            lateral_changes.append(record)

    return {
        "per_case": per_case,
        "counts": counts,
        "regressions": regressions,
        "improvements": improvements,
        "lateral_changes": lateral_changes,
        "total": len(cases),
    }


def print_report(result: dict) -> None:
    total = result["total"]
    print(f"# Routing Replay Report — {total} case(s)\n")

    for variant in ("baseline", "candidate"):
        c = result["counts"][variant]
        print(f"## {variant.upper()}")
        for label in ("correct", "abstain", "false_positive", "false_negative", "mixed"):
            print(f"  {label + ':':<16} {c[label]}")
        print(f"  {'sum:':<16} {sum(c.values())} (must equal total {result['total']})")
        print()

    print(f"## Regressions (candidate got worse than baseline): {len(result['regressions'])}")
    for r in result["regressions"]:
        print(
            f"  - [{r['id']}] expected={r['expected_tiers']} "
            f"baseline={r['baseline_verdict']}->{r['baseline_tiers']} "
            f"candidate={r['candidate_verdict']}->{r['candidate_tiers']} -- {r['note']}"
        )
    print()

    print(f"## Improvements (candidate got better than baseline): {len(result['improvements'])}")
    for r in result["improvements"]:
        print(
            f"  - [{r['id']}] expected={r['expected_tiers']} "
            f"baseline={r['baseline_verdict']}->{r['baseline_tiers']} "
            f"candidate={r['candidate_verdict']}->{r['candidate_tiers']} -- {r['note']}"
        )
    print()

    print(
        f"## Lateral changes (both wrong, differently -- neither better nor worse by rank): "
        f"{len(result['lateral_changes'])}"
    )
    for r in result["lateral_changes"]:
        print(
            f"  - [{r['id']}] expected={r['expected_tiers']} "
            f"baseline={r['baseline_verdict']}->{r['baseline_tiers']} "
            f"candidate={r['candidate_verdict']}->{r['candidate_tiers']} -- {r['note']}"
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

    # Non-zero exit if the CANDIDATE has any regression OR lateral change
    # against baseline -- this is what would gate a future CI check, not
    # enforced yet. Lateral changes (both wrong, differently) are included
    # deliberately (skeptic-found, 2026-09-12): they are not obviously
    # "worse" by the badness rank, but a candidate that starts misfiring in a
    # NEW way on a case it previously got wrong deserves human review before
    # being silently waved through as a non-regression.
    return 1 if (result["regressions"] or result["lateral_changes"]) else 0


if __name__ == "__main__":
    sys.exit(main())
