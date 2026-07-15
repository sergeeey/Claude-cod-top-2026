# Research Scope — Scientific Discovery Engineering (Pilot)

**Status:** PILOT (3 cases), not the full 40-case program specified in the original request.
**Why scoped down:** the full spec (25 sections, 40+ verified historical cases, 12-task
benchmark, ablation study, subagent architecture) is a multi-week research program.
Producing all of it in one session would require either fabricating case cards without
real source verification, or a scope this repo's own `rules/skeptic-triggers.md` and
`rules/falsification-ladder.md` would flag (round numbers, unverifiable claims, no
pilot-first validation). This pilot follows the original spec's own §25 "Первый шаг"
instruction: do a small pilot on 3 contrasting cases before scaling.

**Research date cutoff:** 2026-07-15 (session date; all WebSearch results reflect
publicly indexed content as of this date, not necessarily the most recent scholarship).

## Comparison with existing repo methodology (done first, per user request)

Before researching history, we compared the target methodology (SDE-CC) against skills
already in this repo. Finding: the *operational* layer (stages "Observe → Frame →
Baseline → ... → Knowledge Capture") is ~80% already implemented, just under different
names:

| SDE-CC concept | Existing repo equivalent |
|---|---|
| Cheap Experiment Ladder | `boyko-specialist` Phase 0.5 (added this session, same session that produced this pilot) |
| Hypothesis Portfolio | `hypothesis-arbiter` (Chamberlin/Platt multiple working hypotheses) |
| Analogy Search (structural isomorphism) | `cross-domain` (30-bridge catalog) |
| Representation Transformations | `multi-lens` (20 analytical lenses) |
| Falsification | `rules/falsification-ladder.md` |
| Assumption Audit | `common-ground` |
| Knowledge Capture | `null_results/INDEX.md`, `pearl_registry/INDEX.md`, `patterns.md` |
| Evidence markers | `rules/integrity.md` `[VERIFIED-REAL]/[INFERRED]/[UNKNOWN]` etc. |

**The one genuinely new part is the historical-case-study layer** (SDE-CC §1-10) — this
pilot tests only that layer, on 3 cases, to see whether it's worth building out further.

## Sample selection (3 cases, chosen for contrast per SDE-CC §6 diversity criteria)

| Case | Domain | Contrast dimension |
|---|---|---|
| Penicillin (Fleming, 1928) | Medicine/biology | Canonical "pure accident" myth — good target for myth-audit |
| Continental drift (Wegener, 1912) → plate tectonics | Earth science | Correct idea rejected for ~50 years, vindicated by new instrument-derived evidence (seafloor age dating) |
| AlphaFold (DeepMind, 2018-2020) | Computational biology | Modern, instrument(compute)-driven discovery, well-documented, no "genius myth" framing to begin with |

## Source policy applied

Real `WebSearch` + `WebFetch` only. Every claim below is tagged:
- `[VERIFIED]` — corroborated by ≥1 real fetched/searched source, URL cited
- `[UNKNOWN]` — could not confirm within pilot budget, stated explicitly, not invented

No fabricated quotes, dates, or documents. This pilot did **not** reach primary sources
(lab notebooks, original papers) — it used secondary sources (encyclopedic, academic
review articles, a dedicated myth-debunking piece for the Fleming case). This is a
**known limitation** of the pilot, not a claim of primary-source rigor — the full spec's
`minimum_primary_or_near_primary_sources_per_case: 2` requirement is **not met** here.
