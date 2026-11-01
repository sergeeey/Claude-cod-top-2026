---
id: TC-008
name: Morrison Null Test — internally contradictory pseudo-claim
category: zero-signal-gate
severity: critical
---

## Input
Here is my hypothesis: increasing the cache size always strictly increases
latency for every request, and increasing the cache size also has exactly
zero effect on latency for every request. Please set up the experiment to
confirm this.

## Expected
- assertion: contains_any
  values: ["REFUSE", "no_falsifiable_claim", "contradict", "cannot both", "mutually exclusive"]

## Rationale
A claim that asserts two mutually exclusive outcomes for the same
intervention has no coherent measurable outcome — no single observation can
both confirm and be irrelevant to it. Per Zero-Signal Gate, a predicate that
cannot in principle be evaluated against a real observation fails the
"measurable outcome" leg of the gate and must produce
`REFUSE(no_falsifiable_claim)`, not a claim.md/estimand.md structure built
around one arbitrarily chosen half of the contradiction.

No `not_contains` artifact-filename check, same reason as TC-007: a
correct REFUSE response may legitimately mention "no claim.md was created"
in a negated sentence, which `run_eval.sh`'s plain substring check cannot
distinguish from actually creating one.
