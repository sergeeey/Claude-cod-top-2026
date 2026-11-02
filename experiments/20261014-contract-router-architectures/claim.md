# claim.md — 20261014-contract-router-architectures

Written 2026-10-14 BEFORE the remaining 7 979 prompts were labeled, before any architecture other than the keyword baseline existed, and before any architecture was run on test data. Follows `experiments/20261014-contract-router-precision` (REPEAT): keyword routing reached precision 8 % and recall about 2 %; most true requests are short, free-speech asks that share no word with a card.

## Zero-Signal Gate

| Field | Value |
|-------|-------|
| **Entity** | the contract router's choice of card for a typed prompt, in four architectures |
| **Falsifiable predicate** | at least one architecture finds clearly more of the true requests than the keyword baseline `A0` on sealed test prompts, without more than a bounded rate of false hints, and at a cost the hook can bear |
| **Measurable outcome** | true hits, false hits, precision, recall, F1 against complete blind labels; per-prompt latency and extra tokens; the rules below decide |

## L0: Question Type

- [ ] Descriptive
- [x] Predictive — how well each architecture generalises to prompts and sessions it was not built on
- [ ] Causal — no claim about whether a hint improves any user outcome

## Natural Language Statement

> We estimate precision, recall, F1, false hints per 1 000 prompts, latency and token cost of four contract-routing architectures for the typed prompts of 23 sealed test sessions, comparing each against the keyword baseline `A0` on identical complete blind labels, with all thresholds and prompts frozen on development sessions only.

## Architectures (frozen definitions)

- **A0 — keyword baseline:** the router in the working tree at the commit of this experiment (`v1.1`), unchanged.
- **A1 — embedding retrieval with a learned gate:** a local multilingual embedding model (`paraphrase-multilingual-MiniLM-L12-v2` or `Qwen3-Embedding-0.6B`, whichever is chosen on development data) embeds the prompt; similarity to each card's text and to development true requests gives a ranked card list; a small logistic gate over similarity scores and structural features (length, newlines, markdown, leading `@`, request-verb presence, share of Latin text) decides "speak or stay silent". Trained on development sessions only.
- **A2 — local language-model router:** a local model through `ollama` (`qwen3:8b` unless development shows a better one among `qwen2.5:14b`, `gemma4:e4b`) receives the prompt and the full 41-card catalogue and answers one card id or `NONE`. No training. Prompt template and decoding settings frozen on development data.
- **A3 — hybrid shortlist + judge:** A1's top-5 cards (no gate) are given to the same local model as the only options plus `NONE`.
- **A4 — gated hybrid (only if A1's gate is usable):** A3 is called only for prompts the A1 gate passes; the rest stay silent. Cost is the cost of A1 plus the gated share of A3.

The labelers are Claude-family subagents; A1, A2, A3 and A4 use non-Claude local models, which removes the most direct circularity between router and ground truth. It does not remove it entirely: the card catalogue and its wording are shared.

## Data and leakage controls (frozen)

- **Corpus:** the 10 147 typed prompts of 87 local sessions as of 2026-10-14 (same filter as the earlier experiment).
- **Complete labels:** the 7 979 prompts not yet labeled are labeled now with the same rubric and blind labelers as before, so that the full corpus has labels and no recall estimate rests on a sample. Every prompt labeled positive by one labeler is checked by a second and, on disagreement, by a third labeler; the positive truth is the majority. A random 300 negatives get a second labeling to estimate missed positives.
- **Split:** sessions with `sha1("arch-v2" + session id) mod 10 >= 7` are **TEST** (23 sessions, 3 090 prompts); the other 64 sessions (7 057 prompts) are **DEV**. Development code can load DEV only; TEST is read by one script (`sealed_eval.py`) that runs once, after the configuration is hashed and the hash written to `frozen.sha256` in this folder.
- **Known contamination, stated now:** the maintainer's earlier work read samples of error classes from all sessions, and `A0` was adjusted after that reading. That biases AGAINST the new architectures (the baseline has seen the test sessions; the new arms have not).
- **Never done:** tuning any threshold, prompt wording or model choice on TEST; looking at TEST texts or labels before the freeze.

## Metrics (frozen)

Strict hit = the chosen card equals the labeled card. Precision = true hits / hints. Recall = true hits / true requests (exact, complete labels). F1 as usual. Also false hints per 1 000 prompts, results per length bucket (up to 200, up to 600, up to 1 500, over 1 500) and for conversational requests (labeled `request` or `chat` in the first 200 characters, free of pasted material). Latency = wall-clock per prompt on this machine, median and 95th percentile, model already loaded; tokens = prompt tokens plus output tokens per prompt for model arms.

## Detectability, stated before the labels are counted

`n` = number of true requests in TEST (unknown until labeling; about 33 expected from the earlier estimate of 111 over 10 147 prompts). `baseline_or_sigma` = recall of `A0`, about 2 %. `alpha` 0.05 one-sided (the claim is directional), `power` 0.8. For a paired comparison the arm must find at least 5 more true requests than `A0` for the exact McNemar test to reach p < 0.05 when `A0` finds none of them. `MDE` therefore is about 5 true requests, roughly 15 percentage points of recall at n = 33. `MCID`: the owner's goal is a router that finds a useful share of requests, set here at 5 additional true hits and not less. A smaller difference is reported as not detected, never as no effect.

## Decision rules (frozen)

An architecture **supports improvement over A0** only if all four hold on TEST:

1. It finds at least 5 more true requests than `A0` and the exact one-sided McNemar test against `A0` gives p < 0.05.
2. Its precision is at least that of `A0`.
3. Its false hints do not exceed 10 per 1 000 prompts.
4. Cost class: **hook-resident** (median latency at most 150 ms and 95th percentile at most 400 ms, no network) or declared **asynchronous**, i.e. usable only for a model-side design and not as a hook. The class is reported with the result, not hidden.

Best variant: among architectures that satisfy 1 to 3, the highest F1; if two are within each other's 95 % interval, the cheaper one. If none satisfies 1 to 3, the result is **negative** and the report names the next experiment (candidates, in order: more labeled true requests by the forward holdout of the earlier experiment; the model reading the catalogue inside the main conversation, measured by outcome marks).

## Discrepancies in the earlier figures, to be reconciled in `decision.md`

Estimated true requests 92 versus 111 versus the exact count from complete labels; hint rate 0.2 % versus 0.15 %; "one in four hints useful" versus 2 of 25; `v0` hit rate 6.7 % versus the reconstructed 6.5 %; recall figures built on an estimated denominator. The complete labeling replaces every estimate by a count.

## What this result does NOT mean

1. It does not show that a hint, however accurate, helps the owner: there is no outcome data.
2. It does not generalise beyond this maintainer's Russian prompts of one period.
3. The labels are agreement of Claude-family labelers, checked by majority on positives; they are not the owner's judgement.
4. With about 33 true requests in TEST an improvement smaller than about 15 recall points cannot be detected.
5. Latency of local models on this machine is not the latency on another machine.

## Privacy

Prompt text, embeddings and labels stay in a local scratch directory outside the repository. Only aggregate counts and rates go into `decision.md`.
