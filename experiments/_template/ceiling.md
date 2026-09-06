# ceiling.md — [EXPERIMENT-ID]

_FL Step 4a. Resolve BEFORE Step 6 (the run). Machine-readable format — `hooks/ceiling_gate_guard.py`
parses the `## Floor-Ceiling Interval` block below; keep the headings and `Result:` lines verbatim._

## Floor-Ceiling Interval

### Population
_The population BOTH ends are computed for. MUST equal `population` in `experiment.yaml` / `estimand.md`.
WHY (added 2026-09-06, Y-17 pilot `20260906-riemann-rstat-gue`): the ceiling was the N→∞ GUE value while
the measured population was zeros at finite height → efficiency = 1.038 > 1, silently absorbed into PASS.
A ceiling for population A does not transfer to population B — same rule as Gate 1 artifact identity._

- Population the ends are computed for:
- Identical to the estimand population? [ ] YES  [ ] NO → STOP: recompute floor and ceiling for the measured population before running

### Floor
_The same pipeline with the tested MECHANISM REMOVED (null model). "How much does the metric give for free?"_

- Construction:
- Value:
- Result: [ ] MEASURED  [ ] NOT MEASURED

### Ceiling
_A performer with PRIVILEGED ACCESS to the answer, for the population above. "How much is attainable at all?"_

- Construction:
- Value:
- Result: [ ] MEASURED  [ ] NOT MEASURED

### Efficiency
`efficiency = (observed − floor) / (ceiling − floor)` — fill AFTER the run; the decision table below is filled BEFORE.

- Value:
- Result: [ ] REPORTED  [ ] NOT REPORTED  [ ] DEGENERATE (observed below floor, or ceiling ≈ floor — ratio meaningless)
- Out-of-range rule: **efficiency > 1 → `CEILING_MISSPECIFIED`** (ceiling population ≠ measured population, or the
  "privileged" performer was not privileged); **efficiency < 0 → `FLOOR_MISSPECIFIED`**. Neither is evidence for or
  against the claim — it is evidence about this file.

## Decision (resolve BEFORE Step 6)

| condition | verdict | meaning |
|---|---|---|
| SUCCESS threshold ≤ floor | `CRITERION_INVALID` | passed by a construction with no mechanism — cannot be failed; rewrite claim.md |
| ceiling < SUCCESS threshold | `TASK_INFEASIBLE` | not even privileged access reaches the bar |
| ceiling ≈ floor | `NO_HEADROOM` | the metric cannot separate anything |
| otherwise | `PROCEED` | interval healthy |

- [ ] `CRITERION_INVALID`  [ ] `TASK_INFEASIBLE`  [ ] `NO_HEADROOM`  [ ] `PROCEED`

_Hard rule: the three stop-verdicts are NOT evidence against the claim ("could not have been informative" ≠ "failed")._
