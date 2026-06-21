# Estimand-to-Estimator Map

> **Purpose:** Given your research context, pick the right estimand and estimator.
> Derived from EstimandOps 2.0 Section 6 — adapted for our project types.
> **Rule:** Choose estimand FIRST. Then pick estimator that matches. Never the reverse.

---

## Quick Decision Tree

```
What type of question?
│
├── Descriptive ("what is?")
│   → Summary statistics, prevalence, distribution
│   → No causal assumptions needed
│   → Estimator: mean/proportion + bootstrap CI
│
├── Predictive ("what will be?")
│   → Conditional E[Y|X] — probabilities, predictions
│   → No causal assumptions — but DO NOT interpret as causal
│   → Estimator: regression, ML model + calibration
│
└── Causal ("what would change if?")
    │
    ├── Randomized / A-B test
    │   → ATE, treatment-policy estimand
    │   → Estimator: ANCOVA / t-test / regression adjustment
    │
    ├── Observational with measured confounders
    │   → ATE or ATT with exchangeability assumption
    │   → Estimator: IPW / g-formula / TMLE (doubly robust)
    │
    ├── Natural experiment (IV, RD, DiD)
    │   → LATE (IV) / local ATE (RD) / ATT (DiD)
    │   → Estimator: 2SLS / local linear / two-way FE
    │
    └── Survival / time-to-event
        → Cause-specific hazard OR RMST difference (not HR if heterogeneous)
        → Estimator: KM + log-rank / RMST / Fine-Gray for competing risks
```

---

## Full Reference Table

| Research Type | Typical Estimand | ICE Strategy | Estimators (ranked) | Required Assumptions | Key Diagnostics | Min Sensitivity Checks |
|---|---|---|---|---|---|---|
| **A/B test (hooks, features)** | ATE on metric | treatment-policy for failures; composite for crashes | t-test + regression adjustment (CUPED) | SUTVA, randomization, no SRM | SRM check, pre-test A/A, variance analysis | Long-run holdout; alternative metric |
| **Before-after comparison** | ATT (change in treated) | treatment-policy | Paired t-test, DiD if control available | Parallel trends (if DiD), no contemporaneous confounders | Pre-period trend plot | Placebo test on pre-period |
| **Hook false-positive audit** | Expected FP rate in production | treatment-policy (include all tool calls) | Bootstrap proportion CI | IID samples, no selection | FP rate by tool type, time trend | Alternative population (different tool types) |
| **Model performance eval (dev)** | Expected calibration error + AUC in target population | composite for refusals/failures | Calibration plot + Brier score + AUC with bootstrap CI | IID test set, correct target population, no data leakage | Temporal validation, stratification by difficulty | External validation set; recalibration |
| **LLM eval (prompt A/B)** | ATE on task success rate | composite for context overflow; treatment-policy for tool failure | Bootstrap CI on risk difference | SUTVA (prompt independence), no judge bias | Task-type stratification; judge calibration | Human-expert validation sample vs LLM judge |
| **Causal inference (RCT/experiment)** | ATE — treatment-policy or hypothetical | Choose per research question | MMRM (longitudinal) / ANCOVA (single endpoint) + MI for MAR | SUTVA, randomization, MAR for main analysis | Randomization check, dropout pattern, baseline balance | Hypothetical ↔ treatment-policy; MNAR sensitivity |
| **Observational causal (EHR/logs)** | ATE or ATT with measured confounders | treatment-policy (main); hypothetical (sensitivity) | TMLE (doubly robust, preferred) → IPW → g-formula → PSM | Exchangeability, positivity, consistency, SUTVA | PS overlap, covariate balance (SMD), E-value | Negative control outcome; Rosenbaum bounds |
| **Target trial emulation** | ATE — treatment-policy | treatment-policy (aligned with trial protocol) | Cloning-censoring-weighting → g-computation | No immortal time bias, sequential exchangeability, positivity | Time-zero alignment check, person-time plot | Per-protocol population restriction |
| **DiD (interrupted time series)** | ATT (pre-post, treated vs control) | treatment-policy | Two-way FE / segmented regression | Parallel trends, no anticipation, no contamination | Pre-period trend test (Granger-style), residuals | Placebo intervention at different time; alternative control |
| **Scientific hypothesis (ARCHCODE/APE)** | ATE or CATE on biological/computational outcome | research-question specific | TMLE or g-formula for observational; ANCOVA for RCT; causal forest for CATE | Exchangeability + positivity + consistency (observational) | PS overlap, DAG review, identifiability check | Negative control; E-value; alternative confounders set |
| **Prediction model for decision support** | Interventional probability E[Y\|do(A), X] NOT observational E[Y\|A,X] | treatment-policy | g-computation / sequential prediction estimand | No unmeasured time-varying confounders, correct model | Calibration in deployment population | Comparison vs observational probability model |
| **Subgroup / CATE analysis** | CATE: E[Y(1)-Y(0)\|X=x] | same as primary | Causal forest / X-learner / T-learner | Same as primary + overlap per subgroup | Qini / uplift curve; CATE calibration | Cross-validation stability; alternative learners |
| **Survival (competing risks)** | Cause-specific hazard OR subdistribution hazard | composite for competing event | Cause-specific Cox (preferred) → Fine-Gray | Non-informative censoring, correct model | CIF plot, Schoenfeld residuals | Both cause-specific and subdistribution compared |
| **Meta-analysis / evidence synthesis** | Pooled estimand (requires harmonized primary estimands) | must match across studies | Fixed/random effects on harmonized measure | Estimand compatibility across studies | Heterogeneity (I²), funnel plot | Subgroup by estimand type; sensitivity to ICE strategy harmonization |

---

## Why Not Just Use Hazard Ratio?

Hazard ratio (HR) and odds ratio (OR) are **noncollapsible** — their value changes when you adjust for covariates, even with no confounding. In heterogeneous populations this creates temporal drift and pooling artifacts.

**Preferred alternatives:**

| Instead of | Use |
|---|---|
| HR (time-to-event) | RMST difference (restricted mean survival time) or risk difference at fixed time |
| OR (binary) | Risk difference (RD) or risk ratio (RR) with explicit population |
| Relative risk | Absolute risk difference (ARD) — decision makers need absolute numbers |

> Exception: HR/OR acceptable when the target population is genuinely homogeneous and noncollapsibility is not a concern. Document this choice in `estimand.md`.

---

## TMLE vs IPW vs G-formula: When to Use What

| Method | When | Key Advantage | Key Limitation |
|---|---|---|---|
| **TMLE** (doubly robust) | Default for observational causal | Doubly robust: correct if either propensity or outcome model is correct | Requires SuperLearner or careful nuisance model selection |
| **IPW** (inverse probability weighting) | Simple, when PS model is reliable | Intuitive, easy to implement | Not doubly robust; sensitive to positivity violations |
| **G-formula** (standardization) | When outcome model is reliable | Direct standardization, handles time-varying confounders | Requires correct outcome model; computationally intensive |
| **ANCOVA / regression** | Randomized experiments | Simple, efficient, handles covariate adjustment | Requires correct regression specification; not doubly robust |
| **Causal forest** | CATE estimation | Nonparametric, automatic tuning | Black box; requires large N for reliable CATE |

---

## Sensitivity Analysis Minimum Requirements

For **Standard-Ladder** experiments: ≥1 sensitivity check.
For **Full-Ladder** experiments: ≥2 sensitivity checks from the menu below.

| Check | What it tests | How to do it |
|---|---|---|
| Alternative ICE strategy | Robustness to intercurrent event handling | Re-run with different ICE strategy (e.g., hypothetical vs treatment-policy) |
| Alternative estimator | Robustness to statistical method | Apply 2nd estimator from table above |
| MNAR sensitivity | Robustness to missing data assumption | δ-adjustment or reference-based imputation (J2R, CR) |
| Tipping point | How much unmeasured confounding overturns result | E-value calculation or Rosenbaum bounds |
| Subgroup stability | Heterogeneity of effect | Primary estimand by 2-3 key subgroups |
| Temporal validation | Temporal drift | Re-run on later data window |
| Negative control | Unmeasured confounding detection | Run analysis on outcome where true effect = 0 |

---

## Anti-patterns

| Anti-pattern | Detection | Fix |
|---|---|---|
| Estimator chosen before estimand | Method named in proposal before population/endpoint | Back up: define estimand first |
| HR/OR as sole summary measure | Only relative measure reported | Add risk difference |
| Missing ICE strategy | "We excluded dropouts" or "we imputed" without estimand | Define ICE strategy in estimand.md |
| Descriptive interpreted as causal | "X is associated with Y → X causes Y" | Re-classify question type or add causal layer |
| Synthetic validation as causal confirmation | F1=1.0 on hand-crafted examples | [VERIFIED-SYNTHETIC] only; rerun on real data |
| Subgroup as primary | Subgroup selected post-hoc from many tested | Pre-specify subgroups in estimand.md |

---

*Derived from: EstimandOps 2.0 (2026-05-16), ICH E9(R1), Binette & Reiter (2024),
Hernán & Robins TTE framework, TMLE guidelines 2025, Kahan et al. BMJ primer 2024.*
