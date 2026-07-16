# RFC-001 — Claim Pipeline: Claimify front-stage + claim-type routing for claim-decomposer

**Status:** DESIGN-SETTLED (Sprint 4, decisions D1–D3 resolved 2026-07-16). The three
open questions are answered (see "Resolved decisions"); the routing is fixed at 5. The one
remaining step is the baseline-vs-improved benchmark RUN, which needs claim-decomposer in
the LLM loop and a human "go" — not a number to fabricate here.
**Owner:** design accepted by the author on 2026-07-16; overall RFC still open to owner
revision, and the benchmark run is the gate before any implementation merges.
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

Enhance (do not replace) `claim-decomposer` with a front-stage and a router. The
front-stage lives **inside** `claim-decomposer` as its new first stages (decision D1),
not as a separate skill:

```
free text
  → [Selection]        which spans carry verifiable information?
  → [Disambiguation]   resolve reference/scope; ABSTAIN if a span can't be pinned down
  → [Decomposition]    the existing atomic decomposition (unchanged)
  → [Type classify]    label each atom into one of 5 routes (table below)
  → [Evidence route]   send each atom to the machinery its type needs
  → [Contradiction map + Recomposition + Gate]   (existing, unchanged)
```

### Claim-type routing table (5 routes — decision D3)

The router targets **5** routes, each with genuinely distinct machinery. This is
smaller than the 8-label corpus on purpose: the corpus keeps finer labels for
measurement, the router maps them to these 5 (see D3 for why, and the mapping).

| Route | Next step | Existing machinery |
|-------|-----------|--------------------|
| **FACTUAL** | check directly: source / data / run it | evidence markers (`rules/integrity.md`); metric sub-checks (denominator, round-number) via `rules/skeptic-triggers.md`; procedural = run it |
| **CAUSAL** | estimand + DAG + identifiability | `rules/estimand-ops.md` L0 gate |
| **PREDICTIVE** | time-boxed future test | FL `claim.md` with a deadline |
| **HYPOTHESIS** | competing hypotheses + kill-test | `hypothesis-arbiter` |
| **NORMATIVE** | surface values + trade-offs, return — NO evidence gate (decision D2) | (terminal flag, not a verification route) |

**Corpus-label → route mapping** (the 8 labels in `tests/corpus/claims/claims.jsonl`
stay; they are finer than the routes and collapse into them):

| Corpus label | Route |
|--------------|-------|
| OBSERVATIONAL_FACT, METRIC_CLAIM, PROCEDURAL_CLAIM | FACTUAL |
| CAUSAL_CLAIM | CAUSAL |
| PREDICTION | PREDICTIVE |
| SCIENTIFIC_HYPOTHESIS | HYPOTHESIS |
| NORMATIVE_CLAIM | NORMATIVE |
| ARCHITECTURE_DECISION | *out of claim-pipeline scope* — an ADR concern (`decisions.md`), not a claim to verify |
| AMBIGUOUS, UNVERIFIABLE | *no route* — ABSTAIN at the Selection/Disambiguation stage |

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
eight labels plus ambiguous-should-abstain and unverifiable cases. This is the train/test
substrate. The benchmark is:

1. Run current claim-decomposer over the corpus → record type-labelling accuracy +
   abstention behaviour (baseline).
2. Run the enhanced pipeline → same measurement.
3. Compare; FL Standard `experiments/` run with `claim.md` written BEFORE the numbers.

**This RFC does not report a result.** The measurement needs claim-decomposer running in
the LLM loop (per-claim judgment), which is not a pure-code test — it is a follow-up with
a human in the loop, not a number to fabricate here. Shipping a benchmark corpus without
a run is honest scaffolding; shipping a "42% → 89%" without the run would be theater.

## Resolved decisions (2026-07-16)

All three open questions were resolved by one shared principle: **do not fix an
abstraction or a granularity that no consumer can yet support.** The same discipline
scoped capability-fields (Sprint 2.1) and packs (Sprint 5) to real needs.

### D1 — Front-stage lives INSIDE `claim-decomposer`, not as a separate `claim-selector`

A separate skill is justified only by a **second** confirmed consumer of "extract
verifiable claims from free text." There is exactly one today: `claim-decomposer` itself.
(The guard classifier from Sprint 2.2 solves a different problem — directive-to-the-agent,
not claim-selection; release-scout's novelty step is a grep; `sci-evidence` takes an
already-formed hypothesis.) One consumer → a stage, not a skill; a separate skill now
would be the premature abstraction this repo keeps declining to build.

The gap is real (`claim-decomposer` today assumes a claim is already given), so Selection
+ Disambiguation become its new first stages.

**Extraction trigger:** if a second consumer appears (e.g. a summary-checker or a
citation-extractor that wants selection WITHOUT the contradiction-map / recompose
machinery), extract to a `claim-selector` skill THEN — and wire it as
`claim-decomposer.depends_on: [claim-selector]`. Not before.

### D2 — NORMATIVE_CLAIM stays IN, as a terminal flag — never a verification route

The value of classifying a normative claim is not to verify it (a value judgment has no
evidence gate) — it is to **recognize it precisely so the system STOPS instead of
fake-verifying it.** The real failure mode is mis-reading "correctness matters more than
speed" as factual/causal and burning machinery hunting for evidence of a value. So
NORMATIVE is a route whose action is: surface the implicit values + trade-offs, label as
opinion, return to the human — no evidence gate. In the corpus these rows are already
`verifiable: false`, which is correct.

### D3 — Route on 5, not 8; grow only if the benchmark earns it

Each of the 8 labels formally routes differently, but that is not the test. The test is
whether an LLM classifier **reliably separates them** — and RFC-001's benchmark has not
been run, so that reliability is `[UNKNOWN]`. The most-confused pairs are
OBSERVATIONAL↔METRIC and PREDICTION↔HYPOTHESIS. Collapsing to 5 (see routing table above)
keeps every route that carries genuinely distinct machinery — CAUSAL especially must stay
its own route, since "association read as causation" is the exact error `estimand-ops`'s
L0 gate exists to catch — while removing the classifier's hardest confusions.
`ARCHITECTURE_DECISION` leaves the claim-pipeline entirely (it is an ADR concern, not a
claim to verify). METRIC-specific checks (denominator, round-number) survive as
sub-checks inside FACTUAL, not as a separate route.

The corpus keeps all 8 labels (finer than the routes) so the benchmark can measure
whether the classifier COULD separate the collapsed sub-types — the evidence needed to
justify growing 5→8 later. Do not pre-commit to 8-way routing before that evidence exists.

## Status after decisions

Design is settled; the benchmark RUN is the one remaining step, and it is the
human-in-the-loop follow-up described above — not a number to fabricate here. Sprint 4 is
unblocked to proceed to that run on a "go".
