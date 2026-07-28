# Claim

**Experiment ID:** `20260728-osa-fl-protocol-vs-standard-analysis`
**Date:** 2026-07-28
**Author:** Claude (this session, proposal reviewed and approved by user: "го")
**Ladder tier:** Full (research claim about the methodology itself — this repo's
own core rules: `perelman-audit.md`, `falsification-ladder.md`'s OSA integration,
`doubt-driven-development.md`)

---

## Context — why this experiment exists

A user-provided document described 3 "non-obvious methodologies" (Refute-or-
Promote, Perelman-Style Universal Audit, Option Space Audit) that turned out to
match this repo's own rules almost verbatim. Comparison surfaced candidate
additions (OVS numeric score, EVI/Optimal Stopping). Red-teaming those
candidates (Doubt-Driven Development Trigger 1 applied to the rules themselves)
concluded: do not add new formal machinery on spec — it risks the exact "false
precision" and "resource paralysis" failure modes the source document itself
named. The one action that doesn't add ceremony and does add real evidence:
**test whether the existing protocol actually outperforms standard/informal
analysis**, the same way `hypothesis-arbiter` was validated
(`benchmarks/strong-inference/run-2026-07-23-full.md`).

## Step 0 (MANDATORY FIRST): Question Type — L0 Gate

**[x] Causal** — "Does applying the full OSA/FL/Perelman protocol to a claim's
raw evidence (vs. standard/informal analysis on the SAME raw evidence) cause a
better-reasoned kill/promote verdict?" This is causal, not predictive: both arms
receive IDENTICAL frozen input (the same raw claim + evidence), and only the
analysis METHOD is manipulated — a controlled comparison, not an observational
one. (Contrast with `20260727-config-effectiveness-opportunistic`, which is
Predictive because ITS population is opportunistically selected in a way that
introduces real selection bias — that bias doesn't apply here: the 2 raw
materials used are fixed, already-existing historical artifacts, not chosen
after seeing which arm would look good.)

---

## Estimand: What Exactly Are We Measuring?

| Attribute | Value |
|---|---|
| **Population** | Real historical claims from this repo's own `null_results/` that have a documented REJECT verdict, used in their PRE-verdict raw form (the original claim + the evidence available before the null-result reasoning was written) — currently **n=2** (`20260716-regex-composition-response-guard`, `20260716-llm-judge-response-guard`). **This is a pilot, not a confirmatory run** — n=2 is far below the n≥8 convention this repo already uses elsewhere (`20260727-config-effectiveness-opportunistic/claim.md`) for a confirmatory verdict. More cases accumulate opportunistically as future null results occur (same accumulation pattern as that experiment), each one added as a new pilot data point, not retrofitted. |
| **Intervention** | Arm B: a fresh agent, given ONLY the raw claim + evidence (no access to the real, already-written null_results file), instructed to follow this repo's actual OSA/FL/Perelman apparatus (claim_entropy-style reasoning, No-Collapse-Test-style stability check, Kill Analysis mandate: what's killed / what's NOT killed / Relaxation Map, Anti-Overfitting Gate if proposing a revision) and produce a verdict + reasoning. |
| **Comparator** | Arm A: a fresh agent, same raw claim + evidence, instructed to analyze it as a competent domain expert would WITHOUT the formal apparatus — normal engineering judgment, no claim_entropy/Kill Analysis/AOG scaffolding required (this approximates "standard/ACH-style expert analysis" from the source document's own suggested baseline). |
| **Endpoint** | Blind-graded comparison of each arm's output against the REAL, already-documented null_results verdict (used as a semi-gold-standard — an honest caveat, not perfect ground truth, since it's one prior session's own judgment, not an external authority). Grading rubric (0–3 each, by an independent blind grader who does not know which arm produced which output): (1) correctly identifies the real root cause / core failure mode named in the real verdict; (2) avoids the specific anti-pattern the real verdict warned against (e.g., "don't just patch symptoms"); (3) reasoning is falsifiable/specific, not vague; (4) actionability — does it give a concrete next step matching the real verdict's own recommendation. |
| **Summary Measure** | Per-case score difference (Arm B total − Arm A total, 0–12 scale), reported per case (n=2 is too small to pool into a single statistic with any confidence) plus qualitative comparison. |
| **MCID** | Provisional, pilot-only: a difference of ≥3 points (of 12) on a given case is treated as "the formal apparatus meaningfully helped on this case" — NOT treated as confirmatory at n=2, explicitly labeled exploratory per this repo's own N<8-exploratory convention. |

### Intercurrent Events (ICE)

| ICE | Strategy | Rationale |
|---|---|---|
| Arm's output references or appears to have seen the real null_results file (contamination) | while-active (exclude that unit, log separately) | Contamination invalidates the comparison for that case only |
| Blind grader's verdict is itself ambiguous/disputed | hypothetical (record both readings, do not force a single score) | Forcing false precision on a genuinely ambiguous grading call would be the exact "false precision" failure this experiment exists to avoid importing |

---

## Natural Language Estimand Statement

> We estimate the per-case difference in blind-graded verdict quality (0-12
> rubric) between applying this repo's full OSA/FL/Perelman protocol and
> standard informal analysis, to the SAME raw pre-verdict claim+evidence from
> 2 real historical null_results, treating each case as an individual pilot
> data point (not pooled into a single confirmatory statistic given n=2),
> handling contamination via exclusion.

---

## Falsifiable Statement

"On at least one of the 2 pilot cases, Arm B (full protocol) scores ≥3 points
higher than Arm A (standard analysis) on the blind rubric, AND the higher
score is attributable to a specific protocol mechanism (Kill Analysis / AOG /
stability check), not just longer output." Falsified if Arm A matches or beats
Arm B on both cases, or if Arm B's edge (if any) doesn't trace to a specific
mechanism the protocol adds.

---

## What This Result Does NOT Mean

1. Does NOT prove the protocol is worth its overhead in general — n=2 is a
   pilot; a real answer needs the same accumulation this repo already uses
   for `config-effectiveness-opportunistic`.
2. Does NOT establish causality about WHY a mechanism helps (if it does) —
   this measures whether it helps, not the mechanism of the effect.
3. Does NOT generalize beyond REJECT-verdict null results — both pilot cases
   are rejections; PROMOTE-shaped claims might show a different (or no)
   effect, untested here.
4. Does NOT replace real-time protocol use with a one-shot retrospective
   comparison — retrospective grading against an already-written verdict is
   weaker evidence than a live, prospective run where nobody knows the answer
   yet (the config-effectiveness-opportunistic design is prospective; this one
   is deliberately retrospective, because real historical null_results with a
   documented verdict already exist and using them is cheaper than waiting).

---

## Related

- Prior null results used as raw material: `null_results/20260716-regex-composition-response-guard.md`, `null_results/20260716-llm-judge-response-guard.md`
- Precedent for the benchmark methodology: `benchmarks/strong-inference/run-2026-07-23-full.md` (hypothesis-arbiter's own validation)
- Rejected alternative designs: OVS (numeric score) and EVI/Optimal Stopping were considered and explicitly NOT added to the protocol before running this — see this session's own comparison discussion (not yet a separate artifact; summarized here for the record).
