---
id: TC-009
name: Morrison Null Test — fluent but unfalsifiable claim
category: zero-signal-gate
severity: critical
---

## Input
My hypothesis is that this general approach will make the system better
overall. Let's design an experiment to test it.

## Expected
- assertion: contains_any
  values: ["REFUSE", "no_falsifiable_claim", "falsifiable predicate", "measurable outcome", "specific", "what does \"better\" mean", "define"]

## Rationale
`rules/falsification-ladder.md`'s Zero-Signal Gate names this exact phrasing
as its own kill-signal example for the falsifiable-predicate field: "works
better", "is good", "helps". The sentence is fluent, grammatically well
formed, and uses the auto-trigger word "hypothesis" — the hardest case for
a system that pattern-matches on hypothesis-shaped SYNTAX rather than
checking whether the claim actually has a fillable entity/predicate/outcome
triple. This is the case most likely to slip past a shallow gate.

No `not_contains` artifact-filename check, same reason as TC-007/TC-008.
