# boyko-goal-expansion-100 — quick mode, registry-drift prevention

**Date:** 2026-09-05
**Object:** does quick mode (<=30 ideas, minimal search, no full dedup/audit)
produce a genuinely distinct, non-padded solution space for a real, current
project goal, with an honest top-3 and at least one explicit no-go?

## Why this run exists

Real, current goal surfaced by this same session's own `boyko-leverage-map`
run (Top-3 item #2): prevent the "registry declared-vs-actual drift" pattern
(7 named instances across this repo's history) from recurring for future
declarative fields, cheaply, without a from-scratch meta-architecture.

## Protocol

Ran quick mode per the skill's own reduced-rigor spec for this tier. Feasibility
scored 8/10 (concrete, cheaply achievable engineering goal, not an open
science question). Generated ~10 mechanism-distinct ideas (explicitly fewer
than 30, per the skill's own "honest smaller number, don't pad" rule) across
established methods, cross-domain transfers, one computational-experiment
idea, and one explicit no-go.

## Result

10 ideas produced, deduplicated by mechanism (not wording) down from an
internal pool that included near-duplicates -- e.g. "municipal permit
inspection" and "DNA polymerase proofreading" both map to the same abstract
mechanism (check embedded at creation-time, not audited later) and were kept
as SEPARATE cards only because they suggest different concrete
implementations (pre-commit hook timing vs. CI-gate-at-merge timing), not
counted as independent ideas for scoring purposes.

**Top-3 by adjusted_score:**
1. Exhaustive tagged-union field checking (TypeScript-style) -- highest
   structural leverage, requires the most refactoring effort.
2. TDD-for-the-registry (require a failing test before a new field is added)
   -- cheapest, reuses this repo's own existing `tdd-workflow` skill.
3. "Broken windows" policy (retroactive audit for similar undiscovered
   instances in the SAME PR that fixes one) -- zero code cost, and this
   session already did this spontaneously today (Gate 10 fix cascaded into
   fixing `docs/skill-maturity-criteria.md`'s stale count).

**Explicit no-go:** a standalone meta-schema microservice -- named and
rejected as disproportionate to the stated "cheap" success criterion, not
silently omitted.

## Result vs the object question

Yes: the set is genuinely mechanism-distinct (not "apply AI" restated 10
ways), includes one explicit no-go rather than padding to a round number, and
the top-3 selection names a concrete trade-off (highest-leverage vs.
cheapest) rather than picking one winner without showing what's given up.

## Limitation

Quick mode explicitly skips full dedup/audit and external WebSearch
validation of prior art -- all 10 ideas are grounded in general software-
engineering/cross-domain knowledge, not verified against real external
sources (no citations beyond this repo's own artifacts). A `deep` or
`frontier` mode run would require real WebSearch grounding per the skill's
own anti-hallucination rules, not done here.
