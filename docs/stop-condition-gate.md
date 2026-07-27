# Stop-Condition Gate

> An evolutionary loop without a stop criterion is not a search — it is a drift.

## The problem this solves

Stage 4 (Variant Tournament) can iterate indefinitely: generate variants, score
them, generate more. Without a pre-declared stop condition, three failure modes
appear:

1. **Premature stop** — two rounds produced no winner, so the run is abandoned.
   The stop was driven by exhaustion, not by evidence.
2. **Infinite drift** — the loop keeps running because "maybe the next variant
   will be better", never committing to a verdict. Goodhart in time: optimizing
   the feeling of progress, not the intent.
3. **Retroactive stop** — the run is stopped when a "good enough" result appears,
   making the stop condition a function of the result rather than the intent. This
   is post-hoc rationalization.

The Stop-Condition Gate is **component 4b** of the Oracle-Aware Core — a sub-gate
that runs *inside* the Variant Tournament at the transition point from "still
searching" to "ready to judge".

```
Stage 4 — Variant Tournament
  4a. Generate diverse field (docs/variant-tournament.md)
  4b. Stop-Condition Gate  <-- THIS DOCUMENT
  4c. Score survivors, select finalist
```

## Pre-declaring stop conditions (before the first round)

Stop conditions are declared in `templates/intent_card.yaml` and committed before
any variant is generated. Declaring them after seeing partial results makes them
suspect (the same Anti-Overfitting Gate that applies to falsification conditions
applies here).

**Fill at least one condition from each of the two required categories:**

### Category A — Progress conditions (stop when good enough)

| Condition | Passes when |
|---|---|
| **MCID met** | Finalist score improves baseline by ≥ MCID from `intent_card.yaml` |
| **Oracle ceiling** | Best variant is within one MCID of the oracle's maximum possible score |
| **Stable leader** | Top variant has held for ≥ K consecutive rounds with no competitor within one MCID |

### Category B — Budget conditions (stop regardless of progress)

| Condition | Triggers when |
|---|---|
| **Round cap** | Number of completed tournament rounds ≥ N (declare N before starting) |
| **Time cap** | Wall-clock elapsed ≥ T (declare T before starting) |
| **Variant cap** | Total variants generated ≥ V (forces field diversity discipline) |

**At least one Category B condition is mandatory.** A run with only Category A
conditions can loop forever if MCID is never met. The Category B cap is the hard
outer bound.

## Verdict at the gate

Evaluate all declared stop conditions after each round:

| Verdict | Meaning | Next action |
|---|---|---|
| **CONTINUE** | No stop condition fired | Generate next round of variants |
| **STOP-PROGRESS** | Category A condition fired | Advance finalist to Stage 5 (Red-Team) |
| **STOP-BUDGET** | Category B condition fired, Category A not met | Advance best-so-far as finalist, inherit `[WEAK]` marker on any claim |
| **STOP-ORACLE** | Negative control started passing (oracle break) | Halt tournament, return to Stage 2 (Oracle Adequacy), fix oracle |
| **STOP-EMPTY** | No survivors in latest round | Reject all variants, route to Null Result Ledger (Stage 7) |

A `STOP-BUDGET` finalist is promoted with `[WEAK]` unless the Evidence Gate
(Stage 6) later upgrades it with additional real-data confirmation.

## Hard rules

1. **Pre-commit stop conditions before generating any variant.** Post-hoc
   stop conditions are rationalization.
2. **Always declare at least one Category B (budget) condition.** No open-ended
   loops.
3. **STOP-ORACLE takes priority over all other conditions.** If the negative
   control passes, the tournament result is invalid regardless of scores.
4. **Do not extend budget mid-run to chase a better result.** Extending the cap
   because the current leader "is close" is motivated reasoning. If you must
   extend, record it explicitly in `templates/stop_gate_report.yaml` with the
   reason.

## Interaction with MCID

The MCID (minimum clinically important difference, from `templates/intent_card.yaml`)
has two roles in the stop gate:

- **Progress stop:** finalist score improvement ≥ MCID → STOP-PROGRESS
- **Noise floor:** improvement < MCID → do not report as a win even if
  the finalist has the highest score. A winner that beats the baseline by
  less than MCID is a statistical tie, not a result.

If no variant has beaten the baseline by MCID after the budget is exhausted →
the run result is STOP-BUDGET with no qualified winner. This is a valid outcome
(a null result), not a failure. Route to the Null Result Ledger with Kill Analysis.

## Anti-patterns

| Anti-pattern | What it corrupts |
|---|---|
| **Stopping when "satisfied"** | Stop condition = the feeling of having a winner, not a pre-declared criterion |
| **Extending budget post-hoc** | Turns a budget cap into a "budget minimum", eliminating the outer bound |
| **Ignoring MCID for the stop** | Reports a winner that is noise (below practical threshold) |
| **No Category B condition** | Allows infinite drift when Category A is never met |
| **Running extra rounds after STOP-PROGRESS** | Confirms the result is driven by continued search, not by the stop criterion |

## Artifact

Fill `templates/stop_gate_report.yaml` when any stop condition fires.

---

**Status:** ACTIVE — component 4b of the Oracle-Aware Evolutionary Mode.
**Command:** `/evolve-solution` evaluates this gate at the end of each tournament round.
**Depends on:** `templates/intent_card.yaml` (MCID, success_metric), `docs/variant-tournament.md` (round structure).
**Produces:** `templates/stop_gate_report.yaml` (one per run).
