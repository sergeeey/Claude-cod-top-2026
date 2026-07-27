# decision.md — SDE-CC "v1.0" (91-file, 40-case) historical research claim

**Experiment ID:** 20260715-sde-cc-fabricated-historical-corpus
**Date:** 2026-07-15
**Verdict:** REJECT

## Claim tested

"SDE-CC v1.0" document claims: 40 verified historical discovery cases across 8
disciplines, 20 discovery patterns (Tier 1 = "universal, high confidence, ≥3 cases/
≥2 domains"), 91 supporting artifact files, "7/9 Quality Gates passed", methodology
directly transferable to Claude Code with high confidence.

## Method

Independent honest pilot (this session) produced 3 real case cards via `WebSearch`/
`WebFetch` (Fleming/penicillin, Wegener/continental drift, AlphaFold) with every claim
cited to a real URL. Result: only 1 of 3 candidate cross-case patterns survived even a
weak validity check (see `docs/scientific-discovery-engineering/evaluation_report.md`).

The SDE-CC v1.0 document was then audited three ways:
1. `boyko-triangle-audit` — checked Theory/Computation/Verification/Explanation
   vertices against the document's own text.
2. `boyko-knowledge-audit` — epistemic level classification of 14 atomic claims.
3. `skeptic` (Mode 3) — adversarial falsification attempt + spot-checks against the
   independently-verified pilot case (continental drift).

## Findings

- **Computation vertex: missing.** Document's own text marks the one gate that would
  demonstrate usefulness (`sde_cc_results.json`, benchmark execution) as
  "⏳ Ожидает исполнения" — not done, despite everything else marked ✅.
- **Epistemic audit: 0 of 14 claims reached Level 1-3 with solid in-text evidence.**
  `hardness_index = 0.36`, and even that overstates it (all Level-1 claims are
  self-reported status lines, not independently verifiable data). The document's
  rhetorical register ("установлено с высокой уверенностью") is consistently higher
  than any claim's earned epistemic level (mostly Level 6 — Hypothesis).
- **Factual error found and reproduced across runs.** The "Newton's apple — Voltaire
  1727, 40 years after the event, no contemporary evidence" claim is FALSE
  (`[VERIFIED]` via WebSearch): the real gap is ~60 years, and a 1726 contemporary
  account (Conduitt, from Newton himself) exists. The *same specific wrong numbers*
  appeared in this document, indicating the case was not independently re-verified
  from a real source but reproduced from a prior (also unverified) telling.
- **Categorical mismatch found via direct pilot comparison.** Document 3 files
  "Тектоника плит" (plate tectonics) under pattern P011 "Collective Intelligence"
  alongside Penicillin and AlphaFold. The independently-verified pilot case
  (`historical_cases/case_002_continental_drift.yaml`) shows this is a poor fit:
  Wegener worked alone and was rejected for decades specifically for lacking a
  mechanism; vindication came from an unrelated, unplanned oceanographic research
  program 20-40 years after his death — structurally closer to an unplanned
  side-finding (this repo's own Pearl Registry concept) than to deliberate team
  collaboration (which is what P011 as labeled implies).
- **No case content given for several Tier-1 patterns** (e.g. P014 lists zero named
  cases in the executive summary), yet carries the same "высокая уверенность" label
  as patterns with 3 named cases — flagged by `boyko-knowledge-audit`'s Level
  Consistency Pass as an unjustified uniform-confidence labeling.
- **Zero URLs or citable sources anywhere in the document**, in contrast to the
  independently-verified pilot, where every claim carries a real fetched source.

## Why falsified (not just "incomplete")

This is not merely an unfinished MVP (that would be an honest, acceptable status —
see the document's own honest "⏳" marker on the benchmark). It is falsified because
the specific factual claims checked (3 of 3) were wrong or mischaracterized, and the
pattern is consistent with a document synthesized from training-data pattern-matching
presented with fact-level confidence language, not from an actual verification process
matching what it claims to have done ("40 verified cases").

## Decision

**REJECT** the document's claims of established, high-confidence, universal discovery
patterns. Do not treat "SDE-CC v1.0" as validated input for building Claude Code
tooling. Do not retry by requesting a "bigger" version of the same ungrounded
synthesis — any future attempt must require inline citations per claim (as this
session's own 3-case pilot did) before any pattern can be trusted.

## What survives / next cheap step

The **operational layer comparison already done and NOT falsified**:
SDE-CC's stage structure (Observe→Frame→Baseline→...→Knowledge Capture) genuinely
maps onto skills already in this repo (`boyko-specialist`, `hypothesis-arbiter`,
`cross-domain`, `multi-lens`, `rules/falsification-ladder.md`) — see
`docs/scientific-discovery-engineering/research_scope.md`. That comparison used real
file reads of this repo's own skills, not unverified historical claims, and stands.

## Reviewers

Main session (builder + de-facto skeptic), `boyko-triangle-audit` skill,
`boyko-knowledge-audit` skill, `skeptic` skill (Mode 3).
