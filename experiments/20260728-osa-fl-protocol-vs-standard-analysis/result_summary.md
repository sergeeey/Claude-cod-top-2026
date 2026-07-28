# result_summary.md — 20260728-osa-fl-protocol-vs-standard-analysis

## Design (recap)

2 real historical REJECT-verdict `null_results/` cases, raw pre-verdict material
(claim + design + measurement, stripped of the original investigator's
reasoning/conclusion) given byte-identical to two fresh, independent agents per
case: **Arm A** (standard/informal expert analysis, no scaffolding, explicit
tool-use ban) vs **Arm B** (instructed to Read this repo's real
`falsification-ladder.md` + `perelman-audit.md` + `doubt-driven-development.md`
and apply that methodology, same tool-use ban otherwise). A third, independent
blind grader per case scored both outputs 0–12 (4 sub-scores × 0–3) against the
real documented verdict, unlabeled (`Output 1` / `Output 2`), with instructions
to flag — not penalize on — any style-based arm-identity leakage.

## Contamination check (ICE)

Neither Arm A nor Arm B output referenced `null_results/`, RFC IDs, the real
verdict's specific named failure classes, or any vocabulary/example not present
in the raw package given. Arm B agents' `tool_uses` count matched exactly the 3
whitelisted Read calls (no Grep/Glob/extra Read). **No contamination excluded
from scoring.** Both blind graders DID detect arm identity from *style*
(Arm B's output visibly uses the methodology's own jargon — `claim_entropy`,
`No-Collapse Test`, `Kill Analysis` — vs Arm A's plain prose) — flagged per the
estimand's Exchangeability mitigation, graders were instructed to score content
only regardless, and did so (see their stated reasoning per sub-score below).

## Scores

| Case | Arm A (standard) | Arm B (protocol) | Δ (B − A) | MCID (≥3) crossed? |
|---|---|---|---|---|
| `regex-composition-response-guard` | 9/12 | 5/12 | **−4** | Yes — in A's favor |
| `llm-judge-response-guard` | 9/12 | 7/12 | **−2** | No |

**Arm A (standard/informal analysis) outscored Arm B (full protocol) on BOTH
pilot cases.** No case shows Arm B beating Arm A, let alone by the pre-registered
MCID of ≥3 points.

## Falsifiable Statement — outcome

> "On at least one of the 2 pilot cases, Arm B (full protocol) scores ≥3 points
> higher than Arm A (standard analysis)... AND the higher score is attributable
> to a specific protocol mechanism, not just longer output."

**FALSIFIED.** Arm B did not beat Arm A on either case. (Note: Arm B's outputs
were also substantially longer — case 1: ~640 vs ~1050 words core content,
case 2: ~520 vs ~950 — so length was never a confound in Arm B's favor; if
anything a naive length-correlates-with-thoroughness prior would have predicted
Arm B winning, which makes the actual result more, not less, informative.)

## Why — mechanism-level, not just "protocol underperformed"

Both graders independently converged on the SAME two specific mechanisms,
not a diffuse "worse writing":

**Case 1 mechanism — REPEAT-vs-REJECT threshold conservatism.** Arm B's own
claim_entropy/no-collapse-test reasoning correctly identified the calibration-
set overfit and the data-swap failure (arguably MORE rigorously than Arm A —
grader: "the underlying observations... are concrete"). But it landed on
**REPEAT** ("what died is narrow... rejecting outright would overstate..."),
while the real verdict is a hard **REJECT** ("do NOT retry this way"). The Anti-
Overfitting Gate's own discipline against premature rejection produced
under-rejection relative to the real expert here. Important asymmetry: the real
investigator's confidence for a hard REJECT was informed by "two external
reviews this session" not available to either arm in this pilot's raw package —
a genuine confound in how "PRE-verdict raw form" was operationalized, documented
below, not hidden.

**Case 2 mechanism — mandatory Steelman over-crediting a false argument.**
Doubt-Driven Development's Step 2 instructs "steelman the opposing view." Arm B
did: its Steelman explicitly affirmed the design's "bounded worst case" argument
as "real de-risking, not hand-waving" — which is EXACTLY the claim the real
red-team verdict calls FALSE (a non-blocking warning IS the entire control, not
a bonus layer). Arm A, with no obligation to steelman, rejected that same
framing directly and never conceded it. The grader scored this as Arm B's
single largest anti-pattern-avoidance loss (1/3 vs Arm A's 3/3).

Both mechanisms are **specific and actionable**, not a wholesale indictment:
(1) a discriminator is missing between "steelman a plausible counter-argument"
and "steelman a counter-argument that is actually factually false" — DDD's
Step 2 doesn't currently distinguish these; (2) the REPEAT/REJECT threshold in
Perelman's Promotion Rule may be miscalibrated toward false-REPEAT specifically
when the real-world comparator had outside corroboration the test setup didn't
grant either arm.

## Diamond/Silver scan (per decision.md template, independent of verdict)

💎 **Diamond** — the Steelman-over-crediting-a-false-argument finding is a
genuinely unexpected, transferable result: a mandatory red-team step (present
BECAUSE it's supposed to catch weak reasoning) instead laundered a false
security claim into an implicit endorsement, in a case a non-methodological
reviewer caught cleanly. Worth a Pearl Registry entry (below) independent of
this experiment's narrow REJECT verdict.
