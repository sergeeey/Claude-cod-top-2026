# RFC-001 — Claim Pipeline: Claimify front-stage + claim-type routing for claim-decomposer

**Status:** PROPOSED (Sprint 4). Design + benchmark corpus land here; the implementation
and the baseline-vs-improved run are a follow-up that needs claim-decomposer in the LLM
loop and a human "go".
**Owner:** left for the user to accept/modify.
**Related:** `skills/core/claim-decomposer/SKILL.md`, `rules/estimand-ops.md`,
`skills/extensions/hypothesis-arbiter`, `skills/extensions/proof-ladder`,
`docs/research-sources.yaml` (Microsoft Claimify row).

## Problem

`claim-decomposer` today decomposes a complex claim into atoms → contradiction map →
recomposition → gate. It assumes the input is already a claim worth decomposing, and it
treats all atoms alike regardless of what KIND of claim each is. Two gaps:

1. **No selection/abstention front-stage.** Free-form text (a paragraph, an abstract,
   an LLM answer) is not yet a set of claims. Deciding which spans are verifiable, and
   abstaining when a span is too ambiguous to claim anything, is a distinct step that
   happens before decomposition — and it is exactly what Microsoft's Claimify formalises
   (Selection → Disambiguation → Decomposition).
2. **No claim-type routing.** "X is associated with Y" and "X causes Y" need different
   verification machinery, but decomposition treats both as generic atoms. The repo
   already HAS the type-specific machinery (estimand-ops for causal, hypothesis-arbiter
   for hypotheses, proof-ladder for proofs) — it just isn't wired to a type classifier.

## Proposal

Enhance (do not replace) `claim-decomposer` with a front-stage and a router:

```
free text
  → [Selection]        which spans carry verifiable information?
  → [Disambiguation]   resolve reference/scope; ABSTAIN if a span can't be pinned down
  → [Decomposition]    the existing atomic decomposition (unchanged)
  → [Type classify]    label each atom (table below)
  → [Evidence route]   send each atom to the machinery its type needs
  → [Contradiction map + Recomposition + Gate]   (existing, unchanged)
```

### Claim-type routing table

| Type | Next step | Existing machinery |
|------|-----------|--------------------|
| OBSERVATIONAL_FACT | source + independent check | evidence markers (`rules/integrity.md`) |
| CAUSAL_CLAIM | estimand + DAG + identifiability | `rules/estimand-ops.md` |
| PREDICTION | time-boxed future test | FL claim.md with a deadline |
| SCIENTIFIC_HYPOTHESIS | competing hypotheses + kill-test | `hypothesis-arbiter` |
| METRIC_CLAIM | dataset + formula + denominator + uncertainty | `rules/skeptic-triggers.md` (round-number/baseline) |
| NORMATIVE_CLAIM | surface values + trade-offs | (no auto-verification — flag as opinion) |
| PROCEDURAL_CLAIM | runtime reproduction | actually run it |
| ARCHITECTURE_DECISION | alternatives + constraints + consequences | ADR in `decisions.md` |

## What is deliberately NOT adopted from Claimify

- **Its reported metrics (99% entailment, 96.7% precision) are NOT imported as our
  numbers.** They are Microsoft's, on Microsoft's data. Marked `[UNVERIFIED_EXTERNAL]`
  in `docs/research-sources.yaml`. RFC-001's own benchmark (below) is how we would get a
  number we can stand behind.
- **We do not vendor the unofficial `deshwalmahesh/claimify` code** — we take the method
  from the paper and write our own small version, per that repo's own "unofficial,
  differs from paper" caveat.

## How we would MEASURE it (the honest part)

`tests/corpus/claims/claims.jsonl` — a bilingual (RU+EN) labelled corpus spanning all
eight types plus ambiguous-should-abstain and unverifiable cases. This is the train/test
substrate. The benchmark is:

1. Run current claim-decomposer over the corpus → record type-labelling accuracy +
   abstention behaviour (baseline).
2. Run the enhanced pipeline → same measurement.
3. Compare; FL Standard `experiments/` run with `claim.md` written BEFORE the numbers.

**This RFC does not report a result.** The measurement needs claim-decomposer running in
the LLM loop (per-claim judgment), which is not a pure-code test — it is a follow-up with
a human in the loop, not a number to fabricate here. Shipping a benchmark corpus without
a run is honest scaffolding; shipping a "42% → 89%" without the run would be theater.

## Open questions for the user

1. Should the Selection/Abstention front-stage live inside `claim-decomposer` or as a
   separate upstream skill (`claim-selector`) that feeds it? (Cohesion vs single-purpose.)
2. Is NORMATIVE_CLAIM in scope at all, or out (the repo is evidence-focused, and
   normative claims have no evidence gate — maybe they should just be flagged and
   returned, not routed)?
3. Accept the eight-type taxonomy, or a smaller set? More types = more routing surface.
