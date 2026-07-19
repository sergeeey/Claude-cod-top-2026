# ach_matrix.md — prediction matrix template

Optional artifact. Use ONLY when ≥2 hypotheses are simultaneously alive for the
same underlying question. For a single working hypothesis, skip this file
entirely — a 1-column matrix has nothing to discriminate.

Source: Heuer (1999) Analysis of Competing Hypotheses; Platt (1964) Strong Inference.
This is a template-only artifact — no hook enforces it, it is a thinking aid.

## Competing Hypotheses

_List every hypothesis currently alive for this question._

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

_Selection rule: prefer high-diagnosticity rows over low-cost-but-non-diagnostic ones.
A cheap test that doesn't discriminate is not a valid crucial test._

---

## Optional: Weighted Reranking

_Use only if you need to re-prioritize surviving hypotheses under different
criteria weights WITHOUT rerunning any test — e.g. "if we cared more about cost
than certainty, which hypothesis wins?" Skip this section if C/I/N/A is enough._

Score each hypothesis 0–5 per criterion (not per evidence row — this is a
separate, coarser view for weighting trade-offs).

| Criterion | Weight | H1 score (0-5) | H2 score (0-5) |
|---|---|---|---|
| Evidence support (from Matrix above) | | | |
| Cost to fully validate | | | |
| Reuse value for other alive branches | | | |
| **Weighted total** | — | | |

Recompute the weighted total with different weights to see if the ranking
changes — this does NOT require rerunning any test, only re-scoring the
weights column. If ranking flips easily under small weight changes, treat the
current leader as fragile, not settled.

---

## Decisive Test Log

_After running the highest-priority row, record what it eliminated._

| Test run | Result | Hypotheses eliminated | Surviving hypotheses |
|---|---|---|---|
| | | | |

---

## Terminal State

- [ ] Exactly 1 hypothesis survives → this is the working hypothesis going forward
- [ ] 0 hypotheses survive → all REJECT; state explicitly what killed each and what it does NOT rule out
- [ ] ≥2 hypotheses survive, no affordable differentiating test remains → mark
      remaining hypotheses `parked` with an explicit revival condition (what new
      data/test would let you resume discriminating between them)

## Notes

_Non-diagnostic evidence collected along the way, kept for audit trail only._
