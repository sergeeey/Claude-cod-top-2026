# SDE-CC Pilot Evaluation (3 cases)

**Scope:** this is a pilot per SDE-CC §25, not the full 40-case program. See
`research_scope.md` for why it was scoped down and what was compared against the
existing repo first.

## What the pilot found (cross-case pattern check)

Per SDE-CC §9's own rule, a pattern only counts as real if it appears in ≥3 independent
cases across ≥2 domains, with a stated mechanism and a counter-case. With only 3 cases
we cannot properly validate any pattern yet — but we can note candidate signals:

| Candidate pattern | Case 001 (Fleming) | Case 002 (Wegener) | Case 003 (AlphaFold) | Verdict |
|---|---|---|---|---|
| "Lone genius" myth | Busted — Florey/Chain/Jennings did the real development work | N/A — team not individually mythologized in sources reviewed | N/A — always framed as team (DeepMind) | Only 1/3 cases actually had this myth to bust — **not yet a validated cross-case pattern**, just one confirmed instance |
| Missing mechanism blocks acceptance even with good evidence | N/A | Confirmed — theory rejected specifically for lacking a mechanism, not lacking evidence | N/A — no rejection to explain | Only 1/3 cases — **insufficient support, single instance** |
| Hindsight/retrospective distortion risk varies with time-gap | High (1945 retelling of 1928 events, contested details) | Low-medium (well-documented pattern, one single-sourced causal claim) | Low (near-real-time documentation, peer-reviewed within a year) | **This one DOES show a real cross-case gradient** — the only pattern in this pilot that meets even a weak version of the ≥3-case bar, because it's observed as a *spectrum* across all 3, not a binary present/absent |

**Honest verdict: 1 out of 3 candidate patterns shows even weak cross-case support.**
The other two are single-case observations dressed as patterns — exactly the kind of
premature generalization SDE-CC §20 warns against ("чрезмерно общие эвристики").
This itself is a useful pilot result: it demonstrates the methodology's own bar is
strict enough to reject weak signal, which is a good sign for the methodology's
discipline, even though it means this pilot alone cannot produce a validated
`pattern_card` per the spec's own Gate 3 (Pattern Validity) criteria.

## Comparison to existing repo skills, revisited after doing real cases

The `boyko-specialist` "extract the skill from the win" origin story is itself a live
example of exactly the phenomenon this pilot studied: a real problem (locating a niche
specialist for dipolar dark matter cosmology) produced a reusable skill. That skill's
own v1.2.0 changelog is arguably a 4th, self-referential case card — an SDE-CC-style
discovery-to-methodology extraction event that already happened in this repo, in this
session, before this pilot started.

## Should this scale to the full 40-case program?

**Recommendation: not automatically.** Reasons:
1. Pilot pattern-validation rate (1/3 candidates survived even a weak check) suggests
   the real bar for a validated pattern (≥3 cases, ≥2 domains, stated mechanism,
   counter-case, per SDE-CC §9) will require substantially more than 40 cases to
   produce a small number of genuinely validated patterns — the ratio implied is
   closer to "many cases per 1 real pattern," not 1:1.
2. All 3 sources used were secondary, not primary (`research_scope.md` limitation) —
   scaling to 40 without securing primary-source access would just produce 40
   MEDIUM-confidence case cards, not the rigor the original spec's
   `minimum_primary_or_near_primary_sources_per_case: 2` demands.
3. The operational payoff (SDE-CC's Claude-Code-facing methodology, §11-14) is ~80%
   already implemented in this repo under different names (see `research_scope.md`
   comparison table). The historical research module's main remaining value is
   *validating which patterns are real* — worth doing selectively, not as a blanket
   40-case sweep.

**Alternative recommendation:** if this direction is worth pursuing further, do it
as a targeted top-up — pick 5-8 MORE cases specifically chosen to stress-test the one
surviving candidate pattern (hindsight-distortion-vs-time-gap) across more domains,
rather than a flat 40-case sweep with no prioritization.

## Limitations (explicit, per SDE-CC §22.6)

- Only secondary sources used; no primary lab notebooks, letters, or original papers
  directly accessed.
- 3 cases cannot validate any pattern per the spec's own ≥3-case/≥2-domain bar for a
  SINGLE pattern — this pilot is necessarily inconclusive on pattern validity by
  design, and should not be read as "the methodology doesn't work," only as
  "3 cases is not enough data, as expected."
- No adversarial/independent-evaluator review was run on this pilot's own case cards
  (SDE-CC's own Agent 6: Evaluator role) — this write-up is self-assessed, not
  independently checked, which the spec itself would flag as a gap if this were the
  full program.
