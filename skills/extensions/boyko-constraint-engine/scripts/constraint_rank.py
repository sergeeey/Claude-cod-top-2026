#!/usr/bin/env python3
"""Rank several simultaneous constraints from a table of "fix subset S" runs.

Input (JSON, file path or stdin):
  {
    "metric": "answer_accuracy", "higher_is_better": true,
    "noise": 0.01,       # per-run std of the metric (repeated baseline runs). Required.
    "repeats": 4,        # runs averaged per table row. Required: it sets the standard errors.
    "mcid": 0.03,        # smallest gain that matters (fixed BEFORE the runs)
    "constraints": ["retrieval", "packing", "prompt"],
    "costs": {"retrieval": 3, "packing": 1, "prompt": 1},
    "runs": [ {"fixed": [], "value": 0.62}, {"fixed": ["packing"], "value": 0.74}, ... ]
  }
A run's value is the end metric (mean of `repeats` runs) when only the constraints in
"fixed" are removed (oracle-substituted or minimally patched). value=null means NOT
MEASURED: such a row is treated as missing, never as zero.

Thresholds come from standard errors, not from the raw noise:
  SE of a difference of two rows            = noise * sqrt(2 / repeats)
  SE of an interaction (four rows combined) = 2 * noise / sqrt(repeats)
and a margin of Z=2 standard errors is required before anything is called real,
additive or interacting. The ceiling covers ONLY the listed constraints: a verdict
NO_CONSTRAINT_DETECTED means "among the listed candidates".

Output: JSON with solo gains, leave-one-out gains, pairwise interactions, Shapley shares
(only on a complete table), the conserved-budget ratio, a priority order and a verdict.
Stdlib only. Exit code 0 except unreadable input (2).
"""

from __future__ import annotations

import itertools
import json
import sys
from math import factorial, isfinite, sqrt
from typing import Any

MAX_FULL = 6  # full 2^k table is only asked for up to this many constraints
Z = 2.0  # margin in standard errors
EPS = 1e-9  # absolute floor for margins when noise is 0
DOMINANCE = 0.7  # share of the gap; heuristic, no calibration behind it


def _load(argv: list[str]) -> dict[str, Any]:
    with open(argv[1], encoding="utf-8") if len(argv) > 1 else sys.stdin as fh:
        return json.loads(fh.read())


def rank(spec: dict[str, Any]) -> dict[str, Any]:
    names: list[str] = list(spec["constraints"])
    sign = 1.0 if spec.get("higher_is_better", True) else -1.0
    noise = spec.get("noise")
    repeats = spec.get("repeats")
    mcid = spec.get("mcid")
    raw_costs = spec.get("costs") or {}
    if not isinstance(raw_costs, dict):
        raise ValueError('"costs" must be an object {constraint: cost}')
    if len(set(names)) != len(names):
        raise ValueError("duplicate names in constraints")
    for label, val in (("noise", noise), ("repeats", repeats)):
        if val is not None and (isinstance(val, bool) or not isfinite(float(val))):
            raise ValueError(f'"{label}" must be a finite number')
    if noise is not None and noise < 0:
        raise ValueError('"noise" must be >= 0')
    if repeats is not None and repeats <= 0:
        raise ValueError('"repeats" must be > 0')
    missing_costs = [n for n in names if raw_costs and n not in raw_costs]
    costs = {n: float(raw_costs.get(n, 1.0)) for n in names}
    out: dict[str, Any] = {
        "metric": spec.get("metric"),
        "scope_note": "ceiling covers listed constraints only",
    }

    if not names:
        out["verdict"] = "UNDEFINED"
        out["reason"] = "no constraints listed: nothing to rank"
        return out
    bad_cost = [n for n, c in costs.items() if not c > 0]
    if bad_cost or missing_costs:
        out["verdict"] = "UNDEFINED"
        out["reason"] = (
            f"costs must be given for every constraint and be positive "
            f"(non-positive: {bad_cost}, missing: {missing_costs})"
        )
        return out

    v: dict[frozenset[str], float] = {}
    not_measured = 0
    duplicates: list[list[str]] = []
    unknown: set[str] = set()
    for r in spec["runs"]:
        if not isinstance(r["fixed"], list):
            raise ValueError(f'"fixed" must be a list, got {r["fixed"]!r}')
        key = frozenset(r["fixed"])
        unknown |= key - set(names)
        if r.get("value") is None:
            not_measured += 1
            continue
        val = float(r["value"])
        if not isfinite(val):
            raise ValueError(f"non-finite value for fixed={sorted(key)}")
        if key in v:
            duplicates.append(sorted(key))
        v[key] = sign * val
    out["not_measured_runs"] = not_measured
    if unknown:
        out["verdict"] = "UNDEFINED"
        out["reason"] = f"runs mention constraints not in the list: {sorted(unknown)}"
        return out
    if duplicates:
        out["verdict"] = "UNDEFINED"
        out["reason"] = (
            f"several rows for the same subset (pre-average them and set repeats): {duplicates}"
        )
        return out

    empty, full = frozenset(), frozenset(names)
    if empty not in v:
        out["verdict"] = "UNDEFINED"
        out["reason"] = "no baseline run (fixed=[]): nothing to compare against"
        return out

    base = v[empty]
    total_gap = (v[full] - base) if full in v else None
    solo = {n: v[frozenset([n])] - base for n in names if frozenset([n]) in v}
    loo = {n: v[full] - v[full - {n}] for n in names if full in v and (full - {n}) in v}
    out.update(total_gap=total_gap, solo_gain=solo, leave_one_out_gain=loo)

    have_se = noise is not None and repeats is not None and repeats > 0
    se_diff = noise * sqrt(2.0 / repeats) if have_se else None
    se_int = 2.0 * noise / sqrt(repeats) if have_se else None
    m_diff = max(Z * se_diff, EPS) if have_se else None  # EPS: float residue is not an effect
    m_int = max(Z * se_int, EPS) if have_se else None
    out["noise_known"] = have_se
    out["margin_diff"] = m_diff
    out["margin_interaction"] = m_int

    # Only meaningful when the whole gap is above noise and every solo run exists.
    if have_se and total_gap is not None and total_gap > m_diff and len(solo) == len(names):
        out["budget_ratio_sum_solo_over_total"] = sum(solo.values()) / total_gap
    harmful = [c for c, g in solo.items() if have_se and g < -m_diff]
    if harmful:
        out["harmful_when_fixed"] = (
            harmful  # fixing it lowers the metric: probe artefact or real trade-off
        )

    inter: dict[str, Any] = {}
    for a, b in itertools.combinations(names, 2):
        keys = [frozenset([a, b]), frozenset([a]), frozenset([b])]
        if not all(k in v for k in keys):
            continue
        i_ab = v[keys[0]] - v[keys[1]] - v[keys[2]] + base
        if not have_se:
            kind = "unclassified (noise or repeats unknown)"
        elif abs(i_ab) <= m_int:
            kind = "additive"
        else:
            kind = (
                "complementary (need both)"
                if i_ab > 0
                else "overlapping (one captures part of the other)"
            )
        inter[f"{a}+{b}"] = {"interaction": i_ab, "kind": kind}
    out["pairwise"] = inter

    masked: list[str] = []
    if have_se:
        for a, b in itertools.permutations(names, 2):
            ab, bb = frozenset([a, b]), frozenset([b])
            if a in solo and b in solo and ab in v and bb in v:
                if solo[b] > m_diff and abs(solo[a]) <= m_diff and (v[ab] - v[bb]) > m_diff:
                    masked.append(f"{a} (hidden behind {b})")
        # k >= 5 designs have no pair rows: a constraint with no solo effect but a real
        # leave-one-out effect is hidden behind the others.
        for c in names:
            hider = any(solo[o] > m_diff for o in solo if o != c)
            if hider and c in solo and c in loo and abs(solo[c]) <= m_diff and loo[c] > m_diff:
                if not any(m.startswith(f"{c} (") for m in masked):
                    masked.append(f"{c} (hidden; seen only via leave-one-out)")
    out["masked"] = masked

    complete = len(names) <= MAX_FULL and all(
        frozenset(c) in v for k in range(len(names) + 1) for c in itertools.combinations(names, k)
    )
    shares: dict[str, float] | None = None
    if complete:
        n = len(names)
        shares = {}
        for i in names:
            others = [x for x in names if x != i]
            s = 0.0
            for k in range(len(others) + 1):
                for c in itertools.combinations(others, k):
                    sc = frozenset(c)
                    s += factorial(k) * factorial(n - k - 1) / factorial(n) * (v[sc | {i}] - v[sc])
            shares[i] = s
    out["shapley"] = shares
    out["table_complete"] = complete

    # Priority: Shapley when the table is complete; otherwise the larger of the solo and
    # leave-one-out gains, so a complementary or masked constraint is not ranked last.
    if shares is not None:
        basis, basis_name = shares, "shapley"
    else:
        keys_all = set(solo) | set(loo)
        basis = {c: max(solo.get(c, float("-inf")), loo.get(c, float("-inf"))) for c in keys_all}
        basis_name = "max(solo_gain, leave_one_out_gain)"
    priority = sorted(basis, key=lambda x: basis[x] / costs[x], reverse=True)
    out["priority_basis"] = basis_name
    out["priority"] = [
        {"constraint": c, "gain": basis[c], "cost": costs[c], "gain_per_cost": basis[c] / costs[c]}
        for c in priority
    ]

    if not have_se:
        out["verdict"] = "UNCLASSIFIED"
        out["reason"] = (
            "noise and repeats are both required: effects cannot be separated from run-to-run variation"
        )
    elif total_gap is None:
        out["verdict"] = "UNDEFINED"
        out["reason"] = "no run with every listed constraint fixed: the ceiling is unknown"
    elif (
        total_gap <= m_diff
        and any(g > m_diff for g in solo.values())
        and (
            any(g < -m_diff for g in solo.values())
            or any(x["interaction"] < -m_int for x in inter.values())
        )
    ):
        # A beneficial solo effect AND evidence of cancellation: a harmful solo effect, or a
        # significantly negative pair interaction (A and B help alone but cancel together).
        out["verdict"] = "TRADE_OFF"
        out["reason"] = (
            f"fixing all gains only {total_gap:.4g}, yet some constraint helps on its own: "
            "the constraints cancel each other (trade-off). This is not a null result"
        )
    elif total_gap < -m_diff:
        out["verdict"] = "ANOMALOUS_NEGATIVE_GAP"
        out["reason"] = (
            f"fixing everything LOWERS the metric by {-total_gap:.4g}: suspect an oracle that breaks "
            "downstream stages, or a real trade-off; this is not a null result"
        )
    elif total_gap <= m_diff:
        out["verdict"] = "NO_CONSTRAINT_DETECTED"
        out["reason"] = (
            f"among the listed candidates: fixing all gains {total_gap:.4g} <= margin {m_diff:.4g} "
            f"(2 SE, noise {noise}, repeats {repeats}); an unlisted constraint is not excluded"
        )
        helps = [c for c, g in solo.items() if g > m_diff]
        if helps:
            out["warning"] = f"{helps} help on their own although the all-fixed gap is within noise: check for cancelling effects"
    elif mcid is not None and total_gap < mcid:
        out["verdict"] = "BELOW_MCID"
        out["reason"] = f"real gap {total_gap:.4g} is below the smallest gain that matters ({mcid})"
    elif len(solo) < len(names):
        missing = [n for n in names if n not in solo]
        out["verdict"] = "UNCLASSIFIED"
        out["reason"] = (
            f"solo rows missing for {missing}: dominance cannot be told from substitution "
            "(an unmeasured row can flip the conclusion); priority shown is provisional"
        )
    else:
        dom_basis = shares if shares is not None else solo
        big = [c for c, g in dom_basis.items() if g >= DOMINANCE * total_gap and g > m_diff]
        real = [c for c, g in basis.items() if g > m_diff]
        if masked:
            out["verdict"] = "MASKED_CONSTRAINTS"
        elif len(big) == 1:
            out["verdict"] = "SINGLE_DOMINANT"
        elif len(big) >= 2:
            out["verdict"] = "MULTIPLE_CONSTRAINTS"
            out["note"] = (
                "several constraints each reach the dominance share: they overlap (substitutes)"
            )
        elif real and any(g > m_diff for g in solo.values()):
            out["verdict"] = "MULTIPLE_CONSTRAINTS"
        else:
            out["verdict"] = "NO_SINGLE_BOTTLENECK_FOUND"
        if mcid is not None:
            below = [c for c, g in basis.items() if m_diff < g < mcid]
            if below:
                out["gray_zone"] = below
    return out


def main(argv: list[str]) -> int:
    try:
        spec = _load(argv)
        result = rank(spec)
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        print(json.dumps({"verdict": "UNDEFINED", "error": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
