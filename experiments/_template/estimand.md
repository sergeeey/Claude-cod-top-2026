# Estimand Document (EstimandOps 2.0)

> **Required for:** Full-Ladder experiments AND any causal question type.
> **Fill before:** building artifact, choosing estimator, running analysis.
> **EstimandOps principle:** Estimand precedes estimator. Always.

**Experiment ID:** `<YYYYMMDD-short-slug>`
**Version:** 1.0.0
**Date:** YYYY-MM-DD
**Author:**
**Pre-registered:** [ ] Yes — link: ___  [ ] No — internal only

---

## L0: Question Type (check one)

- [ ] **Descriptive** — observes what IS (no intervention hypothetical)
- [ ] **Predictive** — forecasts what WILL BE for new inputs (no causal claim)
- [ ] **Causal** — estimates what WOULD CHANGE under intervention

> If you checked **Descriptive** or **Predictive** — Sections L3 (Causal Layer) are N/A.
> If you checked **Causal** — L3 is mandatory. You MUST attach a DAG.

---

## L1: Core Attributes (ICH E9(R1) Five Attributes)

### Population

> Who or what are we studying? Explicit inclusion/exclusion.

```
Population: [Description]
Inclusion:  [criteria]
Exclusion:  [criteria]
N (expected): [sample size or "n/a — observational"]
```

### Intervention

> What exactly is the intervention/treatment/version being tested?

```
Intervention: [exact description with version/config/parameters]
```

### Comparator

> What is compared against?

```
Comparator: [baseline / control / alternative version / "no intervention"]
```

### Endpoint

> What is measured for each unit? Operationalized with units and measurement process.

```
Endpoint: [variable name]
Operationalization: [how exactly it's measured — formula, tool, rater]
Units: [%, count, ms, F1, etc.]
Measurement timing: [when / over what window]
Who measures: [automated test / human rater / LLM judge / monitoring system]
```

### Summary Measure

> Population-level statistic that summarizes the effect.

```
Summary measure: [difference_in_means | risk_difference | rate_change | AUC_delta | F1_delta | success_rate_difference]
Direction: [lower is better | higher is better]
```

### MCID (Minimum Clinically/Practically Important Difference)

> The smallest change in summary measure worth acting on. Below this = ship nothing.

```
MCID: [value with units]
Rationale: [why this threshold matters]
```

---

## L1b: Intercurrent Events (ICE)

> Post-intervention events that change the meaning or measurability of the endpoint.
> ICE ≠ missing data. ICE is a substantive event. Handle via strategy, not imputation.

| ICE | Description | Strategy | Rationale |
|---|---|---|---|
| [ICE 1 name] | [what happens] | treatment-policy / hypothetical / composite / while-active / principal-stratum | [why this strategy fits] |
| [ICE 2 name] | [what happens] | | |

**Chosen strategy definitions:**
- **treatment-policy** — ICE is part of intervention effect; all units included regardless
- **hypothetical** — estimate effect as if ICE had not occurred; requires modeling assumptions
- **composite** — ICE incorporated into endpoint as unfavorable outcome
- **while-active** — analysis restricted to period before ICE occurs
- **principal-stratum** — restrict to subgroup defined by counterfactual ICE behavior ⚠️ nontestable assumptions required

---

## L2: Decision Context

| Attribute | Value |
|---|---|
| **Decision maker** | [who acts on this result] |
| **Decision** | [what binary/graded decision is made] |
| **Action space** | [set of possible actions] |
| **FP cost** | [cost of false positive conclusion] |
| **FN cost** | [cost of false negative conclusion] |
| **Loss function type** | symmetric / asymmetric — if asymmetric, which error is more costly? |
| **Practical threshold** | [value of summary measure above/below which = act] |

---

## L3: Causal Layer *(skip if question_type ≠ causal)*

### Causal Contrast

```
E[Y(intervention)] - E[Y(comparator)]
```
*or specify quantile / conditional / distributional contrast if applicable.*

### Target Trial

> Describe the hypothetical randomized experiment this study emulates.
> Required for observational studies; "n/a — actual RCT/A-B test" for experiments.

```
Target trial: [description or "n/a"]
Randomization unit: [session | user | tool call | request]
Eligibility: [same as Population in L1]
Assignment: [random assignment of intervention vs comparator]
Follow-up: [time window]
Outcome assessment: [same as Endpoint in L1]
Causal contrast: [same as above]
```

### DAG (Directed Acyclic Graph)

> Attach `dag.md` or describe the causal structure.

```
dag_attached: [ ] Yes (file: dag.md)  [ ] No — describe here:

Nodes: [list variables: A (intervention), Y (endpoint), L1..Ln (confounders/mediators)]
Directed edges: [A → Y, L1 → A, L1 → Y, ...]
Backdoor paths: [list open backdoor paths from A to Y]
Identification: [which paths are blocked by conditioning on L1..Ln]
```

### Identifiability Checks

| Assumption | Status | Evidence / Justification |
|---|---|---|
| **Consistency** — Y = Y^a when A=a (no hidden version of treatment) | ✅ / ⚠️ / ❌ | |
| **Positivity** — P(A=a\|L) > 0 for all a and L values in data | ✅ / ⚠️ / ❌ | |
| **Exchangeability** — Y^a ⊥ A \| L (no unmeasured confounders) | ✅ / ⚠️ / ❌ | |
| **SUTVA** — no interference between units, no hidden versions | ✅ / ⚠️ / ❌ | |

> ⚠️ If any assumption is ❌ → estimand is NOT identifiable from available data.
> Stop. Redesign experiment or downgrade claim to descriptive/predictive.

### Identification Strategy

```
Strategy: [randomization | A/B test | before-after | DiD | IV | RD | PSM | g-formula | TMLE | other]
Rationale: [why this strategy achieves identifiability given DAG structure]
```

### Unmeasured Confounders

```
Known unmeasured threats: [list variables not in data that could confound A→Y]
Sensitivity plan: [E-value | negative control | Rosenbaum bounds | "n/a — RCT"]
```

---

## L4: Data Reality

| Attribute | Value |
|---|---|
| **Data source** | [RCT / A/B test / CI logs / EHR / production traffic / synthetic] |
| **Missingness mechanism** | MCAR / MAR / MNAR + justification |
| **Censoring** | informative / non-informative / n/a |
| **Known biases** | [list: selection bias / measurement error / temporal drift / ...] |
| **Measurement error in endpoint** | [yes/no — if yes, describe and plan correction] |
| **Time alignment** | [is time zero correctly defined? no immortal time bias?] |
| **Data-generating process** | [structural constraints affecting identifiability] |

---

## L5: Estimator Mapping

| Field | Value |
|---|---|
| **Primary estimator** | [t-test / ANCOVA / IPW / TMLE / g-formula / bootstrap / regression] |
| **Rationale** | [why this estimator matches the estimand — not just "it's standard"] |
| **Required assumptions** | [estimator-specific beyond L3] |
| **Mandatory diagnostics** | [positivity check / balance table / calibration / residuals] |
| **Sensitivity estimator 1** | [alternative method — same estimand, different assumptions] |
| **Sensitivity estimator 2** | [another alternative] |

---

## L6: Robustness Plan

| Check | Description | When to run |
|---|---|---|
| Sensitivity estimand | Alternative ICE strategy (e.g., hypothetical vs treatment-policy) | After primary analysis |
| Alternative estimator | See L5 sensitivity estimators | After primary analysis |
| Subgroup stability | Primary estimand in key subgroups | After primary analysis |
| Tipping point | How much unmeasured confounding overturns conclusion | After primary analysis |
| Temporal validation | Does result hold on later time window? | Optional — if temporal drift is a concern |

---

## L7: Communication Layer

### Natural Language Statement

> One sentence for any stakeholder:

> *"We estimate [summary measure] of [endpoint] for [population], comparing [intervention] vs [comparator], handling [ICE list] by [strategies]."*

**Draft:**
_______________________________________________________________________________

### Technical Statement

> Formal potential outcomes / causal contrast notation:

```
E[Y(intervention)] - E[Y(comparator)]
= [fill with specific formula for your estimand]
```

### What This Result Does NOT Mean

1. _____
2. _____
3. _____

### Interpretation Boundaries

> Conditions under which interpretation is valid:

- Valid for population: _____
- Valid for time window: _____
- Does NOT apply when: _____

---

## L8: Governance

| Field | Value |
|---|---|
| **Pre-registered** | [ ] Yes — where: ___ [ ] No — internal only |
| **SAP version** | v1.0 |
| **SAP written before data access** | [ ] Yes [ ] No |
| **Approval** | [who signed off on estimand before execution] |
| **Change log** | [any changes to estimand after initial approval — must be documented] |

---

## Estimand Review Checklist

Before proceeding to artifact build (Step 2 of Full-Ladder):

- [ ] Question type classified (L0)
- [ ] All 5 ICH attributes filled (L1)
- [ ] ICE identified and strategy assigned
- [ ] MCID defined
- [ ] Natural language statement written
- [ ] "What this does NOT mean" filled
- [ ] For causal: DAG attached or described
- [ ] For causal: all 4 identifiability assumptions checked
- [ ] For causal: identification strategy named and justified
- [ ] Primary estimator matches estimand
- [ ] ≥2 sensitivity estimators named
- [ ] Mandatory diagnostics listed
- [ ] Governance fields complete
