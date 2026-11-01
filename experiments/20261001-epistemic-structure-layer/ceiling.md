# ceiling.md — 20261001-epistemic-structure-layer

_FL Step 4a. Resolved BEFORE any real-data run. Machine-readable heading format kept verbatim._

## Floor-Ceiling Interval

### Population
- Population the ends are computed for: independent real artifacts that are actually filled in — hypothesis
  tables (this repo's `tournament.md`, arbiter-pilot tables; Y-17 sets, read-only), `claim-decomposer` outputs,
  the two 2026-08-24 skeptic-pilot inputs, tracked checkpoints.
- Identical to the estimand population? [x] YES  [ ] NO

### Floor
_The same pipeline with the tested MECHANISM REMOVED: "how much structure does chance alone produce?"_

- Construction (P1): `ach_quotient.py floor` — row-wise shuffle of each test's cells across hypotheses
  (preserves every test's symbol distribution, destroys hypothesis identity), seeded Monte Carlo, same
  `|H| × |tests|` shape as the real set. Few-row matrices merge columns by construction; this is the number the
  real set must beat.
- Construction (P4): repeats of the **identical** blind-agent prompt with no variation (run-to-run noise).
- Construction (P5): 3 repeats of the "no history" framing (run-to-run noise).
- Construction (P3): an AND-only structure over the same atoms (every node a singleton cut) — shows what
  "no redundancy declared" looks like.
- Value (P1, measured 2026-10-01, `metrics/eqr_run.json`, seed 7, 10000 trials): S1 lakes: floor mean 2.0
  non-singleton classes, observed 2 (p_ge 1.0). The floor equals the observation for ANY data of this shape:
  4 of 5 probe rows are constant, so every permutation gives exactly 2 classes of 3. S2 install: floor mean
  0.106, observed 0, so p_ge is 1.0 by construction (observed = 0 cannot exceed any floor).
  P3/P4/P5 floors: AND-only structure computed (kappa 1); P4 noise = base vs base#2; P5 noise = 3 repeats (all
  FALSIFIED, zero variance).
- Result: [x] MEASURED  [ ] NOT MEASURED

### Ceiling
_A performer with PRIVILEGED ACCESS to the answer, for the population above._

- Construction (P1/P3): synthetic matrices / logic structures with a **known injected** number of duplicates /
  known minimal cuts; the tool must recover exactly the injected structure (100% recovery is the ceiling).
  This is `[VERIFIED-SYNTHETIC]` and says nothing about usefulness — it only shows the instrument can reach
  the ceiling at all.
- Construction (P4): the **full-history** variant answers questions about the checkpoint against a git oracle.
- Value: synthetic recovery (`tests/test_ach_quotient.py`, `tests/test_claim_cutsets.py`) reaches 100% on
  injected structure, `[VERIFIED-SYNTHETIC]`; P4 full-history variant = `base`, scored against a git/literal
  oracle (answers all correct).
- Result: [x] MEASURED  [ ] NOT MEASURED

### Efficiency
- Value: not defined: floor and observation coincide on every subject (S1) or observation is 0 (S2); P4/P5
  are at ceiling for the base variant, so there is no interval to take a ratio over.
- Result: [ ] REPORTED  [ ] NOT REPORTED  [x] DEGENERATE
- Out-of-range rule: efficiency > 1 → `CEILING_MISSPECIFIED`; < 0 → `FLOOR_MISSPECIFIED`.

## Decision (resolved BEFORE the run)

| condition | verdict | meaning |
|---|---|---|
| SUCCESS threshold ≤ floor | `CRITERION_INVALID` | passed by a construction with no mechanism |
| ceiling < SUCCESS threshold | `TASK_INFEASIBLE` | not even privileged access reaches the bar |
| ceiling ≈ floor | `NO_HEADROOM` | the metric cannot separate anything |
| otherwise | `PROCEED` | interval healthy |

- P1 (EQR, both subjects): [x] `NO_HEADROOM` — the floor equals the observation (S1) or the observation is 0 (S2);
  no outcome on these data could have exceeded the floor.
- P3 (ECSA): [x] `NO_HEADROOM` — neither claim has OR structure, so computed singleton cuts equal the AND-only floor.
- P4 (Checkpoint Fidelity): [x] `NO_HEADROOM` for the base variant (all answers correct); the control is the
  only variant that moved.
- P5 (Narrative Poison): [x] `NO_HEADROOM` — 5/5 FALSIFIED.
- These are stop-verdicts: they say the measurements could not have been informative, not that the tools failed.

_Hard rule: the three stop-verdicts are NOT evidence against the claim ("could not have been informative" ≠ "failed")._
