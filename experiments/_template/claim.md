# claim.md — [EXPERIMENT-ID]

## Zero-Signal Gate
_Fill all three fields. If ANY is "don't know" or "unclear" — STOP. Do NOT continue this template._
_File a one-line note: `REFUSE([experiment-id]): no falsifiable claim formable — [reason]`_

| Field | Value |
|-------|-------|
| **Entity** — what exactly are we talking about? | |
| **Falsifiable predicate** — what specific property do we claim changes? | |
| **Measurable outcome** — how do we observe PASS vs FAIL? (command, metric, threshold) | |

> **Gate rule:** `(∃ entity) ∧ (∃ falsifiable predicate) ∧ (∃ measurable outcome)` — all three required.
> If the system cannot fill this table from the input alone → the input is white noise or too underspecified.
> **Issuing a REFUSE is a valid and correct output. Structuring noise is not.**

---

## L0: Question Type
_Check exactly one. If unsure, default to Descriptive and document reasoning._

- [ ] Descriptive — "what is X in population P?"
- [ ] Predictive — "what will X be for a new case?"
- [ ] Causal — "what would change if we did A vs B?"

> If Causal: complete `estimand.md` with DAG + 4 identifiability checks before proceeding.

---

## Natural Language Statement
_Write BEFORE collecting any data or running any tests._

> "We estimate [summary measure] of [endpoint] for [population],
> comparing [intervention] vs [comparator],
> handling [ICE] via [strategy]."

---

## Falsifiable Claim
_One sentence. Must be checkable with a specific command or observation._

**Claim:**

**Check (command or observation):**

---

## HD-MAVP Decomposition
_Decompose the claim into atoms before testing. Prevents "locally valid, globally broken"._

### Assumptions
_What must be true for the claim to hold? Explicit, not background._

- [ ] Assumption 1:
- [ ] Assumption 2:

### Constraints
_Where does this claim NOT apply? Scope boundaries._

- Constraint 1:
- Constraint 2:

### Unknowns
_Mark [U] = unknown (no data), [W] = weakly supported (one source)._

- [U] Unknown 1:
- [U] Unknown 2:

### Dependencies
_Prior results or conditions this claim builds on._

- Dependency 1:

---

## Pearl Card
_Turns this claim into a testable, falsifiable registry entry._

**Prediction:** if the claim holds, I expect X to happen in Y scenario.

**Falsification:** this claim is WRONG if [observable condition] is observed.

---

## What This Does NOT Mean
_Write at least 2 explicit non-interpretations BEFORE collecting results._

1. Does NOT prove generalization to [untested population / context].
2. Does NOT establish causality [if question type is descriptive or predictive].
3. Does NOT apply when [boundary condition].

---

## MCID
_Minimum Clinically / Practically Important Difference. Below this threshold = do not act._

MCID = [value + units]
