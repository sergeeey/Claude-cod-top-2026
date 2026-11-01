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

Items 1-4 (Population/Intervention/Comparator/Endpoint) are this project's adaptation of **PICO**,
the standard framework for structuring an answerable clinical/intervention research question
(Cochrane Handbook for Systematic Reviews of Interventions, ch. 3). Not an invention of this
repo — cited so "why these four fields, in this order" has an external, checkable source instead
of resting on this file's own say-so.

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
| Micro | claim.md: L0 checkbox + natural language statement + "what this does NOT mean" (+ the `n, baseline_or_sigma, alpha, power, MDE, MCID` line for a sampling-based comparison; the PR description is fine) |
| Standard | claim.md (full) + experiment.yaml (estimand fields, incl. the MDE keys next to `mcid:` for a sampling-based comparison) |
| Full | claim.md + experiment.yaml + **estimand.md** (complete canvas, incl. the same `n, baseline_or_sigma, alpha, power, MDE, MCID` keys) |
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

## Design Detectability (MDE) — what may a null result claim? (state before seeing results)

Not the "Sensitivity Analyses" above, which vary the *analysis*: this asks what effect the
*design* could detect. Write it down before seeing results, for any comparison that rests on
sampling variability (a contrast between arms, or one arm against a fixed threshold). Benchmark,
seed and split results are NOT exempt: they vary. Exempt only: a deterministic check (same input,
same output) or a lookup of a named source's existence.

One canonical line, the same wherever it lives: `n, baseline_or_sigma, alpha, power, MDE, MCID`

- `n` — independent units per arm (for one arm against a threshold, that arm's n); not repeated
  runs or variants of one subject
- `baseline_or_sigma` — the value used, and where it came from
- `alpha`, `power` — default 0.05 two-sided and 0.8; any other value (including one-sided) needs a
  one-line reason
- `MDE` — the smallest effect the design reliably detects, in absolute units of the endpoint, with
  its direction (increase or decrease from the baseline). If no effect in that direction is
  detectable at your n — the MDE would exceed the available range (the baseline for a decrease,
  1 - baseline for an increase) — write `MDE=undetectable`, never "none" or 0, which read as the
  opposite
- `MCID` — fixed before the data, with its reason (estimand attribute 6); if the summary measure
  is a ratio (RR, HR), convert it to an absolute difference at the baseline first

Where: `claim.md` or the PR description (Micro); `experiment.yaml` next to its existing `mcid:`
key, adding `n`, `baseline_or_sigma`, `alpha`, `power`, `mde` — or `claim.md` if the experiment
has no `experiment.yaml` (Standard); `estimand.md`, adding the same keys (Full).

**Rule:**
1. A null result is always reported with its bound and its design, never as plain "no effect":
   "not detected at MDE=`<value>` (n=`<...>`, baseline=`<...>`, alpha=`<...>` two-sided,
   power=`<...>`, direction=`<...>`)", with the observed estimate and its confidence interval
   beside it. The MDE, n and baseline in that sentence are one consistent set: if the planned MDE
   is kept under rule 4, show the planned n and baseline with it. If `MDE=undetectable`, do not
   write the not-detected sentence; write "uninformative at this n" with the estimate and interval.
2. If `MDE=undetectable`, the design could not detect any effect: there is no null claim at all.
   If `MDE > MCID`, or there is no MCID or no MDE, the design alone does not support a claim about
   effects of the size that matters. If `MDE <= MCID`, effects below the MDE are still not
   excluded (at a given power an effect exactly the MDE is missed in 1 - power of runs).
3. A separately labelled claim "the observed confidence interval excludes effects >= MCID" may be
   added when it holds, using an exact or Wilson interval at 1 - alpha (never a Wald interval near
   rates of 0 or 1: with 0/30 events it is [0, 0] and "excludes" everything). It never replaces the
   MDE statement, which describes the design.
4. After the run, recompute the MDE with the observed baseline or sigma and the analysed n (after
   exclusions). That may only weaken the null claim, never strengthen it: if the recomputed MDE is
   larger, report the larger; if it is smaller than planned, still report the planned one.
5. This fixes what may be *claimed*, not how a result is filed (`falsification-ladder.md` decides
   that, and has no MDE-aware verdict; this section does not add one). Whatever verdict is chosen,
   any sentence in `decision.md` or an INDEX row that states the null carries the bound, and
   "falsified" (likewise "refuted", "ruled out", "no effect") is licensed only when both MDE and
   MCID are stated and `MDE <= MCID`. Known residue, acknowledged rather than hidden: an
   under-powered null can still be filed as `REJECT`, and that file's header and retry block say
   "falsified"; this section does not change that.

**Reference numbers** — n per arm, two independent proportions, two-sided alpha 0.05, power 0.8,
normal approximation, *absolute* rate changes (50% -> 20% is a change of 30 points):

| rate change | n per arm (rounded up) |
|---|---|
| 50% -> 20% | 39 |
| 30% -> 15% | 121 |
| 10% -> 5% | 435 |
| 5% -> 2.5% | 906 |
| 1% -> 0.5% | 4,673 |

The raw values are 38.5, 120.5, 434.4, 905.4, 4672.8; round n UP. Do not interpolate between rows:
they have different baselines.

`n = (z(1-alpha/2) * sqrt(2 * pbar * qbar) + z(power) * sqrt(p1*q1 + p2*q2))^2 / (p1 - p2)^2`,
with `q = 1 - p` and `pbar = (p1 + p2) / 2`. The rule needs MDE *given* n, which is the inverse.
For proportions there is no closed form: move `p2` away from `p1` in the stated direction until
the n above is at most yours. A power calculator does this (for example statsmodels'
`NormalIndPower.solve_power`; it uses an arcsine effect size, so its n differs slightly from this
table: 37.9 against 38.5 for 50% -> 20%). Worked example: n = 30 per arm, baseline 50%, decrease
-> MDE is about 33 points (down to roughly 17%); at n = 100 per arm it is about 19 points. For a
continuous endpoint `MDE = (z(1-alpha/2) + z(power)) * sigma * sqrt(2/n)`.

**Limits, stated rather than hidden:**
- The table and formulas are for two independent arms. One arm against a fixed threshold needs a
  different n (use a power calculator); AUC or F1 comparisons, count data, time-to-event (HR) and
  paired designs, ordinal scores, repeated looks and several endpoints under one alpha are not
  covered by them.
- Repeated runs, variants of one subject, or forks from one checkpoint are clustered: count the
  clusters, not the runs.
- The table is for the uncorrected z-test, so it is a *lower bound* for an exact test (Fisher needs
  more per arm). The continuous formula uses z, not t: below about 30 per arm (a rule of thumb) its
  MDE is optimistically small, so use t or an exact method.
- Near rates of 0 or 1 the normal approximation is rough; use an exact test (3/30 events vs 0/30
  gives an exact two-sided p of about 0.24, where the z-test would say about 0.08).
- None of this says whether the outcome label itself is trustworthy.

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
| Null reported as "no effect" | A sampling-based comparison reported as absence of an effect: no MDE stated, no MCID or an MCID not recorded before the data, `MDE > MCID`, `MDE=undetectable`, or the bound omitted | Report "not detected at MDE=`<value>`" with the design ("uninformative at this n" if `MDE=undetectable`); an MCID set after the data makes the result exploratory (see "Estimand defined after data access") |

**"Estimand defined after data access" is not an invented rule** — it's this project's version of
**preregistration**, the established practice (formalized by the Open Science Framework's
timestamped, immutable, read-only project registrations) of committing to a research question and
analysis plan before results are visible, precisely so the plan cannot be quietly reshaped to fit
what was found. Same failure mode this repo already names elsewhere as "estimator-driven estimand"
and AOG-1 below — OSF is the external, checkable precedent, not a repo-local convention.

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

## Advisory Router (resolve_route.py) — added 2026-09-06

Once a task passes the L0 gate and lands at Standard or Full tier, `scripts/resolve_route.py`
(Claude-cod-top-2026 repo) can suggest a concrete skill sequence instead of picking one from
memory: `python scripts/resolve_route.py "<the task in one line>"` returns a step list (which
skills, in what order, which gates, which verifier) for a single-mechanism vs
multi/competing-hypothesis vs generate-new-hypothesis task — mechanically checked against
`skills/registry.yaml` so the steps' declared inputs/outputs actually chain together, not a
memory-based guess at whether `sci-evidence`, `hypothesis-arbiter`, or `sci-hypothesis` applies.

**This is advisory, not mandatory — treat its output as a default you may override, not a
command.** It is a keyword-based classifier with a known, evolving false-positive/recall-gap
history (an audit on 2026-09-06 found and fixed 3 false positives and 1 false negative in one
sitting; `tests/test_resolve_route.py`'s `TestRealHistoricalPhrases` class documents what it
currently gets right and wrong against real, non-crafted phrasings). If its classification
looks wrong for the specific request in front of you, override it and say why — do not follow
it just because a tool produced it. This deliberately diverges from CLAUDE.md's own L0
auto-trigger keyword list (`hypothesis`, `experiment`, `predict`, `causal`, ...): that list is
intentionally broader, because `experiment`/`predict` alone are fine prompts for "should I even
think about EstimandOps here" but turned out too generic to decide a *specific* workflow on
their own — `resolve_route.py` only treats them as a signal when paired with another one.

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
├── Step 7b: [sampling-based comparisons] State `n, baseline_or_sigma, alpha, power, MDE, MCID` before seeing results
├── Step 8: Plan ≥2 sensitivity checks
└── Step 9: Write all above into estimand.md → then proceed to claim.md → then build
```

**Last updated:** 2026-10-03 (Design Detectability section)  
**Status:** ACTIVE — enforced in FL Full-Ladder for research/causal experiments  
**Source:** EstimandOps 2.0 (2026-05-16), ICH E9(R1), Binette & Reiter (2024)
