# Claim

**Experiment ID:** `20260727-config-effectiveness-opportunistic`
**Date:** 2026-07-27
**Author:** Claude (protocol proposed by human, this session)
**Ladder tier:** Full (research claim about the methodology itself, causal-adjacent — a wrong verdict here could justify stripping or keeping the entire CLAUDE.md apparatus)

---

## Context (why this replaces two earlier, rejected approaches)

This is the third design for testing whether the full CLAUDE.md/rules/skills/hooks
configuration actually improves outcomes, superseding two prior approaches discussed
earlier in this session (not written to disk before context compaction — reconstructed
here from the human's own summary, not independently verified against a transcript):

1. **~10 scripted synthetic scenarios** — rejected: scenario design leaks the tester's own
   idea of what should be caught, and a fixed scenario set can be gamed/overfit once known.
2. **Passive monitoring of ordinary sessions** — rejected: no clean ground truth (most
   ordinary work never resolves to a checkable "was there a bug here" answer), and no
   controlled comparison (you only ever see the config you're actually running).

## Step 0 (MANDATORY FIRST): Question Type — L0 Gate

**[x] Predictive** — "Given a real task and three config variants (vanilla / minimal /
standard), does variant predict catch/no-catch on that task's pre-specified ground truth?"

Not causal: no DAG, no claim about *why* a rule catches something, no intervention on a
population outside this observational-within-task comparison. Not descriptive: the point
is to generalize the catch-rate difference to future tasks, not just describe this sample.

---

## Estimand: What Exactly Are We Measuring?

| Attribute | Value |
|---|---|
| **Population** | Real, currently in-flight tasks (bug, review, security-check, or any task with a checkable claim) from any project the human or Claude is actually working — NOT retrospectively resolved tasks, NOT synthetic/constructed-for-this-test tasks. **Inclusion:** (1) the correct answer is not yet known at task-selection time but WILL become known by doing the real work regardless of this experiment; (2) a one-line catch/no-catch criterion can be written before any of the 3 variants' output is seen; (3) the task is one where config differences are plausibly load-bearing (not a trivial task any config would pass). **Exclusion:** tasks whose ground truth is already known; tasks invented specifically to be caught; tasks too expensive to run 3x without delaying the real work materially. Accumulated opportunistically, one at a time, as they arise — not pre-selected as a batch. **N (expected):** unknown in advance, accumulates over time; no fixed target, tracked as a running population in `results.json`. |
| **Intervention** | Copy C: full standard config — this repo's actual `CLAUDE.md` + `rules/` + `skills/` + `hooks/` as currently checked out, unmodified. |
| **Comparator** | Two separate comparators, each its own contrast against C: Copy A (vanilla — no `CLAUDE.md`, no `.claude/`) and Copy B (minimal — a single anti-hallucination-equivalent doc only, no rules/skills/hooks). |
| **Endpoint** | Binary catch/no-catch per copy, decided against the task's pre-registered one-line criterion (written before seeing any of the 3 outputs). |
| **Summary Measure** | Risk difference: proportion caught by C minus proportion caught by A (and separately, minus proportion caught by B), across the accumulated task population. Paired design (same task, all 3 copies) — NOT an independent-samples comparison, so the estimator must respect pairing (see estimator note below). |
| **MCID** | \|risk difference\| >= 0.2 (20 percentage points) — same threshold family this project's own null_results already use for practical-vs-statistical significance, chosen for direct comparability, not re-derived per experiment. |

### Intercurrent Events (ICE)

| ICE | Strategy | Rationale |
|---|---|---|
| Task abandoned before ground truth resolves (human moves on, work superseded) | hypothetical (exclude, do not impute) | No ground truth exists to score against; imputing would fabricate data |
| One or more copies crash/error out before producing an answer | composite (count as no-catch for that copy) | An agent that crashes has practically failed to catch anything, regardless of cause |
| Task's ground truth turns out ambiguous even after resolution (reasonable people disagree) | while-active (exclude that unit, log separately) | Don't force a binary label onto a genuinely ambiguous case; log it rather than silently drop it |

---

## Natural Language Estimand Statement

> We estimate the risk difference in catch-rate on a pre-specified binary criterion,
> between the standard CLAUDE.md configuration and each of two comparators (vanilla,
> minimal), for real in-flight tasks accumulated opportunistically (one at a time, as they
> arise, not pre-selected), handling abandoned-task and crashed-copy ICE by exclusion and
> composite-failure respectively.

---

## Falsifiable Statement

"Across the opportunistically accumulated task population, the standard config's
catch-rate exceeds vanilla's by >=20 percentage points (risk difference), OR the true
effect is smaller than that and this claim is wrong." Falsified if the accumulated risk
difference stays below 0.2 (or is negative) after a pre-registered minimum of 8 tasks
(see `experiment.yaml` — chosen as the smallest N where a risk difference this large is
even in principle distinguishable from noise via an exact paired test, not an arbitrary
round number).

---

## What This Result Does NOT Mean

1. Does NOT prove *which* specific rule/skill/hook inside "standard" did the catching —
   this is a whole-config A/B/C, not a component ablation.
2. Does NOT establish causality about *why* config helps (if it does) — Predictive, not
   Causal, per L0 above.
3. Does NOT generalize beyond the kind of tasks that got opportunistically included — if
   every accumulated task happens to be, say, Python bug-fixing, the result says nothing
   about docs review or infra changes.
4. Does NOT replace a real controlled trial — this is small-n, opportunistic, and the
   population is whatever tasks happened to come up, not a representative sample of "all
   possible tasks." Treat conclusions as directional evidence, not a definitive verdict,
   until N is large enough for the pre-registered MCID to be distinguishable from noise.

---

## Falsification Criteria

- [ ] Accumulated risk difference (C vs A) < 0.2 after >=8 tasks
- [ ] Positive control fails (see `controls.md` — a task with an obvious catch that even
      vanilla should get; if vanilla passes it too often, the task pool is too easy)
- [ ] Direction reverses (vanilla catches MORE than standard on accumulated population)

## Success Criteria

- [ ] Accumulated risk difference (C vs A) >= 0.2, permutation p < 0.05 (paired exact test)
- [ ] Negative control passes (a task where NO reasonable config should catch anything —
      confirms the criterion isn't rigged to always fire)
- [ ] Effect direction consistent (not driven by 1-2 outlier tasks — check via leave-one-out)

---

## Related

- Prior null results: none yet in this project (`null_results/INDEX.md` empty)
- Overlapping estimands: `experiments/_template/estimand.md` (generic template, this
  claim's estimand.md is the filled Full-tier version, written same day)
