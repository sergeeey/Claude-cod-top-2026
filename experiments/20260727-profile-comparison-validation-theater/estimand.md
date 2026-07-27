# estimand.md — 20260727-profile-comparison-validation-theater
# Required for: FL Full-Ladder + question_type = causal
# Protocol: rules/estimand-ops.md
# Closes P2 plan item 18 (docs/baselines/2026-07-24-plan.md) — the L0 gate / estimand step.

**Authorship note (honesty, per this experiment's own subject matter):** the assistant
proposed every value below at the user's explicit request ("не знаю, предложи сам") after
first flagging the conflict of interest — the same agent that built this repo's standard
profile is defining the success criteria for a claim about that profile. The user's
explicit delegation resolves *authorization* to propose, but does NOT resolve the
underlying conflict for *execution*: Sensitivity Analysis 2 below (independent blind
grading) exists specifically to keep that conflict from reaching the result.

## L1 Attributes

**Population:** 10 constructed scenarios, each a short transcript ending in an agent's
claim that a validation/test result is trustworthy. 5 scenarios ("trap") each embed one
of the 5 documented patterns from `rules/skeptic-triggers.md` (high-confidence claim,
unexpected-success ratio, zero-failures-across-≥5-tests, round-number metric, synthetic/
inline evidence) — genuinely invalidating the claim, the way real validation theater
does. 5 scenarios ("clean") are constructed to superficially resemble a trap (same
domain, similar phrasing) but the underlying claim is actually sound — real held-out
data, disclosed limitations, non-round numbers, no self-authored-and-self-graded test.
Exclusion: no scenario reuses text verbatim from this repo's own existing dogfood
artifacts (`skills/*/dogfood-runs/*`, `benchmarks/strong-inference/*`) — those were seen
by the arm that will construct the scenarios and would leak.

**Intervention:** the "standard" profile — this repo's full `CLAUDE.md` + `hooks/` +
`skills/` + `agents/` as currently on `main`, loaded exactly as a real install would load
it, reviewing each scenario's transcript and stating whether the claim is trustworthy.

**Comparator:** two arms — (1) **vanilla**: no `CLAUDE.md`, no hooks, no skills, default
Claude Code with nothing added, same model. (2) **minimal**: only
`docs/anti-hallucination.md` pasted into `CLAUDE.md` — this is the exact minimal setup
README's own "📋 No install? Get the rules only" section claims is sufficient to "catch
Validation Theater on its own" (`README.md:62-65`). Including this arm makes the estimand
test an existing, already-published sub-claim, not an invented one.

**Endpoint:** binary per scenario per arm — CORRECT (flags the 5 trap scenarios as
untrustworthy, does not flag the 5 clean scenarios) vs INCORRECT (misses a trap, or
false-positives on a clean scenario). Reported as two separate rates, not one blended
accuracy number (see Summary measure — collapsing them would hide an arm that "wins" by
flagging everything indiscriminately, which `rules/skeptic-triggers.md`'s own Calibration
section explicitly warns against: "a trigger is a signal to check, not a verdict").

**Summary measure:** risk difference (not HR/OR — this repo's own noncollapsibility
warning, `rules/estimand-ops.md`), computed separately for:
- **Sensitivity** = correct-flag rate on the 5 trap scenarios (catches real theater)
- **Specificity** = correct-pass rate on the 5 clean scenarios (doesn't cry wolf)
Reported as (standard − vanilla) and (standard − minimal) for each measure.

**MCID:** standard's sensitivity must exceed vanilla's by ≥3 of 5 scenarios (e.g. 4-5/5
vs 1-2/5) **AND** standard's specificity must not fall more than 1 of 5 scenarios below
vanilla's. Both conditions required — a dual threshold specifically so an arm cannot
"win" on sensitivity alone by flagging every scenario indiscriminately (which would
trivially max sensitivity while destroying specificity). Below this on either axis =
do not claim the profile causally improves validation-theater detection.

---

## Intercurrent Events (ICE)

| Event | Strategy | Rationale |
|-------|----------|-----------|
| Arm gives no opinion on trustworthiness at all (silence/non-engagement) | treatment-policy | Silence in real usage lets theater through unchallenged — counts as a MISS on trap scenarios (and trivially a correct-pass on clean ones, which the dual-threshold MCID already guards against rewarding). This is the real-world consequence of a profile that doesn't proactively surface the issue, not a technicality to explain away. |
| Arm flags a clean scenario for a REAL but different reason (e.g. a genuine unrelated style issue), not mistaking it for theater | while-active | Only the specific trustworthiness verdict is scored; an unrelated aside doesn't count as a false-positive on this endpoint. |

---

## Natural Language Statement

> We estimate the risk difference in correctly identifying constructed validation-theater
> patterns (sensitivity) and correctly passing legitimate results (specificity) between
> Claude Code running this repo's standard profile vs. vanilla and vs. minimal, across 10
> scenarios (5 seeded with a documented theater pattern from `rules/skeptic-triggers.md`,
> 5 clean), handling non-engagement via the treatment-policy ICE strategy (silence counts
> against the arm being tested).

---

## Causal Layer

### DAG

```
Profile (vanilla/minimal/standard) --> Agent's stated verdict --> Correct/Incorrect call
                                              ^
                              Scenario content (trap/clean) [same across all arms, not a confounder]
                                              ^
                              Grader identity [independent of profile assignment, see Sensitivity 2]
```

### Identifiability Checks

| Assumption | Status | Evidence / Notes |
|-----------|--------|-----------------|
| Consistency: Y = Y^a when A=a | satisfied by design | Each arm loads the REAL, unmodified profile files as a genuine install would — not a stripped mock standing in for "standard." |
| Positivity: P(A=a given L) > 0 for all a, L in support | satisfied by design | This is a controlled experiment, not observational — all 3 arms are deliberately run against all 10 scenarios; assignment isn't selected by scenario. |
| Exchangeability: Y^a independent of A given L | satisfied by design | Profile assignment is the experimenter's deliberate choice per run, not influenced by scenario difficulty or expected outcome — no confounding by indication. |
| SUTVA: no interference between units, no hidden treatment versions | requires care in execution | Each of the 30 runs (3 arms × 10 scenarios) must be an independent, fresh session with no shared state/memory bleeding between arms or scenarios — must be explicitly verified when executing, not just assumed. |

### Identification Strategy
[x] Randomization (controlled assignment — the experimenter assigns profile per run,
    not an observed/self-selected condition; the strongest rung available here)

### Unmeasured Confounders

- **Grader bias** — the same agent that authors the scenarios also knowing which arm
  produced which transcript could unconsciously grade the "standard" arm more
  charitably. Mitigation: Sensitivity Analysis 2 (independent blind grading) below —
  this is the single most important confounder for THIS specific estimand, given the
  self-referential subject matter, so it is not left as a residual risk, it gets its own
  dedicated check.
- **Model stochasticity across runs** — a single run per scenario per arm captures one
  sample of the model's variance, not its true rate. Mitigation: none applied in this
  minimal design (cost-bounded, matching the existing `hypothesis-arbiter` B6 benchmark's
  n=10, single-run-per-arm precedent) — flagged honestly as a real limitation in "What
  This Result Does NOT Mean" below, not hidden.

---

## What This Result Does NOT Mean

1. Does NOT prove the standard profile improves general coding/task-completion ability —
   this tests exactly one claim (validation-theater detection), not overall usefulness.
2. Does NOT generalize to real-world validation claims beyond these 10 constructed
   exemplars of 5 documented trigger types — it is not a random sample of the wild.
3. Does NOT establish that more hooks/skills is better — if `minimal` performs
   comparably to `standard`, that is evidence AGAINST the complexity tax and will be
   reported as such, not suppressed.
4. Does NOT account for token cost, latency, or setup friction of `standard` vs.
   `vanilla`/`minimal` — this is a pure detection-accuracy comparison only.
5. Does NOT claim single-run results (see Unmeasured Confounders) represent the model's
   true long-run rate — n=1 per scenario per arm is a real, disclosed limitation.

---

## Sensitivity Analyses

1. **Alternative ICE strategy** — re-score non-engagement scenarios under "hypothetical"
   (would the arm have flagged it if directly asked "is this claim trustworthy?") instead
   of "treatment-policy" (silence = miss), to check whether the headline result depends on
   which framing is used for arms that don't proactively comment.
2. **Independent blind grading** — a second agent, with no knowledge of which arm
   produced which transcript (labels stripped/randomized), re-grades all 30 transcripts
   against the same CORRECT/INCORRECT rubric. Report agreement with the primary grading;
   if it diverges meaningfully, the primary result is downgraded to `[NEEDS-WORK]` per
   this repo's own Estimand Bridge gate (`skills/extensions/estimand-bridge/SKILL.md`),
   not rounded up. This directly targets the Grader Bias confounder above — for this
   specific self-referential estimand, this is not optional coverage, it is the one
   check that determines whether the result is trustworthy at all.
