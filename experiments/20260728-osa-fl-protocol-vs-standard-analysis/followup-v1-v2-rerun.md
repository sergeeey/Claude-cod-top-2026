# followup-v1-v2-rerun.md — 20260728-osa-fl-protocol-vs-standard-analysis

Executed overnight (2026-07-28, autonomous continuation, user-authorized: "все по
очереди го действуй автономно"), following up on the two Relaxation Map rows in
`decision.md` and the two `pearl_registry/INDEX.md` entries this pilot produced.
Minimal Relaxation Rule applied: one changed assumption per re-run, same raw
material, same 3-methodology-file instruction, same blind-grading rubric as the
original run.

## V1 — Case 2 (llm-judge), DDD Step-2 Steelman soundness discriminator

**Change:** Arm B's prompt added one instruction — before crediting any
counter-argument found while steelmanning (DDD Step 2), perform an explicit
soundness check first; if the counter-argument does not survive it, name it as
unsound rather than treat it as a mitigating factor.

**Result: CONFIRMED, strongly.**

The revised Arm B' output performed the soundness check exactly as instructed
on the design's "bounded worst case" argument, found it unsound on 3 grounds
(wrong reference baseline, non-adversarial framing, understated causal role of
the warning), and explicitly refused to credit it — matching the real red-team
verdict's own core point (the warning is the *entire* control in a non-blocking
hook) almost exactly.

Blind-graded score (same rubric, fresh grader, same gold verdict):

| | Root-cause | Anti-pattern | Falsifiability | Actionability | Total |
|---|---|---|---|---|---|
| Arm A (unchanged) | 2/3 | 2/3 | 2/3 | 1/3 | 7/12 |
| Arm B' (V1 applied) | 3/3 | 3/3 | 3/3 | 2/3 | **11/12** |

Arm B' now beats Arm A by 4 points on this case (previously Arm B lost, 9 vs
7 in the original run — see caveat on grader variance below). The grader's own
words: the soundness-check step "structurally forces the trap into the open...
almost verbatim" matches the anti-pattern rubric.

**Pearl Registry status → `confirmed`.**

## V2 — Case 1 (regex-composition), explicit REPEAT/REJECT threshold question

**Change:** Arm B's prompt added one instruction — before the final verdict,
explicitly answer "would THIS evidence ALONE, with no outside corroboration,
justify a hard REJECT?"

**Result: falsibied as originally predicted, but with an important, more
specific finding underneath it — not a clean miss.**

The revised Arm B' explicitly answered the added question with a well-reasoned
**"No"** (no comparator exists; n=8 is underpowered; the calibration/held-out
gap indicts the *process*, not necessarily the *mechanism*; no per-signal error
attribution exists) and, following that reasoning honestly, stayed at
**REPEAT** — the verdict did NOT shift toward REJECT as the pearl's falsifiable
prediction stated it would.

Blind-graded score:

| | Root-cause | Anti-pattern | Falsifiability | Actionability | Total |
|---|---|---|---|---|---|
| Arm A (unchanged) | 2/3 | 2/3 | 3/3 | 1/3 | 8/12 |
| Arm B' (V2 applied) | 1/3 | 1/3 | 3/3 | 1/3 | 6/12 |

Score moved 5→6 (marginal improvement over the original run) but Arm B' still
loses to Arm A, and by the grader's own reading, WORSE on anti-pattern
avoidance specifically: the explicit reasoning "talks itself into REPEAT...
re-opening the question of whether regex composition might still work — which
is the specific anti-pattern... the gold verdict was written to close off."

**Why this isn't simply "the fix failed":** the real investigator's confidence
for a hard REJECT was explicitly informed by "two external reviews this
session" (stated in the original null_result) — information genuinely absent
from the raw package given to either arm in this pilot by design (see
`estimand.md`'s Exchangeability row, which flagged this exact risk in advance:
"at risk — requires blind grading to hold"). Arm B' reasoning through "would
this evidence ALONE justify REJECT" honestly concluded "not quite" — which may
be the epistemically correct answer given the actual information available,
not a methodology defect. The V2 fix cannot manufacture information that was
deliberately withheld from the raw package. This is a genuine limitation of
this pilot's *design* for Case 1 specifically (an information-asymmetry
confound the estimand pre-registered as a risk and this re-run makes concrete),
not evidence that the "ask the threshold question" fix itself is wrong in
general.

**Pearl Registry status → `refuted-as-stated, confound identified`.**

## Grader-variance caveat (new, honest limitation found during this re-run)

Arm A's UNCHANGED original text was blind-graded by a fresh grader instance in
each of these two follow-up runs (once per case, since each case needed its own
grading call). Case 2's Arm A scored **9/12** in the original morning run and
**7/12** in this evening's re-grading of the identical text — a 2-point swing
on byte-identical content from a different grader instance. This is real
scoring noise, not a data-entry error (both grader prompts were checked to
carry the identical Arm A text verbatim before this note was written). This
means none of this pilot's specific point totals should be read as precise
measurements — the qualitative direction of a result (which output is clearly
ahead, and roughly by how much) is more trustworthy than any single number.
Consistent with `falsification-ladder.md`'s Independent Verification Strength
Ladder: a single grader pass, even blind, is Weak-Medium independence — this
is exactly the predicted failure mode of that tier, now observed directly
rather than just cited from the rules file.

## Net effect on the pilot's overall conclusion

Does not overturn the original finding (`null_results/20260728-...md`, REJECT
of the pilot's own falsifiable statement) — that verdict was about the
UNMODIFIED protocol, which is still accurately described as losing to plain
analysis on both cases as tested. What this follow-up adds: one of the two
identified mechanisms (Steelman soundness) is a real, cheap, high-leverage fix
— worth carrying into `rules/doubt-driven-development.md` Step 2 as an actual
rule change in a future session. The other (REPEAT/REJECT threshold question)
does not fix what it was aimed at, but running it anyway surfaced a sharper,
more specific finding (the information-asymmetry confound is real and
case-specific, not evenly distributed across both pilot cases) — itself a
legitimate research output, consistent with this repo's own principle that a
falsified fix is not a wasted step when it narrows the option space
(Anti-Overfitting Gate, Kill Analysis discipline).

## Not done in this follow-up (deliberately, scope discipline)

- Did NOT edit `rules/doubt-driven-development.md` to actually add the Steelman
  soundness-check step as a permanent rule change — that's a real methodology
  edit affecting every future DDD invocation across this repo and beyond, and
  should get the user's explicit review rather than being silently rolled out
  overnight on the strength of a single confirmed re-run (n=1 confirmation is
  suggestive, not sufficient for a permanent rule change).
- Did NOT attempt a third re-run to disentangle the information-asymmetry
  confound from Case 1 specifically (e.g., giving Arm B' the same external
  corroboration the real investigator had) — a legitimate next step, but a
  new, separate design decision, not a mechanical continuation of V1/V2.
