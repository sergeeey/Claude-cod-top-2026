# decision.md — 20261014-contract-router-precision

## Verdict

- [ ] PROMOTE
- [x] REPEAT — clause 1 (false hints halved) is met. Clause 2 (recall within 1 pp) cannot be decided at 29 found true requests and fails in the rules-only comparison. The owner's joint goal is reachable only at a useless precision (below). The remaining open question, whether the adjusted rules (`v1.1`) are useful, is decided by a different, pre-registered criterion on future hints (section "Forward holdout"), not by more analysis of this corpus. [Forward holdout cancelled 2026-10-14: see the Forward holdout section.]
- [ ] REJECT
- [ ] ARCHIVE

## Per clause (no composite)

| Clause (frozen in `claim.md`) | Result |
|---|---|
| 1. False hints of `v1` at most half of `v0` | **MET.** 656 → 23 false hints (−96.5 %). Counts are exact **given the labels**; the second labeler found two true requests the first missed, both long inputs, which are where `v0`'s false hints concentrate, so the long-input false hints may be slightly overstated. The margin is far larger than that. Rules-only on the same 41 cards: 1 757 → 23 (−98.7 %). |
| 2. Recall of true requests not lower by more than 1 pp | **Pre-registered comparison: INCONCLUSIVE.** Among the 29 true requests in the candidate set the recall difference is −6.9 pp (95 % bootstrap [−20.7, +6.9]); detectable difference about 19 pp. Over the whole corpus the estimated recall is 3.6 % for `v0` and 1.8 % for `v1` (−1.8 pp, both inheriting the same uncertainty about how many true requests exist). **Rules-only comparison on 41 cards (exploratory, not pre-registered): NOT MET.** `v1` finds 2 of the true requests that the first-version rules find 11 of: 9 lost, 0 gained, exact McNemar p = 0.004. Unchanged with confident labels only (5 → 2). |
| 3. Both together, as one criterion | **Reachable only at useless precision, and not reachable against the stronger reference.** Grid of 576 rule configurations (stems 1 to 4; rarity-score threshold none, 2, 3, 4, 5, 6; request-verb gate on or off; long-input rule none, 600, 1 500; long input by phrases only or not; phrase word-boundary on or off). Against the **pre-registered** `v0` (finds 4 of the 12 true requests that belong to the original 10 cards, 656 false hints): 24 configurations keep those 4 with at most 328 false hints; the best has 308 (−53 %) on 317 hints, 9 of them true (4 on original-card requests, 5 on later cards), i.e. precision 2.8 %. Against the rules-only reference on 41 cards (11 found, 1 757 false): **none** keeps all 11 and halves the false hints; the smallest false-hint count at full recall is 1 235 (70.3 %). This is a statement about this corpus and this family, not a theorem. |

Production rules were **not changed by the experiment**. A candidate found on TRAIN sessions did not beat `v1` on TEST sessions (below). The later `v1.1` adjustment is described in the addendum.

## Data (aggregates only)

- Corpus: 10 147 typed prompts, 87 sessions. Labeled: 2 168 (all 1 768 prompts that any version can hint, plus 400 random others). Labels by blind subagent labelers who never saw router output; 200 prompts labeled twice.
- True requests (a card fits the main ask): 29 among the 1 768 candidates, 3 among the 400 random others. **All three sit in the shortest stratum** (up to 200 characters: 3 of 250 sampled, 0 of 150 in the other three strata). Stratified estimate outside the candidates: **82** (stratum sizes 6 846, 839, 262, 432). An earlier draft of this file used the unweighted rate (63) instead of the stratified one; the stratified figure is the correct one for a stratified sample. Estimated corpus total: **about 111, interval 29 to 221** (stratified parametric bootstrap; the lower end is the number already found), roughly 1.1 % of prompts.
- Label quality: of the 29 positives in the candidate set, 9 carry the labeler's top confidence, 14 at least medium. Agreement between the two labelers on "request vs none": kappa 0.75 on 200 prompts, but only 3 positives are shared (two more were found by the second labeler only, both long inputs), so the kappa is imprecise. The card agreed on all 3.

## Before and after (strict: the hinted card equals the labeled card)

| | hints | TP | FP | precision (95 % Wilson) | recall of ~111 (interval from the positive estimate) | false-positive rate |
|---|---|---|---|---|---|---|
| `v0` reconstructed (10 cards) | 660 | 4 | 656 | 0.6 % [0.2, 1.5] | 3.6 % [1.8, 13.8] | 6.5 % |
| `v0` rules on 41 cards | 1 768 | 11 | 1 757 | 0.6 % [0.3, 1.1] | 9.9 % [5.0, 37.9] | 17.5 % |
| `v1` (current) | 25 | 2 | 23 | **8.0 % [2.2, 25.0]** | **1.8 % [0.9, 6.9]** | 0.23 % |

Lenient (the prompt was labeled with any card): `v0` 15 of 660, `v1` 2 of 25. The earlier manual reading ("about one in four hints is useful") was wrong; the measured figure is 2 of 25.

Error matrix of `v1` over the corpus (stratified estimate): TP 2, FP 23, FN about 109, TN about 10 013.

## Where the false hints were

By length bucket (prompts / true requests found among the labeled sets / `v0` hints / `v0` false / `v1` hints / `v1` false):

| bucket | prompts | true requests | v0 hints | v0 FP | v1 hints | v1 FP |
|---|---|---|---|---|---|---|
| up to 200 | 6 942 | 9 | 14 | 12 | 4 | 3 |
| up to 600 | 1 042 | 9 | 51 | 50 | 12 | 11 |
| up to 1 500 | 477 | 7 | 77 | 76 | 2 | 2 |
| over 1 500 | 1 686 | 7 | 518 | 518 | 7 | 7 |

`v0` false hints by labeled kind: pasted reports and assistant text 289, real requests for a different task that merely mention a card topic 197, questions 82, chat 48, status, role prompts and other 40. 79 % came from prompts over 1 500 characters. `v1` residual false hints: requests for another task 11, questions 4, pasted reports 4, chat 3, status 1.

Contribution of each rule (cumulative, over the 1 768 candidates, strict): version-0 rules on 41 cards 1 757 false; request-verb gate 1 063; long input judged by phrases only 153; three stems 23. The phrase word-boundary rule and the rarity score threshold changed nothing on this corpus (the score threshold is redundant here).

## Why keyword rules cannot reach the owner's goal

- The loosest possible stem rule (two stems, no gates, all cards) finds 29 of about 111 true requests and emits 1 768 hints: **precision ceiling 1.6 %, recall ceiling about 26 % (13 % to 100 %; the upper end shows how little the 3 outside positives pin down)**. The point estimate says most true requests share fewer than two words with any card; the interval does not exclude that the share is smaller.
- 16 of the 29 true requests in the candidate set are not hit by any of the 576 configurations.
- All three true requests found outside the candidates are short (up to 200 characters). Short, free-speech requests are where the missed recall is.
- Detecting a 1 pp difference in recall with the observed discordance would need roughly 4 000 to 11 000 true requests, i.e. 0.4 to 1.0 million prompts at the observed rate. The owner's criterion cannot be verified on any realistic corpus; a null result on it is uninformative by construction.

## Optimization attempt (rule 4 of the claim)

Selection rule fixed before looking at TEST: maximise true hits on TRAIN sessions subject to no more false hints than `v1`. Selected: four stems, request-verb gate, long input still allowed to match by stems (the `v1` rule "long input accepts only phrases" dropped). TRAIN: 5 true hits, 13 false (`v1`: 1 and 14). **TEST: 1 true hit, 11 false** against `v1`'s 1 and 9. Selecting in the reverse direction picked a different configuration. With 24 TRAIN and 5 TEST positives the data cannot separate the two rule sets, so nothing was adopted.

## Forward holdout (frozen 2026-10-14; CANCELLED 2026-10-14, the hook was removed, see the practical-value decision)

The pre-registered recall clause cannot be decided on any realistic corpus, so a repeat with the same predicate would end `INCONCLUSIVE` again. The question that can still be decided cheaply is whether the hints that do fire are useful.

- **Object:** the router as of 2026-10-14 (`v1.1`, the working tree at the commit that adds this experiment).
- **Instrument:** the first 40 hints it emits after that date, each marked `useful` or `not useful` by the owner at the time. This is a different instrument from the blind labelers (the owner's judgement, which the limits section calls authoritative) and it needs the outcome ledger of the contract skill, which is not built yet.
- **Rule:** the claim "useful rate above the 8 % measured for `v1`" is supported if at least **7 of 40** are marked useful. False-alarm probability at a true rate of 8 %: 0.038; power at a true rate of 25 %: 0.90; at 20 %: 0.71. Fewer than 7 is reported as not supported, not as a rate.
- **Recall is not claimed** by this check and is not part of its success criterion.
- **Time:** at the `v1.1` hint rate (15 hints in 10 147 prompts) 40 hints take about 27 000 prompts, roughly 2.7 times this corpus.

## Surgery log / forbidden claims

No component was replaced. Forbidden claims after this experiment: "the router selects tools automatically" (recall about 2 %); "the router is mostly right when it speaks" (8 %, wide interval); "the false-hint rate fell by X without cost" (it fell by 96.5 % and the recall of found true requests fell with it); "the joint goal is impossible" (it is reachable at precision 2.8 % against the pre-registered `v0`).

## Known limits

1. Labels are model-labeler agreement, not the owner's judgement. Where they differ, the owner is right.
2. `v1` was tuned on this same corpus: its figures are optimistic. No independent data exists. The forward holdout above is the only real test of the adjusted rules. **Status (2026-10-14): cancelled.** The shipped hook was removed from the branch after the practical-value experiment (verdict REMOVE, see `../20261014-contract-practical-value/decision.md`), so no new hints will be emitted to mark. The v1.1 rules remain unverified on independent data.
3. The reconstructed `v0` uses today's trigger words, not the original ones; its hit rate (6.50 %) is close to the first measurement (6.7 %) but it is an approximation. The pre-registered `v0`-versus-`v1` recall comparison is confounded by the card set (positives labeled with one of the 31 later cards cannot be hit by `v0`), which is why the rules-only comparison was added after the fact and is labeled exploratory.
4. The estimate of true requests outside the candidate set rests on 3 positives in 400, all in one stratum; its interval is wide, and every recall figure inherits it.
5. The second labeler found more long-input positives than the first. If that pattern is general, true requests among long inputs are undercounted and `v0`'s long-input false hints are overstated.
6. Single maintainer, Russian prompts, one period.

## What this changes in the project

- `SKILL.md` states the measured precision and recall in place of the earlier estimate.
- Regression tests pin the false-hint classes found here (`tests/test_contracts_fixes.py`).
- Recommendation to the owner, not applied: treat the automatic hint as a near-silent safety net. A better route to proactive tool choice is the model reading the card catalogue and judging the task itself, because short free-speech requests, where most of the missed recall sits, share too few words with any card.

## Addendum (post hoc, after the experiment): rules changed to `v1.1`

Two review findings and one regression test led to a change AFTER the figures above were fixed. The change was not fitted to maximise a metric; the labels were used only to check that no found true request is lost. It is still contaminated: the labeler's `kind` field and the error classes of this corpus were read before the change, and the labels were read afterwards.

1. A topic phrase (for example "p-value", "circuit breaker") no longer raises a hint on its own: every hint needs at least one request verb in the judged text. Rationale: phrases are names of topics, not requests (independent review finding; synthetic regression test).
2. Words that are mostly nouns in this user's mixed RU/EN text were removed from the request-verb list: аудит, audit, test, run, build, plan, profile, benchmark, design, review, check, and later `fix` and `measure`.

Result on the same labels (`v1` frozen: 25 hints, 2 true, 23 false): **`v1.1`: 15 hints, 2 true, 13 false** (precision 13 %, Wilson 95 % [3.7, 37.9] %), no hint outside the labeled candidate set. The two true hits are kept; false hints fell a further 43 %. A TRAIN/TEST split was not run for `v1.1` because it has only two true hits; 2 versus 2 says nothing about recall on the other 100 or so true requests. It stays a hypothesis; its forward holdout was cancelled on 2026-10-14 when the hook was removed.
