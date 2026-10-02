"""Run `scripts/ach_quotient.py` on the committed, hand-extracted matrices (W2 headroom).

Deterministic: fixed seed and trial count (fixed BEFORE the first run). Writes
`metrics/eqr_run.json`; nothing in that file is retyped by hand.

    python experiments/20261001-epistemic-structure-layer/run_eqr.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "scripts"))

import ach_quotient as aq  # noqa: E402

SEED = 7
TRIALS = 10000
SUBJECTS = {
    "S1_lakes_negative_controls": "data/lakes_negative_controls.json",
    "S2_install_tournament": "data/install_tournament.json",
}


def main() -> int:
    out: dict[str, object] = {"seed": SEED, "trials": TRIALS, "subjects": {}}
    subjects: dict[str, object] = {}
    for name, rel in SUBJECTS.items():
        m = aq.load_matrix(HERE / rel)
        subjects[name] = {
            "classes": aq.summarize(m),
            "identify": aq.identify(m),
            "floor": aq.floor_null(m, trials=TRIALS, seed=SEED),
            "row_essential": aq.row_essential(m),
        }
    out["subjects"] = subjects
    target = HERE / "metrics"
    target.mkdir(exist_ok=True)
    (target / "eqr_run.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
