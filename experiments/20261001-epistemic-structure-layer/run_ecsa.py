"""Run `scripts/claim_cutsets.py` on the two subjects fixed in `rules/ecsa_extraction.md`.

Deterministic, no randomness. Writes `metrics/ecsa_run.json`; nothing in it is retyped by hand.

    python experiments/20261001-epistemic-structure-layer/run_ecsa.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "scripts"))

import claim_cutsets as cc  # noqa: E402

MAX_SETS = 5000
E2_LOGIC = "H = T1 & T2 & T3 & T4 & T5"  # source states "passing all 5"; no OR quoted
# Declared by the sources, fixed in rules/ecsa_extraction.md before this run.
DECLARED = {"E1_two_source_gate": ["C5", "C6"], "E2_evidence_chain_verifier": ["T4"]}


def main() -> int:
    e1 = cc.decomposer_analysis(
        (HERE / "data/e1_two_source_gate.txt").read_text(encoding="utf-8"), None, MAX_SETS
    )
    e2 = cc.analyze(cc.parse_logic(E2_LOGIC), {}, MAX_SETS)
    subjects = {"E1_two_source_gate": e1, "E2_evidence_chain_verifier": e2}
    summary: dict[str, dict[str, Any]] = {}
    for name, res in subjects.items():
        singles = res.get("singleton_failures", [])
        summary[name] = {
            "only_and_logic": res.get("only_and_logic"),
            "kappa": res.get("kappa"),
            "computed_singleton_failures": singles,
            "source_declared_critical": DECLARED[name],
            "has_or_structure": not res.get("only_and_logic", True),
            "computed_minus_declared": sorted(set(singles) - set(DECLARED[name])),
        }
    out = {
        "subjects": subjects,
        "summary": summary,
        "claims_with_or_structure": sum(1 for s in summary.values() if s["has_or_structure"]),
        "independent_claims": len(subjects),
    }
    target = HERE / "metrics"
    target.mkdir(exist_ok=True)
    (target / "ecsa_run.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    n_or, n_all = out["claims_with_or_structure"], out["independent_claims"]
    print(f"claims_with_or_structure: {n_or} of {n_all}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
