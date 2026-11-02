# decision.md — 20261014-contract-router-architectures

## Verdict

- [ ] PROMOTE
- [x] REPEAT — the claim is **not supported at this sample size**: no architecture satisfies the frozen decision rules on sealed test data. The best model-based arm (`A3`) found 5 of the 15 true requests against 1 for the keyword baseline, but that is net +4 (rule needs +5), p = 0.11 one-sided, and it emits 18 false hints per 1 000 prompts (cap 10). The test set is now opened; the next test needs new data.
- [ ] REJECT
- [ ] ARCHIVE

Production was **not changed**. Nothing outside this experiment folder and a local scratch directory was touched.

## What was done

- Complete labels for all 10 147 prompts (earlier estimates replaced by counts): first pass by blind subagents, an audit pass on 864 prompts (all 64 first-pass positives plus 800 random negatives, kappa 0.85, 80 % of positives confirmed, 0.5 % of negatives called positive), a third labeler for the 19 disputed prompts. **67 true requests** in the corpus (0.66 %); 52 in development sessions, 15 in the sealed test sessions.
- Development on 64 sessions only; configuration frozen by hash (`frozen.sha256`) before the 23 test sessions (3 090 prompts) were opened; the evaluation script refuses to run if any frozen file changed.
- Six architectures. `A0` keyword router `v1.1`. `A1` local multilingual embeddings plus a learned gate. `A2` a local language model (`gemma4:e4b`, chosen on development data among three) reads the prompt and all 41 cards. `A3` the same model sees only A1's five best candidates. `A4` is A3 behind the A1 gate. `A5` is A2 behind the A1 gate (added after seeing development results; exploratory, counted in the multiplicity).

## Sealed test result (strict: the hinted card equals the labeled card)

| arm | hints | true | false | precision [95 % Wilson] | recall [95 % Wilson] | F1 | false per 1 000 | vs A0: arm-only / A0-only, one-sided p |
|---|---|---|---|---|---|---|---|---|
| A0 keyword | 4 | 1 | 3 | 25 % [5, 70] | 6.7 % [1, 30] | 0.105 | 1.0 | — |
| A1 embeddings + gate | 37 | 2 | 35 | 5.4 % [1.5, 17.7] | 13.3 % [3.7, 37.9] | 0.077 | 11.3 | 2 / 1, p = 0.50 |
| A2 model, full catalogue | 72 | 4 | 68 | 5.6 % [2.2, 13.4] | 26.7 % [10.9, 52.0] | 0.092 | 22.0 | 3 / 0, p = 0.125 |
| A3 model, 5 candidates | 61 | 5 | 56 | 8.2 % [3.6, 17.8] | 33.3 % [15.2, 58.3] | 0.132 | 18.1 | 5 / 1, p = 0.109 |
| A4 A3 behind gate | 19 | 2 | 17 | 10.5 % [2.9, 31.4] | 13.3 % [3.7, 37.9] | 0.118 | 5.5 | 2 / 1, p = 0.50 |
| A5 A2 behind gate | 35 | 2 | 33 | 5.7 % [1.6, 18.6] | 13.3 % [3.7, 37.9] | 0.080 | 10.7 | 1 / 0, p = 0.50 |

Frozen rules: (1) at least 5 more true hits than A0 and one-sided exact McNemar p < 0.05; (2) precision not below A0's; (3) at most 10 false hints per 1 000 prompts. **No arm passes rule 1 or rule 2; only A4 passes rule 3.** Holm-adjusted p across the five arms: A2 and A3 0.55, the others 1.0. Result: **no arm supports improvement over A0.**

This is "not detected", not "no effect". With 15 true requests the design detects an improvement only if the arm finds about 5 more of them than the baseline; smaller real gains would not show. The model arms point in the right direction (A3 net +4, A2 net +3) and could be real.

## Development estimates did not survive (recall, precision, false per 1 000)

| arm | development | sealed test |
|---|---|---|
| A2 | 44 %, 18 %, 14.8 | 27 %, 5.6 %, 22.0 |
| A3 | 46 %, 15 %, 19.1 | 33 %, 8.2 %, 18.1 |
| A4 | 35 %, 28 %, 6.6 | 13 %, 10.5 %, 5.5 |
| A5 | 33 %, 85 %, 0.4 | 13 %, 5.7 %, 10.7 |
| A1 | 17 %, 8.9 %, 13.0 | 13 %, 5.4 %, 11.3 |

The gated arms' development precision was produced by a handful of heavily weighted negatives crossing a threshold; A5's 85 % on development was a sampling artefact, as flagged at the time. The sealed test is what the earlier-sample numbers could not give.

## Robustness: long and conversational prompts

True requests by length: up to 200 characters 8, up to 600 5, up to 1 500 1, over 1 500 1. Conversational asks (up to 200): A0 1 of 8, A2 3 of 8, A3 3 of 8, A1 0, A4 0, A5 1. The single true request over 1 500 characters was found by nobody. False hints concentrate in short prompts for the model arms (A2: 38 of 68 on prompts up to 200 characters) and in long prompts for the gate arms. With 8 and 1 true requests per bucket, no length claim has statistical weight.

## Where the model arms' false hints are

Of A2's 68 false hints, 39 sit on prompts the labelers marked as genuine requests for work that no card fits (A3: 36 of 56), 11 on pasted reports, 9 on questions, 8 on short status messages. The model does what the card catalogue invites: it picks the nearest card for any work request. Part of that is a disagreement about the boundary of a card, not noise, but the strict definition counts it as false and a hint that names the wrong task is not harmless. Wrong card on a true request: A0 0, A1 2, A2 3, A3 0.

## Cost and latency (this machine, models already loaded)

| arm | per-prompt time | extra tokens per prompt | deployable as |
|---|---|---|---|
| A0 | 0.1 ms in process; 84 ms end to end as a hook (interpreter start) | 0 | hook-resident |
| A1 | embedding 18 ms median, 34 ms p95 warm; about 2 s cold per fresh process | 0 | needs a resident service |
| A2 | 673 ms median, 762 ms p95; 35.5 min for 3 090 prompts | 2 701 prompt, 7 output (local model, no paid tokens) | needs a resident service |
| A3 | 802 ms median, 1 203 ms p95; 43.9 min | 550 prompt, 7 output | needs a resident service |
| A4 | model on 12.4 % of prompts; about 121 ms average | as A3 on that share | needs a resident service |
| A5 | model on 12.4 % of prompts; about 104 ms average | as A2 on that share | needs a resident service |

A hook starts a fresh process for every prompt, so every model-based arm needs a resident local service to meet the cost class of rule 4. None is hook-resident. A3 is slower than A2 although its prompt is five times shorter, because a different candidate list per prompt defeats the model's prompt-prefix cache; the constant full catalogue of A2 is cached.

## Label sensitivity

Of the 15 true requests in the test, 9 were confirmed by the first two labelers without arbitration, 6 went through the third labeler, who sided with the positive reading in 18 of 19 disputes overall, so the arbiter is more lenient than the first two. On the 9 unanimous requests: A0 1, A2 3, A3 3. The ordering of the arms does not change.

## Reconciliation of the earlier figures

| quantity | earlier statement | exact value now |
|---|---|---|
| true requests in the corpus | 92, then 111 (estimated from 3 positives in 400) | **67** (complete labels, three labelers on disputes) |
| hint rate of v0 reconstructed | 6.7 % vs 6.5 % | 6.5 % reconstructed, 6.7 % first measurement; consistent, different card sets |
| keyword hints useful | "one in four" (manual), then 2 of 25 | 2 of 25 on all labeled prompts; on the sealed test sessions 1 of 4 |
| recall of v1 | about 2 % (of an estimated denominator) | 2 of 67 = 3.0 % on the whole corpus |

The earlier figures built on a sampled denominator are superseded by counts. The estimate 111 was too high because the sample of 400 held 3 positives, all in the shortest stratum; complete labeling found 36 true requests among the 7 979 prompts that had not been labeled before (after audit and arbitration), where the earlier estimate for that population was 82.

## What the result does NOT mean

1. It does not mean the model-based routers are worse than keywords: they find three to five times more true requests; they are not shown to be reliably better and they pay with false hints.
2. It does not show that a hint, however accurate, helps: there are no outcome data.
3. The test set is spent: any new tuning must be evaluated on new prompts, not on these 23 sessions.
4. One maintainer, Russian prompts, one period; labels are model-labeler agreement.

## Next verifiable experiment

The one decision-relevant question left is whether the false hints can be cut without losing the recall the model arms show. Proposed, in order:

1. **Two-stage verification** developed on the development sessions only: the model proposes a card, a second call asks whether the message itself asks for that work now, and a hint is emitted only on "yes". Success rule frozen beforehand: at least 5 net true hits over A0 and at most 10 false per 1 000 on a **new sealed set**.
2. **New sealed set**: prompts after 2026-10-14. At 0.66 % true requests, 50 true requests need about 7 600 prompts, roughly three quarters of this corpus; labeling them costs the same pipeline as here. Until then the test result above stands as the evidence.
3. In parallel and independent of data volume: the owner's outcome marks on the first 40 hints of the shipped router (`experiments/20261014-contract-router-precision`, forward holdout; cancelled 2026-10-14 when the hook was removed, see the practical-value decision).

## Surgery log / forbidden claims

No component was replaced. Forbidden claims after this experiment: "a language-model router is better than the keyword router" (net +4, p = 0.11); "the gate fixes the false hints" (it halves them and loses the recall, p = 0.5); "development figures predict test figures" (they overstated recall by 1.4 to 2.5 times and precision by 2 to 15 times); "the router can run as a hook with a model" (cost class: needs a resident service).
