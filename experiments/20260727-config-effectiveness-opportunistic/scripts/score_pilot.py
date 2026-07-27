#!/usr/bin/env python3
"""score_pilot.py -- records one pilot task's graded catch/no-catch verdicts into
results.json and recomputes the running paired-permutation-test estimate for
exp 20260727-config-effectiveness-opportunistic.

Stdlib only, no scipy -- same from-scratch paired-permutation convention already
established this session in DNA Ladder's paired_permutation_test (reimplemented
here rather than imported, since this is a different repo/project).

Usage (record a new task):
  python score_pilot.py --task-id task01 --criterion "names the off-by-one at line 42" \
      --catch-a 0 --catch-b 1 --catch-c 1

Usage (just recompute/print current stats without adding a task):
  python score_pilot.py --recompute-only
"""

import argparse
import json
import random
from pathlib import Path

RESULTS_FILE = Path(__file__).resolve().parent.parent / "results.json"
N_PERMUTATIONS = 10000
SEED = 42
MCID = 0.2


def load_results():
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE) as f:
            return json.load(f)
    return {"controls": {}, "tasks": []}


def save_results(data):
    with open(RESULTS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def paired_permutation_test(diffs, n_perm, seed):
    """diffs: list of {-1, 0, +1} per-task paired differences (catch_C - catch_X).
    Tests whether the mean diff is far from what random sign-flips would produce."""
    n = len(diffs)
    observed = sum(diffs) / n
    rng = random.Random(seed)
    count_extreme = 0
    for _ in range(n_perm):
        flipped = sum(d if rng.random() < 0.5 else -d for d in diffs)
        if abs(flipped / n) >= abs(observed):
            count_extreme += 1
    p = (count_extreme + 1) / (n_perm + 1)
    return observed, p


def leave_one_out(diffs):
    """Does the sign of the observed mean diff flip if any single task is removed?"""
    if len(diffs) < 2:
        return None
    base_sign = (sum(diffs) > 0) - (sum(diffs) < 0)
    flips = []
    for i in range(len(diffs)):
        rest = diffs[:i] + diffs[i + 1 :]
        if not rest:
            continue
        rest_sign = (sum(rest) > 0) - (sum(rest) < 0)
        if rest_sign != base_sign:
            flips.append(i)
    return flips


def summarize(data):
    tasks = data["tasks"]
    n = len(tasks)
    print(f"\n=== Accumulated population: n={n} tasks ===")
    if n == 0:
        print("No tasks recorded yet.")
        return

    for label, key_x in (
        ("C vs A (standard vs vanilla)", "catch_a"),
        ("C vs B (standard vs minimal)", "catch_b"),
    ):
        diffs = [t["catch_c"] - t[key_x] for t in tasks]
        risk_diff, p = paired_permutation_test(diffs, N_PERMUTATIONS, SEED)
        loo_flips = leave_one_out(diffs)
        mcid_met = abs(risk_diff) >= MCID and p < 0.05
        print(f"\n{label}:")
        print(f"  risk difference = {risk_diff:+.3f}")
        print(f"  permutation p   = {p:.4f}")
        print(f"  MCID (|rd|>=0.2 AND p<0.05) met: {mcid_met}")
        if loo_flips:
            print(
                f"  ⚠ leave-one-out: removing task index {loo_flips} flips the sign "
                "-- fragile result, n too small"
            )
        elif n >= 2:
            print("  leave-one-out: sign stable under single-task removal")

    if n < 8:
        print(
            f"\nNote: pre-registered minimum N for a confirmatory verdict is 8 "
            f"(see claim.md). Current n={n} -- treat any verdict above as "
            "exploratory, not confirmatory, until n>=8."
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-id")
    ap.add_argument("--criterion", help="the pre-registered one-line catch criterion for this task")
    ap.add_argument("--catch-a", type=int, choices=[0, 1])
    ap.add_argument("--catch-b", type=int, choices=[0, 1])
    ap.add_argument("--catch-c", type=int, choices=[0, 1])
    ap.add_argument("--recompute-only", action="store_true")
    ap.add_argument(
        "--exclude-reason",
        help="if this task is being excluded per an ICE strategy, log why instead of scoring",
    )
    args = ap.parse_args()

    data = load_results()

    if not args.recompute_only:
        if not (args.task_id and args.criterion is not None):
            ap.error("--task-id and --criterion are required unless --recompute-only")
        if args.exclude_reason:
            data.setdefault("excluded_tasks", []).append(
                {
                    "task_id": args.task_id,
                    "criterion": args.criterion,
                    "exclude_reason": args.exclude_reason,
                }
            )
            print(f"Logged EXCLUDED task {args.task_id}: {args.exclude_reason}")
        else:
            if args.catch_a is None or args.catch_b is None or args.catch_c is None:
                ap.error("--catch-a/--catch-b/--catch-c required unless --exclude-reason is set")
            existing = [t for t in data["tasks"] if t["task_id"] == args.task_id]
            if existing:
                ap.error(
                    f"task_id {args.task_id} already recorded -- use a new "
                    "task_id or edit results.json directly"
                )
            data["tasks"].append(
                {
                    "task_id": args.task_id,
                    "criterion": args.criterion,
                    "catch_a": args.catch_a,
                    "catch_b": args.catch_b,
                    "catch_c": args.catch_c,
                }
            )
            print(
                f"Recorded task {args.task_id}: A={args.catch_a} B={args.catch_b} C={args.catch_c}"
            )
        save_results(data)

    summarize(data)


if __name__ == "__main__":
    main()
