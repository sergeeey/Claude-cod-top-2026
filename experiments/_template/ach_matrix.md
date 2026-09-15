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

## Optional: Expected Information Gain
_Use only when ≥2 rows above are tied at `Diagnostic: yes` and the choice between
them actually matters — a cheap test that discriminates is not automatically as
good as an expensive test that discriminates; C/I/N/A cannot tell you which one
of two "yes" rows is worth running first. Skip this section if the qualitative
column already gives an unambiguous next test — computing EIG when it wouldn't
change the decision is Structure-Bias theater, not rigor._

_Pearl-registered 2026-09-14 (`~/.claude/rules/pearl_registry/INDEX.md`) as
`pending [SPECULATIVE]`, with an explicit instruction not to add this to the
live template until a real tied-diagnostic case occurs. **This section is here
anyway, on an explicit user decision to implement now rather than wait** — that
override is recorded in the pearl entry itself (see its `status` field), not
inherited silently from this file alone. The promotion trigger the pearl entry
names (≥3 real cases where this section's number changed which test ran first)
has NOT been reached; using this section does not mean that bar was cleared._

_This is plain Bayesian experimental design (Lindley 1956) — mutual information
between a test's outcome and the hypothesis — not Free Energy Principle. Do not
call it that in this file or anywhere it gets cited; FEP's own critiques
(tautology/falsifiability, description≠mechanism, analogy inflation) apply to
the parts of that theory this project has no use for. Only the one formula below
is being borrowed._

```
EIG(t) = Σ_i Σ_o P(H_i) · P(o|H_i) · log2( P(o|H_i) / P(o) ),   P(o) = Σ_i P(H_i)·P(o|H_i)
```

Compute with your real numbers:

```bash
python scripts/eig_calculator.py --priors '{"H1":0.5,"H2":0.5}' \
    --likelihoods '{"H1":{"pos":0.9,"neg":0.1},"H2":{"pos":0.1,"neg":0.9}}'
```

(`tests/test_eig_calculator.py` reproduces both worked examples below to 5
decimal places via an INDEPENDENT derivation route, not the same formula
re-checked against itself, plus the prior-entropy upper-bound edge case.)
Fill one row per tied test:

| Test | P(H1) prior | P(o\|H1) | P(o\|H2) | EIG (bits) | Note |
|---|---|---|---|---|---|
| | | | | | real estimate / `UNAVAILABLE` |

**Do not use a default C/I/N/A→probability lookup table here** (e.g. "C≈0.85,
I≈0.15") — checked directly: for the one case this section exists for (two rows
both `Diagnostic: yes`), ANY fixed C/I/N/A→number mapping produces the IDENTICAL
EIG for both rows, because both rows have the identical C/I pattern under that
mapping. A default that cannot discriminate two tied rows fails at the one job
this section has. If you don't have a real, case-specific `P(o|H)` for each row,
that row genuinely has `UNAVAILABLE` EIG — go back to the C/I/N/A column, don't
manufacture a number that looks precise and isn't.

**Worked example, not this experiment's data — shows why "both score yes" is not
"both are equal":**

| Test | P(pos\|H1) | P(pos\|H2) | EIG (bits) |
|---|---|---|---|
| A (strong) | 0.9 | 0.1 | 0.531 |
| B (weak) | 0.6 | 0.4 | 0.029 |

Both are `Diagnostic: yes` under the Matrix above (H1 and H2 disagree in
direction on both). EIG shows Test A is ~18× more informative — the qualitative
column alone cannot make that call.

**Hard gating rule — read before filling `P(o|H)` with a number:**

```
Can P(o|H) be justified — independently estimated, or empirically measured
(e.g. a real historical rate from a prior run of this exact test)?
        │
    ┌───┴───┐
   YES      NO
    │        │
 compute   write UNAVAILABLE, use the plain
  EIG      C/I/N/A Matrix column above instead
```

`UNAVAILABLE ≠ 0`. "Cannot compute information gain" is not evidence the test
is uninformative — it means the qualitative column is what you have, and that
is a normal, complete outcome for this section, not a failure to fill it in.
An LLM inventing "H1 predicts this with probability 0.73" to make the formula
computable is precision theater with a logarithm in it — exactly what
`skeptic-triggers.md` already exists to catch, and exactly why there is no
default lookup table here for you to reach for instead.

---

## Optional: Weighted Reranking
_Use only if you need to re-prioritize surviving hypotheses under different
criteria weights WITHOUT rerunning any test — e.g. "if we cared more about cost
than certainty, which hypothesis wins?" Skip this section if C/I/N/A is enough._

_Source: ARCHCODE (Han et al. 2024) — post-hoc reweighting of already-collected
evidence, no regeneration needed. Score each hypothesis 0–5 per criterion (not
per evidence row — this is a separate, coarser view for weighting trade-offs)._

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
- [ ] Exactly 1 hypothesis survives → promote to claim.md as the working hypothesis
- [ ] 0 hypotheses survive → all REJECT; run Kill Analysis in decision.md for each
- [ ] ≥2 hypotheses survive, no affordable differentiating test remains → mark
      remaining hypotheses `parked` (see falsification-ladder.md § Adaptive
      Iteration — Branch Rule) with an explicit revival condition

## Notes
_Non-diagnostic evidence collected along the way, kept for audit trail only._
