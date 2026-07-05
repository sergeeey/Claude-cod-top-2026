# ach_matrix.md — [EXPERIMENT-ID]
# Optional artifact. Use ONLY when ≥2 hypotheses are simultaneously alive for the
# same underlying question (see claim.md HD-MAVP Assumptions `status` column).
# For a single working hypothesis, skip this file entirely — use the plain
# Cheapest Differentiating Test Protocol Selection Rule in falsification-ladder.md.
# Source: Heuer (1999) Analysis of Competing Hypotheses; Platt (1964) Strong Inference.
# This is a template-only artifact — no hook enforces it, no promotion gate checks it.

## Competing Hypotheses
_List every hypothesis currently alive for this question. If only 1 row applies,
delete this file — a 1-column matrix has nothing to discriminate._

| ID | Hypothesis | Status |
|---|---|---|
| H1 | | alive / weak_alive / parked / killed / hard_killed |
| H2 | | alive / weak_alive / parked / killed / hard_killed |

---

## Matrix
_Score each cell: `C` consistent with this hypothesis / `I` inconsistent /
`N/A` no discriminating power. A row with the SAME symbol across every column
is non-diagnostic — it does not help you choose between hypotheses. Deprioritize it._

| Evidence / Test | Cost | H1 | H2 | Diagnostic? | Priority |
|---|---|---|---|---|---|
| | | C / I / N/A | C / I / N/A | yes / no (non-diagnostic if all cells match) | run next / deferred / done |

_Selection rule (same spirit as Cheapest Differentiating Test Protocol): prefer
high-diagnosticity rows over low-cost-but-non-diagnostic ones. A cheap test that
doesn't discriminate is not a valid cheapest test._

---

## Decisive Test Log
_After running the highest-priority row, record what it eliminated._

| Test run | Result | Hypotheses eliminated | Surviving hypotheses |
|---|---|---|---|
| | | | |

---

## Terminal State
- [ ] Exactly 1 hypothesis survives → promote to claim.md as the working hypothesis
- [ ] 0 hypotheses survive → all REJECT; run Kill Analysis in decision.md for each
- [ ] ≥2 hypotheses survive, no affordable differentiating test remains → mark
      remaining hypotheses `parked` (see falsification-ladder.md § Adaptive
      Iteration — Branch Rule) with an explicit revival condition

## Notes
_Non-diagnostic evidence collected along the way, kept for audit trail only._
