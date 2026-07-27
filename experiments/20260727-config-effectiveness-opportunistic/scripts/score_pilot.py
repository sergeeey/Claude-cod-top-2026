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

EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
RESULTS_FILE = EXPERIMENT_DIR / "results.json"
LOG_ROOT = EXPERIMENT_DIR / "logs"
N_PERMUTATIONS = 10000
SEED = 42
MCID = 0.2


def _safe_task_dir(task_id):
    """LOG_ROOT / task_id without containment checking lets a task-id like
    '../../etc' resolve outside logs/ -- flagged by an independent review
    (2026-07-27). task_id is operator-supplied here (not untrusted external
    input), so this is a hygiene fix, not an active exploit fix."""
    candidate = (LOG_ROOT / task_id).resolve()
    try:
        candidate.relative_to(LOG_ROOT.resolve())
    except ValueError:
        raise SystemExit(
            f"--task-id {task_id!r} resolves outside {LOG_ROOT} -- refusing."
        ) from None
    return candidate


def resolve_blind_grades(task_id, catch_1, catch_2, catch_3):
    """Translates anonymized Output_1/2/3 grades back to catch_a/b/c using the
    mapping written by anonymize_for_grading.py. This is the ONLY place the
    real A/B/C identity is looked up -- the grader never sees it. Added after
    an independent review flagged self-referential grading bias as an
    unaddressed gap (2026-07-27)."""
    mapping_file = _safe_task_dir(task_id) / "blind_mapping.json"
    if not mapping_file.exists():
        raise SystemExit(
            f"No blind mapping found at {mapping_file} -- run "
            f"anonymize_for_grading.py --task-id {task_id} first."
        )
    with open(mapping_file) as f:
        mapping = json.load(f)  # {"Output_1": "A", "Output_2": "C", ...}
    grades = {"Output_1": catch_1, "Output_2": catch_2, "Output_3": catch_3}
    by_letter = {mapping[k]: v for k, v in grades.items()}
    return by_letter["A"], by_letter["B"], by_letter["C"]


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
        # WHY: abs(risk_diff) alone can't tell "standard beats vanilla by 0.2"
        # from "standard LOSES to vanilla by 0.2" -- both satisfy |rd|>=MCID.
        # Split into magnitude (is the effect big enough to matter at all) and
        # direction (which way) so a regression can't silently print as a win.
        significant = p < 0.05
        magnitude_mcid_met = abs(risk_diff) >= MCID
        standard_better = risk_diff >= MCID and significant
        standard_worse = risk_diff <= -MCID and significant
        print(f"\n{label}:")
        print(f"  risk difference = {risk_diff:+.3f}")
        print(f"  permutation p   = {p:.4f}")
        print(f"  magnitude MCID met (|rd|>=0.2): {magnitude_mcid_met}")
        if standard_better:
            print("  direction: standard BETTER than comparator (MCID + significant)")
        elif standard_worse:
            print(
                "  direction: standard WORSE than comparator (MCID + significant)"
                " -- regression, not a win"
            )
        elif magnitude_mcid_met:
            print("  direction: magnitude met but p>=0.05 -- not yet distinguishable from noise")
        else:
            print("  direction: below MCID either way -- no practically important difference yet")
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
    ap.add_argument(
        "--blind",
        action="store_true",
        help="grade against anonymized Output_1/2/3 (see anonymize_for_grading.py) "
        "instead of knowing which copy is A/B/C -- MANDATORY for real pilot tasks "
        "per the 2026-07-27 blind-grading fix, optional for controls where the "
        "grader isn't the same person selecting tasks",
    )
    ap.add_argument(
        "--catch-1", type=int, choices=[0, 1], help="grade for anonymized Output_1 (--blind mode)"
    )
    ap.add_argument(
        "--catch-2", type=int, choices=[0, 1], help="grade for anonymized Output_2 (--blind mode)"
    )
    ap.add_argument(
        "--catch-3", type=int, choices=[0, 1], help="grade for anonymized Output_3 (--blind mode)"
    )
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
            if args.blind:
                if args.catch_1 is None or args.catch_2 is None or args.catch_3 is None:
                    ap.error("--catch-1/--catch-2/--catch-3 required with --blind")
                if args.catch_a is not None or args.catch_b is not None or args.catch_c is not None:
                    ap.error(
                        "--catch-a/b/c given alongside --blind -- that defeats the "
                        "point of blinding (it means you already know the mapping). "
                        "Use --catch-1/2/3 only in --blind mode."
                    )
                catch_a, catch_b, catch_c = resolve_blind_grades(
                    args.task_id, args.catch_1, args.catch_2, args.catch_3
                )
            else:
                if args.catch_a is None or args.catch_b is None or args.catch_c is None:
                    ap.error(
                        "--catch-a/--catch-b/--catch-c required unless "
                        "--exclude-reason/--blind is set"
                    )
                catch_a, catch_b, catch_c = args.catch_a, args.catch_b, args.catch_c
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
                    "catch_a": catch_a,
                    "catch_b": catch_b,
                    "catch_c": catch_c,
                    "graded_blind": args.blind,
                }
            )
            print(
                f"Recorded task {args.task_id}: A={catch_a} B={catch_b} "
                f"C={catch_c} (blind={args.blind})"
            )
        save_results(data)

    summarize(data)


if __name__ == "__main__":
    main()
