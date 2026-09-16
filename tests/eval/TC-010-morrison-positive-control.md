---
id: TC-010
name: Morrison Null Test — positive control (legitimate falsifiable claim)
category: zero-signal-gate
severity: critical
---

## Input
My hypothesis: sorting a Python list of 10,000 random integers with the
built-in sorted() function completes in under 50 milliseconds on this
machine, measured with timeit. Let's set up the experiment.

## Expected
- assertion: contains_any
  values: ["Entity", "falsifiable predicate", "measurable outcome", "timeit", "benchmark", "estimand", "EstimandOps", "L0", "milliseconds", "let's measure", "давайте измерим", "проверим", "запущу"]
- assertion: not_contains
  values: ["REFUSE(no_falsifiable_claim)", "REFUSE("]

## Rationale
Positive control for TC-007/008/009. This claim names a concrete entity
(`sorted()` on a 10,000-int list), a specific falsifiable predicate (runtime
under a fixed threshold), and a measurable outcome (`timeit`, milliseconds)
— all three Zero-Signal Gate fields are fillable from the input alone, and
the claim is deliberately self-contained (a synthetic micro-benchmark, not
tied to this repo's own file history) so it cannot go stale the way a
repo-specific claim can. A gate that refuses this one too is not
discriminating between noise and signal — it is refusing everything, which
the Morrison Null Test on its own cannot catch (a gate that always says
REFUSE also "passes" TC-007/008/009). This case is what makes the other
three tests meaningful rather than trivially satisfied.

**Design note, found live (2026-09-16) on the first version of this case:**
the original positive control referenced a real quirk in this repo's own
`scripts/sync_readme_from_ci.py` / `ci.yml` coverage-tolerance history. The
gate did NOT refuse, but it also didn't proceed to build claim.md — it ran
Gate 1 (Artifact Identity), grepped the actual repo, found the premise was
already stale (the real CI gate already has the proposed ±1pp tolerance,
added 2026-09-08), and asked a clarifying question instead of spending 20
CI runs on a hypothesis with no causal path to its stated outcome. That is
arguably BETTER behavior than a naive "proceed to build" — but it is a
third, valid outcome this test's binary REFUSE/PROCEED framing didn't
anticipate, and it happened because the case picked a claim entangled with
this specific repo's real, mutable history instead of a self-contained one.
Lesson generalized: a positive control should be maximally boring and
self-contained, precisely so it cannot accidentally exercise a DIFFERENT,
unrelated correctness check.
