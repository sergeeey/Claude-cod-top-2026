# EstimandOps — Research Integrity Protocol

## Why This Exists

Without explicit estimand specification, experiments suffer from:
- **Estimator-driven estimand**: method chosen before question defined → question retrofitted to method
- **ICE confusion**: post-baseline events handled as missing data (imputed) instead of as substantive events (ICE strategy)
- **Type confusion**: descriptive result interpreted as causal claim → months of wasted follow-up
- **Validation theater**: synthetic data validates claim about real world → `[VERIFIED-SYNTHETIC]` fraud

EstimandOps adds the **design-time layer** our stack was missing: what exactly are we measuring, for whom, under what assumptions, and what would the result mean (and NOT mean)?

**Stack position:**
```
EstimandOps (estimand-ops.md)   ← this file: "WHAT to measure, for whom, why"
     ↓
Falsification Ladder (FL)        ← "does the claim hold?"
     ↓
Evidence Policy (integrity.md)   ← "are the claims properly marked?"
     ↓
Hooks / CI / Tests               ← "does the code work?"
```

---

## Mandatory Gate: L0 Question Classification

**Before ANY experiment, analysis, or claim — classify the question:**

| Type | Question form | What is estimated | Key constraint |
|---|---|---|---|
| **Descriptive** | "What is X in population P?" | Summary of what exists | No causal interpretation |
| **Predictive** | "What will X be for new case?" | Conditional expectation | No causal interpretation |
| **Causal** | "What would change if we did A?" | Counterfactual contrast | Requires causal assumptions |

**Hard rules:**
- Descriptive result → NEVER interpret as causal
- Predictive model → NEVER use for "effect of intervention" without causal re-framing
- Causal claim → ALWAYS requires explicit DAG + identifiability check
- Unsure between descriptive and causal → default to descriptive, document reasoning

---

## Estimand Attributes (Fill All, In Order)

1. **Population** — who/what, with explicit inclusion/exclusion criteria
2. **Intervention** — what exactly (version, config, parameters)
3. **Comparator** — vs. what (baseline, alternative, no-treatment)
4. **Endpoint** — measured variable, operationalized, with units
5. **Summary Measure** — population-level statistic (prefer absolute: risk difference, rate difference)
6. **MCID** — minimum practically important difference (below this = don't act)

**Intercurrent Events (ICE):** post-intervention events changing endpoint meaning/measurability.

ICE ≠ missing data. ICE is a substantive event requiring a *strategy*, not imputation.

| Strategy | When | Meaning |
|---|---|---|
| treatment-policy | pragmatic / real-world effectiveness | ICE is part of treatment effect |
| hypothetical | ideal efficacy / biological effect | Model as if ICE didn't occur |
| composite | ICE = bad outcome | Incorporate ICE into endpoint definition |
| while-active | effect during active period only | Truncate at ICE |
| principal-stratum | effect in ICE-defined subgroup | ⚠️ requires nontestable assumptions |

---

## Causal Layer Requirements (question_type = causal only)

When the question is causal, ALL of the following are required BEFORE building the artifact:

1. **DAG** — directed acyclic graph showing causal structure. Attach as `dag.md` in experiment folder.
2. **Identifiability check** — verify 4 assumptions:
   - Consistency: Y = Y^a when A=a
   - Positivity: P(A=a|L) > 0 for all a and L in support
   - Exchangeability: Y^a ⊥ A | L (no unmeasured confounders)
   - SUTVA: no interference between units, no hidden treatment versions
3. **Identification strategy** — how causality is identified (randomization / IV / RD / DiD / g-formula / TMLE)
4. **Unmeasured confounders** — list known threats; plan E-value or negative control sensitivity

**Hard stop:** if any identifiability assumption is violated and cannot be recovered by design or conditioning → the causal estimand is NOT identifiable from available data. Stop. Downgrade to descriptive or redesign.

---

## Natural Language Statement (Required)

For every estimand, write ONE sentence before collecting results:

> *"We estimate [summary measure] of [endpoint] for [population], comparing [intervention] vs [comparator], handling [ICE] by [strategy]."*

This statement must be written **before** seeing results. If you find yourself writing it after — you are rationalizing.

---

## "What This Result Does NOT Mean" (Required)

Write ≥3 explicit non-interpretations before results are known:

1. Does NOT prove generalization to [untested population]
2. Does NOT establish causality [if question was descriptive/predictive]
3. Does NOT apply when [boundary condition]

---

## Estimand → Estimator Rule

**Estimand is chosen for the RESEARCH QUESTION.**
**Estimator is chosen to MATCH the estimand.**

Never the reverse. If your preferred statistical method doesn't match the estimand — change the method, not the estimand.

Reference: `docs/estimand-to-estimator-map.md` — full table by research type.

**Noncollapsibility warning:** Avoid hazard ratio (HR) and odds ratio (OR) as primary summary measure in heterogeneous populations. Prefer:
- Risk difference (RD) or restricted mean survival time (RMST) for time-to-event
- Risk difference (RD) or risk ratio (RR) for binary endpoints
- Difference in means for continuous

---

## Required Artifacts by Tier

| Ladder Tier | Required Estimand Artifacts |
|---|---|
| Micro | claim.md: L0 checkbox + natural language statement + "what this does NOT mean" |
| Standard | claim.md (full) + experiment.yaml (estimand fields) |
| Full | claim.md + experiment.yaml + **estimand.md** (complete canvas) |
| Full + causal | All above + **dag.md** or DAG description in estimand.md |

---

## Sensitivity Analysis Minimum Requirements

For Standard-Ladder: ≥1 sensitivity check.
For Full-Ladder: ≥2 sensitivity checks.

Priority order:
1. Alternative ICE strategy (most common source of estimand ambiguity)
2. Alternative estimator (doubly robust backup)
3. MNAR sensitivity (if missing data present)
4. Tipping point / E-value (if observational causal)

If Standard-Ladder result shows ≥90% success → stress_tests.md becomes REQUIRED (per skeptic-triggers.md rule 3).

---

## Anti-patterns (EstimandOps violations)

| Violation | Detection | Response |
|---|---|---|
| Estimand defined after data access | Date of estimand.md after data collection | STOP. Pre-register or mark as exploratory only |
| ICE imputed as missing data | "We used LOCF/MI for dropouts" without ICE strategy | Reclassify: is dropout an ICE or pure missing? |
| Causal interpretation of descriptive result | "X is associated with Y → X reduces Y" | Require causal layer or remove causal language |
| Method chosen before estimand | "We'll use logistic regression" before population is defined | Back up: define estimand first, then method |
| One estimand for multiple objectives | Single analysis answering regulatory + clinical + safety | Separate estimands per objective |
| Principal stratum without sensitivity | SACE without monotonicity check | Add ≥2 sensitivity analyses for untestable assumptions |
| Pooling noncollapsible measures | Meta-analysis on OR/HR across heterogeneous studies | Convert to RD or use estimand harmonization protocol |

---

## Integration with Existing Rules

| Rule | EstimandOps relationship |
|---|---|
| `integrity.md` — [VERIFIED-REAL/SYNTHETIC/INLINE] | Estimand validation claims MUST be [VERIFIED-REAL]. [VERIFIED-SYNTHETIC] = internal unit test only, NOT estimand confirmation. |
| `falsification-ladder.md` — Full-Ladder | EstimandOps is a pre-step (Step -1) before FL Step 0. estimand.md precedes claim.md. |
| `skeptic-triggers.md` — Trigger 5 | Synthetic validation of causal estimand fires Trigger 5 automatically |
| `doubt-driven-development.md` — DDD | DDD skeptic reviews DESIGN (pre-build). EstimandOps reviews ESTIMAND (pre-design). Together: question → design → artifact → validation. |
| `audit-verification-gate.md` | After agent produces estimand, verify identifiability check independently before accepting [VERIFIED] |

---

## Quick Reference

```
New experiment or analysis?
├── Step 0: Classify question type (descriptive / predictive / causal)
├── Step 1: Fill L1 estimand attributes (population / intervention / comparator / endpoint / summary measure / MCID)
├── Step 2: Identify all ICEs + assign strategy
├── Step 3: Write natural language statement
├── Step 4: Write "what this does NOT mean"
├── [If causal] Step 5: Draw DAG + check 4 identifiability assumptions
├── [If causal] Step 6: Name identification strategy
├── Step 7: Choose estimator from docs/estimand-to-estimator-map.md
├── Step 8: Plan ≥2 sensitivity checks
└── Step 9: Write all above into estimand.md → then proceed to claim.md → then build
```

**Last updated:** 2026-05-16  
**Status:** ACTIVE — enforced in FL Full-Ladder for research/causal experiments  
**Source:** EstimandOps 2.0 (2026-05-16), ICH E9(R1), Binette & Reiter (2024)
