#!/usr/bin/env python3
"""Expected Information Gain (EIG) for ach_matrix.md's optional quantitative section.

WHY: ach_matrix.md's `Diagnostic?` column is binary (yes/no) -- two tests can both
score "yes" while one barely moves belief between hypotheses and the other is
decisive. EIG (Lindley 1956 "On a measure of the information provided by an
experiment"; equivalently mutual information I(H;O|t) between the test outcome
and the hypothesis) gives a real number instead of a yes/no, without pulling in
Free Energy Principle or any of its philosophical baggage -- this is plain
Bayesian experimental design, evaluated and pearl-registered on 2026-09-14
(see ~/.claude/rules/pearl_registry/INDEX.md, same date).

RELATIONSHIP TO THE EXISTING SHADOW HEURISTIC (corrected -- skeptic-found,
2026-09-14 review, first draft of this docstring overclaimed the opposite):
this is the closest computable proxy for the "information_gain" factor in
scripts/promotion_score_observer.py's shadow-only priority formula
(expected_value x falsifiability x information_gain x evidence_independence /
expected_cost) -- but the SAME pearl_registry entry this module cites also
records that EIG likely does NOT cleanly isolate that one factor: a test with
high EIG structurally also has high "kill_power" (driving a posterior toward
0/1 is both at once under different names). Do not wire this into that shadow
formula without first resolving that double-counting risk -- this module
computes a number, it does not license folding it into a composite score.

STATUS -- read before assuming this is settled (skeptic-found, 2026-09-14
review): the SAME pearl_registry entry this module cites recorded this
section's status as `pending [SPECULATIVE]` with an explicit instruction --
"Do not add to the live template until a real tied-diagnostic case actually
occurs; do not manufacture one to force the check." This module and the
ach_matrix.md section below were added to the live template anyway, on the
user's own explicit instruction ("реализуй, протестируй" -- overriding that
deferral is the user's call to make, not this module's to inherit silently).
That override is recorded in the pearl_registry entry itself, not left
implicit here -- see the entry's updated status before trusting either
document's framing on its own.

HARD GATING RULE (the actual point of this module, not a footnote): quantitative
EIG is only meaningful when P(outcome | hypothesis, test) is independently
justified or empirically estimated. An LLM inventing "H1 predicts Y with
probability 0.73" out of thin air is exactly the failure mode
skeptic-triggers.md / validation_theater_guard.py already exist to catch --
precision theater with a log in it. This module computes the number correctly
IF you give it real probabilities; it has no way to check whether your inputs
are real, and does not try to. That check is the caller's job, per
falsification-ladder.md's own Zero-Signal Gate discipline: garbage in is a
finding about the input, not something this function can detect.

Does NOT modify ach_matrix.md's existing C/I/N/A qualitative column or its
Diagnostic? decision -- this is a strictly additive, optional companion. No
hook enforces this file's use; no promotion gate reads its output. Matches
ach_matrix.md's own header: "no hook enforces it, no promotion gate checks it".

Usage:
    python scripts/eig_calculator.py --demo
        # runs the two worked examples from the 2026-09-14 pearl entry

    python scripts/eig_calculator.py --priors '{"H1":0.5,"H2":0.5}' \\
        --likelihoods '{"H1":{"pos":0.9,"neg":0.1},"H2":{"pos":0.1,"neg":0.9}}'
        # computes EIG for real inputs -- this is the actual filling-in path
        # ach_matrix.md's template points to; --demo alone cannot do this
        # (skeptic-found, 2026-09-14: the template said "compute with this
        # script" while the script only ran two hardcoded examples)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class EIGResult:
    """Result of an EIG computation, carrying enough to audit the number later.

    WHY carry inputs, not just the bit count (audit-verification-gate.md):
    a bare "EIG = 0.53 bits" six months from now is unauditable -- was it a
    real estimate, a default, or a typo? Round-tripping the inputs alongside
    the output lets a later reader check the arithmetic without re-deriving
    it from a decision.md prose paragraph.
    """

    eig_bits: float
    priors: dict[str, float]
    likelihoods: dict[str, dict[str, float]]  # hypothesis -> {outcome: P(outcome|hypothesis)}
    marginal_outcome: dict[str, float]  # P(outcome), for audit


class EIGInputError(ValueError):
    """Raised when priors/likelihoods are not a valid probability distribution.

    WHY a distinct exception, not a bare ValueError (skeptic-triggers.md
    discipline): the caller (a human filling ach_matrix.md, or a future skill)
    needs to distinguish "your numbers don't sum to 1" from any other bug --
    that distinction IS the enforcement of the gating rule this module exists
    to carry. Swallowing it into a generic ValueError would make that harder
    to catch programmatically later.
    """


_PROB_TOLERANCE = 1e-6


def _check_distribution(values: dict[str, float], label: str) -> None:
    """Validate one probability distribution.

    WHY isfinite checked FIRST, before any arithmetic on the value (skeptic-found,
    2026-09-14: `abs(nan - 1.0) > tol` and `nan < 0.0` are both False in Python --
    a NaN prior silently passed this check and produced a NaN EIGResult instead
    of an error. A NaN is exactly the shape a real caller can produce -- 0/0 from
    an empty historical bucket, the "empirically measured rate" this module's own
    gating rule recommends -- so this is not a hypothetical input.

    WHY the same tolerance for the per-value bound as for the sum (skeptic-found,
    2026-09-14: the first version used an exact [0.0, 1.0] bound here but a
    tolerant sum check above -- a value like 1.0000000001 from float roundoff in
    an upstream normalization would fail the per-value check while being fine by
    the sum check's own standard. One tolerance, applied consistently, closes
    that inconsistency instead of papering over one occurrence of it.
    """
    for key, v in values.items():
        if not math.isfinite(v):
            raise EIGInputError(f"{label}[{key!r}] = {v!r} is not a finite number")
        if v < -_PROB_TOLERANCE or v > 1.0 + _PROB_TOLERANCE:
            raise EIGInputError(f"{label}[{key!r}] = {v!r} is not a valid probability")
    total = sum(values.values())
    if not math.isfinite(total) or abs(total - 1.0) > _PROB_TOLERANCE:
        raise EIGInputError(f"{label} must sum to 1.0, got {total!r}: {values!r}")


def expected_information_gain(
    priors: dict[str, float],
    likelihoods: dict[str, dict[str, float]],
) -> EIGResult:
    """Compute EIG(t) = E_{y~p(y|t)}[D_KL(p(H|y,t) || p(H))] = I(H; Y | t), in bits.

    Args:
        priors: P(H_i) for each hypothesis id, must sum to 1.
        likelihoods: for each hypothesis id, P(outcome | hypothesis) over the
            SAME set of possible outcomes for every hypothesis -- each inner
            dict must independently sum to 1 (it is a conditional distribution
            over outcomes given that one hypothesis is true).

    Returns:
        EIGResult with the bit count and the exact inputs/marginal used, so
        the result can be audited later without re-deriving it by hand.

    Raises:
        EIGInputError: priors or any likelihood row is not a valid distribution,
            or a hypothesis in `priors` has no matching row in `likelihoods`,
            or the outcome sets disagree between hypotheses (an outcome must
            mean the same thing under every hypothesis to be summed over).

    WHY this exact formula and not a KL-divergence-of-posteriors implementation
    (mathematically equivalent, verified by hand against both this session's
    worked examples before this module was written -- see tests): expanding
    mutual information as a double sum over (hypothesis, outcome) pairs avoids
    computing every one of the 2^|outcomes| possible posteriors explicitly --
    this scales to any outcome-set size with the same two nested sums.
    """
    _check_distribution(priors, "priors")
    if len(priors) < 2:
        # WHY (skeptic-found, 2026-09-14): a single hypothesis has nothing to
        # discriminate from -- ach_matrix.md's own header says so explicitly
        # ("a 1-column matrix has nothing to discriminate"). Silently returning
        # EIG=0 here would be mathematically correct and semantically useless;
        # this is the same "garbage in" case the module's docstring already
        # claims to reject, just one this code didn't actually reject before.
        raise EIGInputError(
            f"need >=2 hypotheses to compute a discriminating test's value, got {sorted(priors)}"
        )
    if set(priors) != set(likelihoods):
        raise EIGInputError(
            f"priors and likelihoods must name the same hypotheses: "
            f"{sorted(priors)} vs {sorted(likelihoods)}"
        )
    for h, dist in likelihoods.items():
        _check_distribution(dist, f"likelihoods[{h!r}]")

    outcome_sets = {h: frozenset(dist) for h, dist in likelihoods.items()}
    distinct_outcome_sets = set(outcome_sets.values())
    if len(distinct_outcome_sets) > 1:
        raise EIGInputError(
            "every hypothesis must define P(outcome|H) over the SAME outcome "
            f"set (an outcome must mean the same thing under every H): {outcome_sets!r}"
        )
    outcomes = next(iter(distinct_outcome_sets))

    marginal: dict[str, float] = {
        o: sum(priors[h] * likelihoods[h][o] for h in priors) for o in outcomes
    }

    bits = 0.0
    for h, prior_h in priors.items():
        for o in outcomes:
            p_o_given_h = likelihoods[h][o]
            p_o = marginal[o]
            if p_o_given_h <= 0.0 or p_o <= 0.0:
                continue  # 0 * log(0/x) contributes 0 to mutual information by convention
            bits += prior_h * p_o_given_h * math.log2(p_o_given_h / p_o)

    return EIGResult(
        eig_bits=bits,
        priors=dict(priors),
        # WHY a nested copy, not dict(likelihoods) (skeptic-found, 2026-09-14):
        # dict(likelihoods) only copies the outer dict -- the inner {outcome: p}
        # dicts stayed shared with the caller's own objects, so mutating one
        # after the call silently changed an already-returned, frozen-looking
        # EIGResult. @dataclass(frozen=True) only blocks reassigning the field,
        # not mutating what it points to.
        likelihoods={h: dict(dist) for h, dist in likelihoods.items()},
        marginal_outcome=marginal,
    )


def _demo() -> None:
    """The two worked examples from the 2026-09-14 pearl_registry entry, run for
    real instead of re-quoted from prose -- so this module's own README claim
    (it reproduces those numbers) is checked by running it, not just asserted."""
    priors = {"H1": 0.5, "H2": 0.5}

    test_a = expected_information_gain(
        priors, {"H1": {"pos": 0.9, "neg": 0.1}, "H2": {"pos": 0.1, "neg": 0.9}}
    )
    test_b = expected_information_gain(
        priors, {"H1": {"pos": 0.6, "neg": 0.4}, "H2": {"pos": 0.4, "neg": 0.6}}
    )

    print("Test A (strong):  P(pos|H1)=0.9, P(pos|H2)=0.1")
    print(f"  EIG = {test_a.eig_bits:.4f} bits")
    print("Test B (weak):    P(pos|H1)=0.6, P(pos|H2)=0.4")
    print(f"  EIG = {test_b.eig_bits:.4f} bits")
    print()
    print("Both would score 'Diagnostic: yes' under ach_matrix.md's existing C/I/N/A")
    print("column (H1 and H2 disagree in direction on both tests) -- EIG shows they")
    print("are not remotely equal: Test A is ~18x more informative than Test B.")


def main() -> int:
    # WHY --priors/--likelihoods exist at all (skeptic-found, 2026-09-14):
    # ach_matrix.md's template said "compute with this script" while the only
    # runnable path was --demo's two hardcoded examples -- a user filling in
    # their own real numbers had no way to actually use this CLI and would
    # have had to write a Python one-liner the template never mentioned.
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--demo", action="store_true", help="run the two worked examples")
    parser.add_argument(
        "--priors", help='JSON object, e.g. \'{"H1":0.5,"H2":0.5}\' -- must sum to 1'
    )
    parser.add_argument(
        "--likelihoods",
        help='JSON object, e.g. \'{"H1":{"pos":0.9,"neg":0.1},"H2":{"pos":0.1,"neg":0.9}}\' '
        "-- one row per hypothesis, each row must sum to 1 over the SAME outcome names",
    )
    args = parser.parse_args()

    if args.demo:
        _demo()
        return 0

    if args.priors or args.likelihoods:
        if not (args.priors and args.likelihoods):
            parser.error("--priors and --likelihoods must both be given together")
        try:
            priors = json.loads(args.priors)
            likelihoods = json.loads(args.likelihoods)
        except json.JSONDecodeError as e:
            parser.error(f"invalid JSON: {e}")
            return 2  # unreachable -- parser.error() exits; keeps mypy happy about return type
        try:
            result = expected_information_gain(priors, likelihoods)
        except EIGInputError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(f"EIG = {result.eig_bits:.4f} bits")
        print(f"marginal outcome distribution: {result.marginal_outcome}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
