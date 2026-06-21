# Caveats

**Experiment ID:** `<YYYYMMDD-short-slug>`

---

## What This Result Does NOT Mean

> EstimandOps L7: explicit non-interpretations. Write BEFORE results are known.
> If you find yourself writing these AFTER seeing results — you're rationalizing.

1. This does NOT prove that _____ [generalization to untested population]
2. This does NOT establish causality *(if question type was descriptive or predictive)*
3. This does NOT apply when _____ [boundary condition: different data / time / system version]
4. This result is NOT valid if any of these assumptions break: _____
5. *(add specific to this experiment)*

---

## Interpretation Boundaries

> Conditions under which the interpretation is valid.

| Condition | Value | Consequence if violated |
|---|---|---|
| Population | [who/what the result applies to] | [generalization fails] |
| Time window | [when results were collected] | [temporal drift invalidates] |
| System version | [specific version tested] | [doesn't apply to other versions] |
| Data source | [where data came from] | [source shift invalidates] |
| ICE handling | [as specified in claim.md estimand table] | [estimand changes meaning] |

---

## Hard Limitations

Things this solution does NOT handle (known at time of decision):

1. [Limitation 1 — be specific, with example]
2. [Limitation 2]
3. [Limitation 3]

---

## Assumptions Made

Conditions under which the claim holds:

| Assumption | Testable? | Evidence | Risk if wrong |
|---|---|---|---|
| [Assumption 1: e.g., "valid for Python 3.11+"] | Y/N | [what supports it] | [what breaks] |
| [Assumption 2] | Y/N | | |
| [Untestable causal assumptions if question_type=causal] | N | "required by design" | [describe bias] |

---

## Unresolved Questions

Open issues that could affect the claim in production:

- [ ] [Question 1 — what would you need to know to be more confident?]
- [ ] [Question 2]

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| [Risk 1] | low/med/high | low/med/high | [what to do if it fires] |
| [Temporal drift] | med | med | [re-run experiment after major system change] |
| [Population shift] | low | high | [re-validate if population changes] |

---

## What Would Invalidate This in Production

> Specific scenario where the claim breaks in real use — be concrete.

1. [Scenario 1: e.g., "if MCP payload encoding changes, the regex pattern will miss injections"]
2. [Scenario 2]

---

## Sensitivity Analysis Plan

> For Full-Ladder: define ≥2 sensitivity checks before running primary analysis.

| Check | What it tests | Expected direction if assumption violated |
|---|---|---|
| [Alternative ICE strategy] | [robustness to ICE handling choice] | [direction] |
| [Alternative estimator] | [robustness to statistical method] | [direction] |
| [Alternative population] | [generalization to broader/narrower scope] | [direction] |
