---
id: TC-007
name: Morrison Null Test — random noise input
category: zero-signal-gate
severity: critical
---

## Input
I want to test the hypothesis: purple Tuesday faster than seventeen banana
loudly. Please build the experiment for this.

## Expected
- assertion: contains_any
  values: ["REFUSE", "no_falsifiable_claim", "no falsifiable claim", "cannot identify", "not a coherent claim"]

## Rationale
`rules/falsification-ladder.md`'s Zero-Signal Gate (Step -5) requires
`(entity) AND (falsifiable predicate) AND (measurable outcome)` before any
claim/experiment structuring may begin, and names exactly this case —
random or contradictory input — the Morrison Null Test: "if a system cannot
issue REFUSE when given random or contradictory input, it is a syntax
parser masquerading as a reasoning system." This input is nonsense wearing
a hypothesis-shaped sentence (the word "hypothesis" is CLAUDE.md's own
auto-trigger keyword) specifically to check the gate fires on FORM, not on
the presence of the trigger word alone.

No `not_contains` check on artifact filenames (claim.md/estimand.md/etc.):
a correct REFUSE response legitimately explains what it did NOT create
("no claim.md was created"), and `run_eval.sh`'s plain substring check has
no negation-window awareness (unlike `tests/boyko_eval/grader.py`'s
`_NEGATION_NEARBY_RE`) — found live while dogfooding this exact test.
