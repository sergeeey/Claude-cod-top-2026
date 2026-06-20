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

## Counterfactual Frame
_"In what possible world is H true, and how close is that world to ours?"_
_Write BEFORE seeing data. Reveals hidden assumptions and flags cross-domain import opportunities._

| Question | Answer |
|---|---|
| What must change for H to be true? (laws / assumptions / conditions) | |
| How many independent changes required? | |
| Known system where these conditions already hold? | |

**Verdict:** `within-framework` / `requires-new-physics` / `formulation-error`

> **Rule:** ≥ 3 independent changes required → downgrade branch confidence before entering Red Team.
> **Cross-domain trigger:** if a known system exists → check for isomorphic solution before building from scratch.

---

## Falsifiable Claim
_One sentence. Must be checkable with a specific command or observation._

**Claim:**

**Check (command or observation):**

---

## HD-MAVP Decomposition
_Decompose the claim into atoms before testing. Prevents "locally valid, globally broken"._

### Assumptions
_What must be true for the claim to hold? For each assumption: name it, classify type and role.
Complete list prevents "assumption laundering" — retrofitting after null result._

_Types: structural / empirical / mathematical / operational / economic / tooling / context / measurement / behavioral / safety / causal_
_Roles: core (cannot change without abandoning the claim) / protective_belt (can be modified) / peripheral (optional) / hidden (implicit, often missed)_
_Status: alive / weak\_alive / parked / killed / hard\_killed / unknown_
_`hard_killed`: direct contradiction, theorem, or verified null result — cannot be revived without theorem-level input._
_`killed`: current formulation falsified — may create new formulation branch (one assumption at a time)._
_`parked`: not usable as evidence; revisit only when Revival Condition is satisfied._
_`weak_alive`: weaker non-circular formulation + Revival Condition + cheapest differentiating test + AOG passed._
_`alive`: independent mechanism + test / evidence program defined._
_`unknown`: insufficient data._

| # | Assumption | Type | Role | Evidence | Status |
|---|---|---|---|---|---|
| A1 | | | core / belt / peripheral / hidden | | alive / weak_alive / parked / killed / hard_killed / unknown |
| A2 | | | core / belt / peripheral / hidden | | alive / weak_alive / parked / killed / hard_killed / unknown |
| A3 | | | core / belt / peripheral / hidden | | alive / weak_alive / parked / killed / hard_killed / unknown |

_Hard rule: Minimal Relaxation — when this claim fails, change ONE assumption at a time per retry._
_Status rule: status change requires evidence link. `hard_killed` requires theorem-level proof, direct contradiction, or verified null result. `killed` requires at least one falsifying test or direct inconsistency. `parked` requires Rescue Review confirmation. No status change without evidence (`null_results/<id>.md` or test path)._

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
