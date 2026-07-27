# Estimand Document (EstimandOps 2.0)

**Experiment ID:** `20260727-config-effectiveness-opportunistic`
**Version:** 1.0.0
**Date:** 2026-07-27
**Author:** Claude (protocol proposed by human)
**Pre-registered:** [x] No — internal only (written before any pilot task's ground truth
is known, which is what matters for validity here, even without external registration)

---

## L0: Question Type

**[x] Predictive** — forecasts catch/no-catch for new real-world tasks, no causal
mechanism claim. See `claim.md` for full L0 reasoning. L3 (Causal Layer) is N/A per the
template's own instruction for Predictive questions.

---

## L1: Core Attributes

Full detail in `claim.md`'s Estimand table (Population/Intervention/Comparator/Endpoint/
Summary Measure/MCID) — not duplicated here verbatim to avoid the two documents drifting
out of sync. Summary for cross-reference:

```
Population:   opportunistically accumulated real in-flight tasks, N unknown in advance
Intervention: Copy C — full standard CLAUDE.md/rules/skills/hooks (this repo, as-is)
Comparator:   Copy A (vanilla, no config) and Copy B (minimal, one anti-hallucination doc)
Endpoint:     binary catch/no-catch per pre-registered one-line criterion
Summary:      risk difference (C vs A, and separately C vs B), paired by task
MCID:         |risk difference| >= 0.2
```

## L1b: Intercurrent Events

See `claim.md` ICE table (task-abandoned / copy-crashed / ground-truth-ambiguous).

---

## L2: Decision Context

| Attribute | Value |
|---|---|
| **Decision maker** | The human (repo owner) |
| **Decision** | Keep the full CLAUDE.md/rules/skills/hooks apparatus as-is, trim it toward "minimal," or drop it toward "vanilla" |
| **Action space** | {keep standard, adopt minimal, go vanilla, redesign specific underperforming rules} |
| **FP cost** (concluding standard helps when it doesn't) | Continued maintenance burden on an elaborate rule/skill/hook system that isn't earning its complexity cost — real but recoverable (can simplify later) |
| **FN cost** (concluding standard doesn't help when it does) | Stripping down to vanilla/minimal and silently losing real bug/hallucination-catching capability across every future session — harder to detect after the fact, since there's no longer a comparison running |
| **Loss function type** | Asymmetric — FN cost is plausibly worse (silent capability loss vs. visible maintenance cost), but this is the human's call to weigh, not something this estimand can resolve |
| **Practical threshold** | Risk difference >= 0.2 (MCID above) triggers "keep/strengthen standard"; risk difference indistinguishable from 0 across a reasonable N triggers "seriously consider trimming toward minimal" |

---

## L3: Causal Layer

N/A — question type is Predictive, not Causal (see L0). If a future version of this
experiment wants to make a causal claim ("standard config CAUSES better catch rates,"
not just "predicts/correlates with"), it needs its own L3 with a DAG and identifiability
checks — not assumed here.

---

## L4: Data Reality

| Attribute | Value |
|---|---|
| **Data source** | Live, opportunistic capture of real work — not CI logs, not synthetic, not a pre-existing dataset |
| **Missingness mechanism** | MNAR risk exists: tasks that are "too hard to bother running 3x" may be systematically the tasks where config differences matter MOST (high-stakes, ambiguous) — flagged here as a known bias, not solved. Any task excluded for cost/time reasons should be logged in `results.json` with a reason, not silently dropped, so this bias is at least auditable later. |
| **Censoring** | Non-informative for the "task abandoned" ICE (assumed unrelated to which copy would have caught it) — this assumption is NOT verified and should be revisited if abandoned-task count grows large relative to completed count |
| **Known biases** | (1) Selection: the human picks which real tasks become pilot units — conscious or not, tasks that "feel like a good test" may be pre-filtered toward ones standard config plausibly wins; (2) Order effects: running copy C (with full context/memory of the actual codebase from real work) alongside fresh A/B copies is not perfectly symmetric — C's context window may carry incidental info the fresh copies lack purely from HOW the task was described, not from config; mitigate by giving all 3 copies the identical task prompt, not letting C "know more" from prior conversation |
| **Measurement error in endpoint** | The catch/no-catch criterion is written by a human (or Claude) BEFORE seeing outputs specifically to reduce this, but grading whether a given output actually satisfies that criterion is still a judgment call, not automatic — no inter-rater reliability check planned given small N; flag as a real limitation, not solved |
| **Time alignment** | Each task's 3 copies run at the same git commit (`git worktree add` from one SHA) — this is explicitly required precisely to avoid immortal-time-style bias from codebase drift between copies |
| **Data-generating process** | Not experimentally randomized — every included task gets ALL THREE conditions (paired), not a random subset getting each. This is a repeated-measures design, not an RCT; the estimator must respect that (see L5) |

---

## L5: Estimator Mapping

| Field | Value |
|---|---|
| **Primary estimator** | Exact paired sign-style test on the (C-caught, A-caught) binary pairs — reuse this project's established from-scratch, no-scipy convention (permutation test on the paired difference, same pattern as DNA Ladder's `paired_permutation_test`), NOT an independent-samples test (Mann-Whitney/Fisher would ignore the pairing and understate power or misstate variance) |
| **Rationale** | Data is paired by construction (same task, same prompt, 3 copies) — McNemar-family exact tests are the standard estimator for paired binary outcomes; permutation variant chosen to stay consistent with this project's existing no-external-dependency statistical toolchain rather than introducing scipy for a single test |
| **Required assumptions** | Task-level independence (task N's result doesn't mechanically influence task N+1's — plausible but not verified, since the same human is choosing tasks over time and could unconsciously adjust selection based on prior results; mitigate by writing the catch criterion before seeing prior tasks' verdicts too, not just before seeing the current task's 3 outputs) |
| **Mandatory diagnostics** | Leave-one-out check (does the verdict flip if any single task is removed — a small-N red flag, not proof of robustness) |
| **Sensitivity estimator 1** | Simple proportion difference with a normal approximation CI, reported alongside the exact test as a cross-check, not a replacement |
| **Sensitivity estimator 2** | Per-comparator split (C vs A alone, C vs B alone) instead of pooling — checks whether "standard beats vanilla" and "standard beats minimal" tell the same story or diverge (minimal existing but incomplete could plausibly perform close to standard on some tasks) |

---

## L6: Robustness Plan

| Check | Description | When to run |
|---|---|---|
| Sensitivity estimand | Re-run with a stricter catch criterion (partial credit excluded) vs. the primary lenient one | After >= 8 tasks accumulated |
| Alternative estimator | Simple proportion-difference CI (L5 sensitivity 1) | Every update, alongside primary |
| Subgroup stability | Split by task type (bug-fix / review / security-check / other) if population is large enough | Once population >= 15 |
| Tipping point | How many additional no-catch tasks for C would erase the observed effect | After first positive-looking result, before declaring success |
| Temporal validation | n/a — no obvious time-window structure yet; revisit if accumulation spans months and the config itself changes mid-experiment (see Governance change log) |

---

## L7: Communication Layer

### Natural Language Statement

> We estimate the risk difference in catch-rate on a pre-specified binary criterion,
> between the standard CLAUDE.md configuration and each of two comparators (vanilla,
> minimal), for real in-flight tasks accumulated opportunistically, handling
> abandoned-task and crashed-copy intercurrent events by exclusion and composite-failure
> respectively.

### Technical Statement

```
Let D_i = 1{C catches task i} - 1{A catches task i}, paired by task i.
Estimand: E[D] (risk difference), estimated via mean(D_i) across accumulated population,
significance via exact permutation test on the paired sign pattern.
Repeated separately for D'_i = 1{C catches} - 1{B catches}.
```

### What This Result Does NOT Mean

See `claim.md` — not duplicated here.

### Interpretation Boundaries

- Valid for: the specific set of tasks that happened to get included, weighted by
  whatever selection bias exists in how they were chosen (see L4)
- Valid for: this specific version of "standard" config — if `CLAUDE.md`/rules/skills
  change materially mid-experiment, log it (Governance below) and consider whether
  earlier and later tasks are still comparable
- Does NOT apply when: the config under test differs meaningfully from what's actually
  checked out at experiment time — always re-verify Copy C = current HEAD before each run

---

## L8: Governance

| Field | Value |
|---|---|
| **Pre-registered** | [ ] No — internal only |
| **SAP version** | v1.0 (this document) |
| **SAP written before data access** | [x] Yes — no pilot task has been run yet as of this writing |
| **Approval** | Human (repo owner), verbally in this session |
| **Change log** | (empty — log any changes to this estimand here, with date and reason, especially if made after seeing partial results) |

---

## Estimand Review Checklist

- [x] Question type classified (L0) — Predictive
- [x] All 5 ICH attributes filled (L1, in `claim.md`)
- [x] ICE identified and strategy assigned
- [x] MCID defined (0.2 risk difference)
- [x] Natural language statement written
- [x] "What this does NOT mean" filled (in `claim.md`)
- [ ] For causal: N/A (Predictive, not Causal)
- [x] Primary estimator matches estimand (paired exact/permutation test, not independent-samples)
- [x] >=2 sensitivity estimators named
- [x] Mandatory diagnostics listed (leave-one-out)
- [x] Governance fields complete
