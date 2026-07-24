# Skill maturity criteria

Added 2026-07-24, closing plan item P2-16 (`docs/baselines/2026-07-24-plan.md`).
The enum and its evidence-citation enforcement already existed in
`scripts/check_architecture.py` (`gate_kind_maturity`, Gate 10) before this
file did — this document is the missing plain-language rubric for what each
rung actually means, so promoting a skill is a judgment against a stated bar,
not a vibe.

## Why this exists

Before this file, `registry.yaml` had 128 skills and exactly 1 with a real
`maturity_evidence` citation (`hypothesis-arbiter`). Not because the other
127 are all untested, but because there was no written definition of what
"tested enough" means at each rung — so nobody had a bar to promote against,
and the honest default was to leave everything at `wired`.

## The ladder

`maturity: described | wired | dogfooded | benchmarked` (`_MATURITY_VALUES`
in `check_architecture.py`).

### `described`
`SKILL.md` exists, documents intended behavior and triggers. Never invoked
for real, or invoked but never checked against a known-correct outcome. This
is the default for a newly-written skill.

### `wired`
Registered in `registry.yaml`, resolvable by the dispatcher/router,
`depends_on` targets exist (Gate 9 checks this). May have been invoked in
passing during normal work, but nobody has deliberately checked its output
against a known-correct answer and written that down anywhere. This is where
most of the 128 skills sit today, and for most of them that's an honest
place to be — not every skill needs `dogfooded` status to be useful.

### `dogfooded`
Promoting to `dogfooded` requires ALL of:

1. **A real invocation**, not a hypothetical walkthrough — the skill was
   actually run (`Skill(...)` or the equivalent agent path) against a task
   with a checkable outcome.
2. **A citable artifact**, checked at commit time by Gate 10: `registry.yaml`
   `` name: -- description "" `` splits on the first `` -- `` and the leading
   segment must be a real, repo-relative path that exists. A prose claim
   inside the skill's own `SKILL.md` does *not* count — that's the skill
   citing itself, the exact "evidence laundering" pattern
   `rules/perelman-audit.md` names as an anti-pattern (one source "confirming"
   multiple claims, here the same source confirming its own maturity).
3. **A task that could have failed.** Synthetic test cases are acceptable
   for a *methodology/verifier* skill IF they're constructed with a known
   correct answer designed to catch a specific failure mode (this is unit
   testing a checker, not validating a claim about the real world — see
   `rules/skeptic-triggers.md`'s Trigger 5 for the boundary). Synthetic data
   is NOT acceptable as evidence for a skill whose job is to produce claims
   *about* the real world (research-scout, boyko-specialist, etc.) — those
   need a real task with a real, checkable outcome.
4. **The result is disclosed honestly**, failures and all. A run that
   surfaced a real gap and got fixed (see `hypothesis-arbiter`'s B6 run
   finding real grader bugs before the number was trusted) is *better*
   evidence than a suspiciously clean first pass — see
   `rules/skeptic-triggers.md` on round numbers and zero-failure claims.

### `benchmarked`
Everything `dogfooded` requires, plus a **comparative** result against a
baseline (arm-vs-arm, not skill-vs-nothing-written-down) with an
**MCID-anchored** threshold defined *before* the run
(`rules/estimand-ops.md`), and — if grading involves any subjective
judgment — an **inter-rater reliability** check.

**Worked example, and why the bar is genuinely hard:**
`hypothesis-arbiter` is the one skill in this repo with a full comparative
benchmark: `benchmarks/strong-inference/run-2026-07-23-full.md`, n=10 tasks,
Arm B (hypothesis-arbiter) 10/10 vs Arm A (plain) 6/10 — 4x the stated MCID.
By the letter of "comparative + MCID" above it clears the bar. It is
nonetheless still recorded as `dogfooded`, not `benchmarked`, in
`registry.yaml` — because the follow-up Cohen's kappa computation
(`benchmarks/strong-inference/compute_kappa.py`) came back **κ = 0.565**,
"moderate" on Landis & Koch (1977), short of "substantial" (0.61+). The
session that ran this explicitly left the `dogfooded` → `benchmarked`
call as "a judgment call for the user, not decided unilaterally" rather
than rounding a moderate kappa up to a passing grade. That standing,
unresolved judgment call is itself the reference point for how strict
`benchmarked` is meant to be — treat it as the bar, not as an example to
relax.

## Anti-theater checklist before setting `maturity_evidence`

Before writing `dogfooded`/`benchmarked` on any skill, check all of:

- [ ] The citation target file exists and is not the skill's own `SKILL.md`
- [ ] The run happened this session or is traceable to a real past commit —
      not reconstructed from memory (see `rules/falsification-ladder.md`'s
      Hindsight Distortion Gap Heuristic: a same-session record beats a
      reconstructed one)
- [ ] If the result is suspiciously clean (100%, zero failures), that alone
      is a `skeptic-triggers.md` trigger — re-verify before writing it down
- [ ] For `benchmarked` specifically: baseline + MCID were defined before
      seeing results, not fitted after

## Status

As of 2026-07-24: 1/128 skills at `dogfooded` (`hypothesis-arbiter`), 0/128
at `benchmarked`. Promoting additional skills requires actually running them
for real per the checklist above — this document defines the bar, it does
not itself promote anything.
