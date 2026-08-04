# decision.md — Pairwise Elo-style hypothesis ranking for variant-tournament.md

**Experiment ID:** 20260715-pairwise-elo-tournament-premature-recommendation
**Date:** 2026-07-15
**Verdict:** REJECT (recommendation withdrawn, not implemented)

## Claim tested

"Adding a pairwise Elo-tournament ranking mode (modeled on Google DeepMind's
AI Co-Scientist) to `docs/variant-tournament.md`, as an alternative to the current
absolute single-metric scoring (Step 3-4), would be an improvement for cases where
`success_metric` is a judgment call rather than a hard measurement."

## Method

Real-world research trail: found Google's AI Co-Scientist architecture (6 agents +
supervisor, Elo-style pairwise tournament ranking for hypotheses) via `WebSearch`.
Proposed importing pairwise comparison into this repo's `variant-tournament.md` on
the reasoning "LLM judges are more reliable at relative comparison than absolute
scoring" — sourced from a general literature summary, not a specific verified paper.

User asked "а есть исследования на эту тему?" (are there actual studies on this).
Went back and verified with real papers instead of the general summary.

## Findings — direct source conflict

- General search summary (multiple 2025-2026 blog-level sources): pairwise
  comparison framed as "gold standard," absolute scoring framed as unstable/drifting.
- **[VERIFIED via WebFetch]** "The Coin Flip Judge? Reliability and Bias in
  LLM-as-a-Judge Evaluation" (arxiv.org/pdf/2606.13685, >10,000 judgments examined):
  the OPPOSITE finding — pairwise comparisons are LESS stable on re-evaluation
  (judges reverse preference when the quality margin is small), and the paper's
  core finding is that pairwise forced-choice format specifically manufactures
  confident "winners" between options that are statistically indistinguishable.
  Absolute (pointwise) scoring showed better re-test consistency in their data.
- A third source (openreview.net, "Pairwise or Pointwise? Evaluating Feedback
  Protocols for Bias in LLM-Based Evaluation") could not be read — the fetch
  returned only a login wall, not paper content. Marked `[UNKNOWN]`, not guessed.

## Why rejected

The original recommendation was made on a single convenient literature summary
without checking a primary source — exactly the failure mode
`rules/rationalizations.md` #1 and `rules/integrity.md`'s Spot-Check Rule exist to
catch. When checked, the strongest single available primary source (highest sample
size, most specific methodology) directly contradicts the premise the
recommendation was built on. With `[CONFLICTING]` evidence and no way in this
session to resolve which side is right for THIS repo's specific use case (an
audited, falsification-contract-gated tournament — not a generic chatbot-response
comparison, which is what most of the cited literature studies), the responsible
call is REJECT, not "50/50 so let's ship it and see."

## Decision

**REJECT.** Do not add a pairwise Elo-tournament mode to `docs/variant-tournament.md`
on the current evidence. The existing absolute-scoring mechanism (Step 3: exactly
one locked `success_metric`, pre-committed controls) already has its own guard
against the specific failure mode ("Coin Flip Judge") that pairwise comparison is
now shown to be vulnerable to: a hard, pre-registered success metric with
pass/fail controls does not let the judge "confidently declare a winner" on a
statistically meaningless margin, because the metric is not a subjective judgment
call to begin with in the cases variant-tournament.md was designed for.

## What would change this

If a future case genuinely needs `success_metric` to be a soft judgment (no hard
test possible) AND a primary source resolves the pairwise-vs-pointwise conflict
specifically for structured, audited comparisons (not open-ended chatbot outputs),
re-open this with that source cited directly, not a summary of it.

## Reviewers

Main session, self-caught after user's direct question forced re-verification of an
un-sourced claim made two turns earlier in the same conversation.
