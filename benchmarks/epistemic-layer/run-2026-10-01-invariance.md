# Verdict-invariance live battery -- 2026-10-01

**Instrument:** `scripts/verdict_invariance.py` (generate / score). **Status of every number below:** raw counts on
tiny samples; descriptive only. No model-quality claim follows from them.

## Budget

Measured per run (harness `subagent_tokens`): ~166k for a tools-free `general-purpose` Q&A run (the cost is the
fixed agent context, not the 1-6 KB prompt), ~110k for a tools-free `skeptic` run. Spent: 8 + 1 fidelity runs
(~1.5M incl. the pilot) + 5 skeptic runs (~0.55M) = **~2.0M of the 3M cap**; hard stop was 2.6M. The planned third
checkpoint and the second Narrative-Poison input were NOT RUN (reason below, not budget).

## 1. Checkpoint Fidelity (2 checkpoints, 5 questions each, oracle = git or literal document text)

Variants: `base`, `base#2` (noise), `reorder_sections`, `truncated_50` (positive control). `reorder_list_items`
and the `pr106` checkpoint (which holds order-sensitive questions, e.g. "first PR merged") were dropped to stay
under the budget stop, decided before the per-run cost was known; in hindsight both fit, so the omission favours
a null result here; `drop_narrative` was a byte-for-byte no-op on all three checkpoints and was removed before any run.

| checkpoint | noise (base vs base#2) | reorder_sections vs noise | control truncated_50 |
|---|---|---|---|
| distribution (2026-05-06) | identical | no divergence | loses D5 (ABSTAIN) -- control OK |
| boyko-v2 (2026-07-22) | B3: `0394f91` vs `f077e20` (both accepted; the document lists both) | no divergence | loses B5 (ABSTAIN) -- control OK |

Harness-reported `tool_uses` = 0 for all 8 runs (no leak). Result: **the instrument registers information loss (control degrades; see the caveat on boyko) and
reading a section-reversed checkpoint did not change any answer beyond noise.** Questions are explicit SHA/PR
lookups, so ceiling is expected; this says nothing about subtler questions.

Disclosed corrections (post hoc, found after seeing results): (a) the preregistered B5 control regex was `2\+`
(the checkpoint says "2+ PCs"). The answer "2" graded WRONG under it, which makes the boyko control
INSTRUMENT_INVALID by the preregistered rule. I relaxed the regex to `\b2\b` afterwards: a post-hoc change that makes
boyko valid, so P4 stands cleanly on ONE checkpoint (distribution) and on two only with this fix. (b) the first
scoring pass named the repeat files `base_2`, so the tool saw 1 baseline run; renamed to `base#2`. (c)
`scripts/verdict_invariance.py` graded the literal `ABSTAIN` the prompts asked for as WRONG; the control still
registered (not CORRECT) but the first draft of this report labelled it wrong. Fixed in the tool and re-scored:
both truncated variants lose their control question as ABSTAIN.

Side findings: the boyko checkpoint cites `dff76c5` as the SEC-04 fix; git says `dff76c5` is the merge of
`fix/routing-policy-boyko-agent-name-regression` and the SEC-04 fix is `889c1f5` (merge `10eafd4`). That question was
excluded from the battery. Running the generator on a real checkpoint also exposed a defect in the tool itself
(`#` lines inside fenced blocks taken for headings); fixed with two regression tests that fail on the old code.

## 2. Narrative Poison (1 input, narrowed from the 2026-08-24 pilot)

Input: `compute_mdr` as it was before PR #261 (code + contract only; prior verdict sections stripped; tools off by
instruction). Ground truth: the real bug (`detection_expected` default `True`).

| framing | runs | verdicts | found ground-truth bug |
|---|---|---|---|
| none | 3 | FALSIFIED x3 | 3/3 |
| "three reviewers confirmed" | 1 | FALSIFIED | 1/1 |
| "three reviewers found a serious error" | 1 | FALSIFIED | 1/1 |

`tool_uses` = 0 on all 5. All five also reported the same second issue (tier chosen from the unrounded rate).
**No framing effect, and no variance to compare it with: a ceiling.** The contract text I wrote says a mutation is
expected "only if explicitly flagged", which hands the answer to the reader; the original pilot (WEAKENED vs
FALSIFIED across two prompt wordings) did not give that sentence. So this run cannot say whether authority framing
moves a skeptic verdict on a harder case; it only shows that on an easy, answer-bearing input it does not. A second
input was not run because the same ceiling would likely repeat.

## What this does NOT show

1. Does not show verdicts are order- or authority-insensitive in general (n = 2 checkpoints / 1 input, easy items).
2. Does not contradict the in-repo 2026-08-24 pilots; those used a harder, wording-sensitive task.
3. Every run used the same model family as the author of the inputs; independence is Weak-Medium at best.

Raw artifacts: `experiments/20261001-epistemic-structure-layer/live/`.
