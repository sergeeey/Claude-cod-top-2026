# Claim

**Experiment ID:** `<YYYYMMDD-short-slug>`
**Date:** YYYY-MM-DD
**Author:** Claude / human
**Ladder tier:** micro / standard / full

---

## Step 0 (MANDATORY FIRST): Question Type — L0 Gate

> EstimandOps L0: classify BEFORE writing the claim.
> Wrong classification = wrong estimand = wasted experiment.

**[ ] Descriptive** — "What is observed in this system/population right now?"
**[ ] Predictive** — "What will happen for a new input/case?"
**[ ] Causal** — "What would change if we intervened on X?"

⚠️ **Causal** → `estimand.md` REQUIRED (DAG + identifiability + ICE strategy).
⚠️ Unsure descriptive vs causal → default to **descriptive**, document why.
⚠️ Using causal interpretation for descriptive result → INVALID. Stop.

---

## Estimand: What Exactly Are We Measuring?

> ICH E9(R1) 5 attributes. Fill ALL. Vague estimand = unmeasurable claim.

| Attribute | Value |
|---|---|
| **Population** | [Who/what — explicit inclusion/exclusion. e.g., "MCP tool calls with ≥50-char payloads, Python hooks only"] |
| **Intervention** | [What exactly — version, config, parameters. e.g., "input_guard.py v2 with TRUSTED_MCP_PREFIXES allowlist"] |
| **Comparator** | [vs. what — e.g., "input_guard.py v1 without allowlist", "no guard", "baseline"] |
| **Endpoint** | [Measured variable with units. e.g., "false-positive rate % on legitimate MCP calls over 12-day window"] |
| **Summary Measure** | [Population-level statistic: difference in means / risk difference / AUC delta / success rate / F1 delta] |
| **MCID** | [Minimum change that matters. Below this = not worth shipping. e.g., "≥20% FP reduction"] |

### Intercurrent Events (ICE)

Post-intervention events that change meaning or measurability of endpoint:

| ICE | Strategy | Rationale |
|---|---|---|
| [e.g., tool call timeout] | composite (count as failure) | [timeout = user-visible failure, not excludable] |
| [e.g., context overflow] | hypothetical (exclude) | [not caused by intervention under test] |
| [e.g., upstream API change] | treatment-policy (include) | [real-world conditions apply] |

**Strategy reference:**
- `treatment-policy` — include ICE as part of effect (pragmatic / real-world)
- `hypothetical` — model as if ICE hadn't occurred (ideal efficacy)
- `composite` — ICE becomes part of endpoint (failure counts as failure)
- `while-active` — truncate measurement at ICE occurrence
- `principal-stratum` — restrict to subgroup defined by ICE behavior ⚠️ requires nontestable assumptions

---

## Natural Language Estimand Statement

> One sentence a non-statistician can quote. Write BEFORE technical claim.
> Template: "We estimate [summary measure] of [endpoint] for [population], comparing [intervention] vs [comparator], handling [ICE] by [strategy]."

**Statement:** _______________________________________________________________

---

## Falsifiable Statement

> Derived from estimand. Technically precise. Specifies what would prove it WRONG.

> *(Example: "input_guard v2 reduces FP rate from baseline 8.3% to <2% for legitimate
> MCP tool calls (population: mcp__context7__* prefix calls over 12 days), handling
> timeout ICE by composite strategy (count as FP).)*

---

## What This Result Does NOT Mean

> Write BEFORE collecting results — protects against post-hoc interpretation drift.

1. This does NOT prove that _____ [generalization beyond tested population]
2. This does NOT establish causality if question type = descriptive/predictive
3. This does NOT apply when _____ [boundary condition: different dataset / time window / system version]
4. *(add specific to this experiment)*

---

## Falsification Criteria

What would FALSIFY this claim:
- [ ] [specific measurable failure — fill from estimand endpoint + MCID]
- [ ] positive control fails (known-good input rejected)
- [ ] performance regression on baseline
- [ ] ICE not handled as specified in estimand table above

## Success Criteria

What would CONFIRM this claim:
- [ ] [specific measurable success — endpoint crosses MCID threshold]
- [ ] positive control passes
- [ ] no regression on baseline
- [ ] ICE handled as specified — verified in controls.md

---

## Related

- Prior null results: *(grep `null_results/INDEX.md` for population/endpoint keywords)*
- Linked PR/issue:
- Overlapping estimands: *(search wiki for same population or endpoint in other experiments)*
