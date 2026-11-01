# Live-only lines from global novelty-assessment (not in repo), saved 2026-11-01 before deploy
name: novelty-assessment
description: Assess research idea novelty through systematic literature search. DUAL independent screening in at least two vocabularies (own phrasing + adjacent-field terms), scored by relative recall against a pre-specified benchmark set. Three outcomes — novel / not_novel / recall_failure — because "nothing found" is usually a wrong-vocabulary search, not an empty niche. Use before committing to a research direction.
Triggers: /novelty-assessment, оценка новизны, is this novel, новизна идеи, prior art check.
triggers: [/novelty-assessment, "оценка новизны", "is this novel", "новизна идеи", "prior art check"]
- Assessment prompts and criteria: `~/.claude/skills/novelty-assessment/references/assessment-prompts.md`
**Why two.** Measured in systematic-review methodology: single-reviewer screening
misses **13%** of relevant studies; dual screening misses **3%**. A single agent
running N rounds is single-reviewer screening no matter how large N is.
the 13%→3% gain is lost. Reconcile only after both have returned.
- **Novel**: BOTH screeners returned nothing overlapping, AND relative recall = 1.0, AND the citation chase is **complete** (Step 2.3 item 6) and found nothing overlapping
  single-reviewer screening (13% miss rate) regardless of round count.
cost one parallel call. That is the 13%→3% gain, observed rather than cited.
| single-reviewer screening misses ~13% of relevant studies; dual screening ~3% | systematic-review screening methodology |
- `/negative-space-miner` — Stage 8 delegates its mandatory Novelty Check here; without delegation the status caps at `closely related`
