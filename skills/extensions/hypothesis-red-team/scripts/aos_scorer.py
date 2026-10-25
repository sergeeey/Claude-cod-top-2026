#!/usr/bin/env python3
"""
Anti-Overfitting Score (AOS) — standalone CLI scorer.
Usage: python aos_scorer.py
Or import: from aos_scorer import compute_aos, full_audit
"""

import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StudyParams:
    # Preregistration (25 pts)
    preregistered: bool = False            # hypothesis + method on OSF before data
    epsilon_fixed_before: bool = False     # ε declared before seeing results

    # Alternative models (25 pts)
    n_alternative_models: int = 0          # number of rival models tested (not just H0)

    # Statistical rigor (25 pts)
    correct_test_TED_WD: bool = False      # TED or Wilcoxon for ratio tests (not TΔ)
    multiple_comparison: bool = False      # FWER or FDR correction applied
    power_80_pct: bool = False             # a priori power ≥ 0.80

    # Replication & robustness (25 pts)
    multiverse_analysis: bool = False      # all reasonable specs tested
    independent_replication: bool = False  # ≥ 2 independent datasets
    robust_fraction: float = 0.0           # share of multiverse specs supporting H1

    # Metadata (not scored)
    hypothesis_name: str = "Unnamed"
    domain: str = "Unknown"


def compute_aos(params: StudyParams) -> dict:
    blocks = {}

    # Preregistration block
    pre_score = 0
    if params.preregistered:        pre_score += 15
    if params.epsilon_fixed_before: pre_score += 10
    blocks["preregistration"] = {"score": pre_score, "max": 25}

    # Alternative models block
    alt_score = min(params.n_alternative_models * 5, 25)
    blocks["alternative_models"] = {"score": alt_score, "max": 25,
                                     "n_models": params.n_alternative_models}

    # Statistical rigor block
    stat_score = 0
    if params.correct_test_TED_WD:  stat_score += 8
    if params.multiple_comparison:  stat_score += 8
    if params.power_80_pct:         stat_score += 9
    blocks["statistical_rigor"] = {"score": stat_score, "max": 25}

    # Replication block
    rep_score = 0
    if params.multiverse_analysis:       rep_score += 10
    if params.independent_replication:   rep_score += 10
    if params.robust_fraction > 0.7:     rep_score += 5
    blocks["replication_robustness"] = {"score": rep_score, "max": 25,
                                         "robust_fraction": params.robust_fraction}

    total = sum(b["score"] for b in blocks.values())

    thresholds = [
        (85, "✅ CONFIRMATORY — publication as hypothesis confirmation justified"),
        (60, "⚠️ CONFIRMATORY WITH CAVEATS — publish with explicit limitations"),
        (40, "🔶 EXPLORATORY ONLY — label as hypothesis-generating, not confirming"),
        (0,  "❌ UNRELIABLE — do not publish as confirmation"),
    ]
    verdict = next(v for lo, v in thresholds if total >= lo)

    return {
        "hypothesis": params.hypothesis_name,
        "domain": params.domain,
        "total_score": total,
        "max_score": 100,
        "verdict": verdict,
        "blocks": blocks,
    }


def full_audit(params: StudyParams) -> str:
    result = compute_aos(params)
    lines = [
        f"═══ AOS AUDIT: {result['hypothesis']} ═══",
        f"Domain: {result['domain']}",
        "",
        "BLOCK SCORES:",
    ]
    for block_name, block in result["blocks"].items():
        bar = "█" * block["score"] + "░" * (block["max"] - block["score"])
        lines.append(f"  {block_name:30s} {block['score']:2d}/{block['max']} [{bar}]")

    lines += [
        "",
        f"TOTAL: {result['total_score']}/100",
        f"VERDICT: {result['verdict']}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    # Interactive mode
    print("=== Anti-Overfitting Score (AOS) Calculator ===\n")
    name   = input("Hypothesis name: ") or "Test"
    domain = input("Domain (biology/psychology/ML/other): ") or "other"

    def ask(q): return input(f"{q} [y/n]: ").lower().strip() == "y"
    def ask_int(q): return int(input(f"{q} [0-5]: ") or "0")
    def ask_float(q): return float(input(f"{q} [0.0-1.0]: ") or "0.0")

    params = StudyParams(
        hypothesis_name=name,
        domain=domain,
        preregistered=ask("Hypothesis preregistered on OSF before data collection?"),
        epsilon_fixed_before=ask("Tolerance ε fixed BEFORE seeing results?"),
        n_alternative_models=ask_int("Number of rival models tested (not just H0)?"),
        correct_test_TED_WD=ask("Using TED or Wilcoxon (NOT TΔ) for ratio tests?"),
        multiple_comparison=ask("Multiple comparison correction applied?"),
        power_80_pct=ask("A priori power analysis done, power ≥ 0.80?"),
        multiverse_analysis=ask("Multiverse analysis run?"),
        independent_replication=ask("Independent replication dataset exists?"),
        robust_fraction=ask_float("Share of multiverse specs supporting H1?"),
    )

    print("\n" + full_audit(params))
    print("\nJSON output:")
    print(json.dumps(compute_aos(params), indent=2))
