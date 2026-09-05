# sci-code-audit — blind pilot, pre-registration

**Written before any results exist.** Per this repo's own EstimandOps rule
("estimand before data") and per today's user-requested pilot design: define
success BEFORE running, so nothing here gets adjusted after seeing outcomes.

## Object

Does applying `sci-code-audit`'s actual 10-layer protocol find more real,
verifiable code-trust issues than a strong free-form code review baseline,
on real code samples with independently-sourced, sealed ground truth,
without an unacceptable false-positive rate on clean code?

## Question type (EstimandOps L0)

**Predictive/comparative**, not causal in the deep sense -- this measures
whether the skill's structured protocol outperforms an unstructured
alternative on a fixed task set, not why. No DAG required.

## Protocol (mirrors `benchmarks/construct-measurement-gate/run-2026-08-30-blind-holdout.md`)

1. **Independent Case Curator** (`Agent(general-purpose)`, blind to the fact
   that `sci-code-audit` exists or is being tested) -- told only to build a
   set of real code review objects for "evaluating the quality of code-trust
   audits in general," sourced from real, verifiable GitHub history (actual
   commits that fixed a documented bug), not fabricated.
2. **Arm A -- Strong Baseline** (`Agent(general-purpose)`, given the raw code
   objects, asked for a rigorous free-form code review, no fixed template).
3. **Arm B -- Treatment** (`Agent(general-purpose)`, given the same objects
   plus `sci-code-audit`'s actual SKILL.md, told to apply it exactly).
4. **Blind Adjudication** (`Agent(general-purpose)`, given sealed ground
   truth + both arms' anonymized responses labeled "Response 1"/"Response 2",
   no indication of which is baseline/treatment).

## Population (case composition target)

6 real objects minimum:
- 4 objects with a REAL, documented bug matching `sci-code-audit`'s stated
  concern areas (silent fallback, missing invariant test, control/data
  provenance issue, undocumented reproducibility gap) -- sourced as an
  actual pre-fix commit state + its real fix commit as sealed ground truth.
- 2 clean objects (no such issue) -- to measure false-positive rate.

## Endpoint

Per object, per arm: did it correctly name the real issue (or correctly
report "no issue found" on clean objects)? Was the finding actionable
(concrete next step) or vague?

## Summary measures (all must hold simultaneously, per the construct-
measurement-gate precedent's own formal-pass-criteria structure)

1. Treatment finds >=2 real issues baseline misses, across the 4 buggy
   objects.
2. Specificity >= 0.80 on the 2 clean objects for BOTH arms (neither
   arm is allowed to cry wolf on clean code as the price of sensitivity).
3. No critical false positive: neither arm recommends a destructive/
   high-severity action on a clean object.
4. Actionability: treatment names a concrete discriminating next step in
   at least 4 of 6 cases.

**MCID:** if criterion 1 alone fails (treatment finds 0-1 issues baseline
misses), the pilot's headline claim ("the structured protocol helps") does
NOT hold, regardless of how the other 3 criteria land.

## ICE

Not applicable -- this is a one-shot structured comparison, not a
longitudinal or dropout-prone design.

## What this result will NOT mean

1. Does NOT establish `sci-code-audit` is better on all code, only on this
   6-object set with this shape of bug.
2. Does NOT establish WHY (mechanism) -- purely a comparative outcome
   measure, not a causal explanation.
3. Does NOT generalize to code radically unlike these 6 objects (e.g.
   frontend UI code, if the objects skew backend/data-pipeline).
4. A single pilot (n=6) is a first read, not a statistically powered trial --
   per this same project's own skeptic-triggers.md, a suspiciously clean
   sweep (6/6 either direction) should itself trigger a skeptic re-check
   before being trusted.

## Acknowledged limitation, stated up front (not discovered after the fact)

True format-blinding is not fully achievable: Arm B's structured 10-layer
output is visually distinguishable from Arm A's free-form prose, so the
adjudicator could plausibly infer which response used a template. Content-
blinding (not told which is which, scored on content not form) is real;
format-blinding is not -- same acknowledged gap as the construct-measurement-
gate precedent.
