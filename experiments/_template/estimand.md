# estimand.md — [EXPERIMENT-ID]
# Required for: FL Full-Ladder + question_type = causal
# Protocol: rules/estimand-ops.md

## L1 Attributes

**Population:** [who/what, with explicit inclusion/exclusion criteria]

**Intervention:** [what exactly — version, config, parameters]

**Comparator:** [vs. what — baseline, alternative, no-treatment]

**Endpoint:** [measured variable, operationalized, with units]

**Summary measure:** [prefer absolute: risk difference, rate difference, difference in means]

**MCID:** [minimum practically important difference — below this = do not act]

---

## Intercurrent Events (ICE)

_Post-baseline events that change endpoint meaning or measurability. ICE is NOT missing data._

| Event | Strategy | Rationale |
|-------|----------|-----------|
| [event name] | treatment-policy / hypothetical / composite / while-active / principal-stratum | [why this strategy] |

---

## Natural Language Statement
_Write BEFORE collecting results._

> "We estimate [summary measure] of [endpoint] for [population], comparing [intervention] vs [comparator], handling [ICE] via [strategy]."

---

## Causal Layer (complete only if question_type = causal)

### DAG
_Attach dag.md or describe the causal graph here._

```
[Variable A] --> [Variable B] --> [Outcome]
                     ^
              [Confounder C]
```

### Identifiability Checks

| Assumption | Status | Evidence / Notes |
|-----------|--------|-----------------|
| Consistency: Y = Y^a when A=a | unchecked / satisfied / violated | |
| Positivity: P(A=a given L) > 0 for all a, L in support | unchecked / satisfied / violated | |
| Exchangeability: Y^a independent of A given L | unchecked / satisfied / violated | |
| SUTVA: no interference between units, no hidden treatment versions | unchecked / satisfied / violated | |

> Hard stop: if ANY assumption is violated and cannot be recovered by design or conditioning,
> the causal estimand is NOT identifiable. Downgrade to descriptive or redesign.

### Identification Strategy
[ ] Randomization  
[ ] Instrumental variable (IV)  
[ ] Regression discontinuity (RD)  
[ ] Difference-in-differences (DiD)  
[ ] G-formula  
[ ] TMLE  
[ ] Other: ___

### Unmeasured Confounders
_List known threats. Plan E-value or negative control sensitivity._

- Confounder 1: [name] — mitigation: [strategy / none]
- Confounder 2: [name] — mitigation: [strategy / none]

---

## What This Result Does NOT Mean
_Write at least 3 explicit non-interpretations BEFORE collecting results._

1. Does NOT prove generalization to [untested population].
2. Does NOT establish causality [if question type is descriptive or predictive].
3. Does NOT apply when [boundary condition].

---

## Sensitivity Analyses
_Minimum 2 for Full-Ladder. Minimum 1 for Standard-Ladder._

1. [Alternative ICE strategy — e.g. hypothetical instead of treatment-policy]
2. [Alternative estimator — e.g. doubly-robust backup]
