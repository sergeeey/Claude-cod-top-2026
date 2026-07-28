# estimand.md — hypothesis-arbiter taxonomy + Oracle Adequacy Gate pilot

## L0 — Question type

**Causal.** The question is: does adding the 8-class generator taxonomy to
`hypothesis-arbiter`'s SPAWN step CAUSE the generated candidate set to include the
correct causal mechanism, compared to the unmodified SPAWN step, on a real case
with independently-verified ground truth?

## Population

Single real case (n=1 pilot, matching this repo's own OSA/FL pilot precedent of
starting with a small, cheap, real-case pilot before a larger population):
the `skeptic_auto_trigger.py` T1-trigger investigation from earlier this session
(2026-07-28). Real, tool-verified telemetry: 826 real hook firings logged in
`~/.claude/logs/hook_triggers.jsonl`, T1 (`high_confidence_claim`) alone = 737
(89.2%). Ground truth (independently confirmed via masked-context log analysis,
then via a negative-control harness proving the mechanism, then via a live
regression test on CI across Linux and Windows): the real cause is an ARTIFACT
class explanation — T1's regex matches the literal "100%" inside `pytest`'s own
`[100%]` stdout progress bar, which every completed test run prints. It is not
an authored claim, not a wording/prose match on "all/passed" phrasing (my own
first hypothesis this session, which was WRONG and had to be discarded after a
negative-control harness showed it explained only 1/7 of the observed cases).

## Intervention vs. comparator

- **Intervention (Arm B)**: `hypothesis-arbiter`'s SPAWN step as modified today
  (`19df07a`-adjacent uncommitted edit) — includes the 8-class taxonomy table
  (Mechanistic/Null/Artifact/Confounder/Reverse-causality/Boundary/Cross-domain/
  Adversarial) as an explicit checklist during hypothesis generation.
- **Comparator (Arm A)**: `hypothesis-arbiter`'s SPAWN step exactly as committed
  at `6ba1c29` (the version already benchmarked `dogfooded`, 10/10 on the
  `benchmarks/strong-inference/` corpus) — no explicit class taxonomy, just the
  4-6-hypotheses/H0-required/no-vague-wording rules.

## Endpoint

Binary, tool-checkable: does the arm's SPAWN-stage candidate table include a
hypothesis whose mechanism is "the trigger matches formatting/output produced by
a tool, not an authored claim" (i.e., an Artifact-class explanation), REGARDLESS
of whether the arm's later stages correctly promote it to the final answer?

WHY this endpoint and not "did the arm reach the final correct answer": the
question under test is specifically about SPAWN-stage diversity (Step 1 of the
5-stage cycle), not the full pipeline's overall correctness — the existing
benchmark already showed the full pipeline gets this class of question right
at 10/10 on unrelated tasks, so a full-pipeline correctness endpoint would be
subject to a ceiling effect and uninformative for isolating whether THIS ONE
addition changes anything.

## Summary measure

Presence/absence (Arm A: yes/no, Arm B: yes/no) of an Artifact-class hypothesis
in the SPAWN-stage candidate table. n=1 per arm — this is a cheap directional
pilot, not a powered comparison; see MCID below for what "cheap" commits to.

## MCID (minimum practically important difference)

Arm B includes an explicit Artifact-class candidate AND Arm A does not. This is
the *minimum* signal that would justify treating the taxonomy addition as doing
real work rather than being cost with no benefit — matching this session's own
recent, fresh counter-evidence (`null_results/20260728-osa-fl-protocol-vs-
standard-analysis.md`) that added protocol structure can measurably UNDERPERFORM
a simpler baseline, so the burden of proof here is on the addition, not the
status quo.

## ICE (intercurrent events)

None expected — this is a single, isolated generation step with no follow-up
interaction, no dropout, no post-randomization event to strategize around.

## What this result does NOT mean

1. Does NOT establish that the taxonomy addition improves FINAL-answer accuracy
   — endpoint is SPAWN-stage candidate diversity only, not pipeline correctness.
2. Does NOT generalize beyond this one case — n=1, explicitly a directional
   pilot, not a powered claim. A real population-level claim would need the
   same population-category discipline `strong-inference.md` §14 already uses
   for the existing benchmark (5 categories × ≥2 each).
3. Does NOT establish the Oracle Adequacy Gate addition does anything — this
   pilot's endpoint only exercises the SPAWN-stage taxonomy; the Oracle
   Adequacy Gate operates later (Этап 4) and is not isolated by this design.

## Grading (Oracle Adequacy, self-applied)

Blind grader (fresh `Agent` call, no session history, context-asymmetric):
given only the two arms' raw SPAWN-stage output tables (labeled "Transcript 1"
/ "Transcript 2", arm identity withheld) plus the ground-truth mechanism
description, judges independently whether each transcript's candidate table
contains an Artifact-class (or functionally equivalent) hypothesis. Negative
control: grader is also shown a deliberately-injected fake table with NO
Artifact-class entry, to confirm it correctly reports absence rather than
defaulting to "present" under ambiguity.
