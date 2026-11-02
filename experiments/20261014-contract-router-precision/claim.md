# claim.md — 20261014-contract-router-precision

Written 2026-10-14 BEFORE any label existed and before any labeler ran. The only numbers known at this point are the hit counts of the two router versions on the corpus (660 and 25 of 10 147 prompts); no label, precision or recall figure existed.

## Zero-Signal Gate

| Field | Value |
|-------|-------|
| **Entity** | the contract router (`skills/core/contract/contracts_lib.py`, as called by `hooks/resource_router.py`) and its first version, reconstructed as `v0` |
| **Falsifiable predicate** | on the same labeled prompts, `v1` produces at most half as many false hints as `v0`, and its recall of true requests is not lower than `v0`'s by more than 1 percentage point |
| **Measurable outcome** | counts of false hints (exact, from the labeled candidate set), recall with a 95 % interval, both against independent blind labels |

## L0: Question Type

- [x] Descriptive — the error profile of two fixed rule sets on a fixed corpus
- [x] Predictive — only in one narrow sense: whether the rule change generalises to sessions not used for tuning (session-level split below)
- [ ] Causal — no claim about whether a hint improves any user outcome; there are no outcomes in the data

## Natural Language Statement

> We estimate precision, recall and false-positive counts of the contract router versions `v0` and `v1` for the 10 147 typed prompts in 87 local Claude Code sessions, comparing `v1` against `v0` on identical labels, with labels supplied by blind independent labelers who never see router output.

## Design (frozen here)

- **Population:** user-typed prompts from `~/.claude/projects/*/*.jsonl` as of 2026-10-14, minus slash commands, `fast:` / `just do:` prompts and prompts shorter than 15 characters (the same filter as `scripts/eval_contract_router.py`).
- **Versions:** `v1` is the router as committed in this worktree on 2026-10-14. `v0` is reconstructed by switching rules off: min 2 stems, no rarity score, no request-verb gate, long input from 1500 chars judged by head 700 and tail 300 with stems allowed, phrases matched anywhere, the first 10 cards only. Control: the harness reproduces `lib.route` on all 10 147 prompts with 0 mismatches; `v0` reproduces the earlier measurement approximately (660 hits, 6.50 %, against 675 of 10 143, 6.7 %).
- **Candidate set C (labeled in full):** every prompt where the loosest rule set (2 stems, no gates, all 41 cards) matches. It contains every hint either version can emit: 1 768 prompts.
- **Random sample R (labeled):** 400 prompts from the complement of C, stratified by length (250 up to 200 chars, 50 each in the other three buckets). It estimates the true requests that no rule catches.
- **Labels:** each prompt gets one of 41 card ids or `NONE`, plus a `kind` (request, pasted report, role prompt, chat, status, question, other). Labelers are fresh subagents; they see the card catalogue and the prompt text, never a router decision. A random subset of 200 prompts is labeled twice by different agents; agreement is reported as Cohen's kappa on "positive vs NONE" and as exact card agreement.
- **Strict hit:** the hinted card equals the labeled card. **Lenient hit:** the prompt is labeled with any card.
- **Independent data:** none exists. `v1` was tuned while reading samples from this very corpus, so its numbers are optimistic. Any further rule change in this experiment is tuned on a TRAIN split (sessions with `sha1(session id) mod 10 < 7`) and reported on TEST (the rest); the corpus-wide figures stay labeled "contaminated". A forward holdout (prompts after 2026-10-14, from `contract_routes.jsonl`) is the real independent check and is not available yet.

## Detectability, stated before labels are counted

`n` = number of labeled true requests P (unknown until labeling; expected small, tens). `baseline` = recall of `v0` (unknown). `alpha` 0.05 two-sided, `power` 0.8. For a paired difference in recall the detectable drop is roughly `2.8 * sqrt(d) / P`, with `d` the number of discordant prompts. With P below about 300 no difference of 1 percentage point can be detected, whatever the data show. `MCID` = 1 percentage point (the owner's criterion). Pre-registered consequence: the recall clause is decided `INCONCLUSIVE` unless the 95 % interval of the recall difference lies entirely within ±1 percentage point or entirely outside it. An interval that includes both is reported as such, not rounded to success or failure.

## Decision rules (frozen)

1. False-hint clause: `FP(v1) <= 0.5 * FP(v0)` over C, where FP counts hints under the strict definition. This is an exact count, not an estimate.
2. Recall clause as above; the recall estimate is a stratified estimate over C and R with Wilson intervals.
3. If clause 1 holds and clause 2 is `INCONCLUSIVE` or fails, the verdict is stated per clause; no composite "success".
4. Rule changes made during the experiment are listed in `decision.md` with the TRAIN/TEST numbers on both sides of each change.

## What this result does NOT mean

1. It does not show that a correct hint helps: there is no outcome data, so usefulness is untested.
2. It does not generalise to other users, other languages or later months: one maintainer's Russian-language prompts from one period.
3. It does not make the labels ground truth: they are the agreement of blind model labelers, checked against each other on a subset, not against the owner. Where the labelers disagree with the owner, the owner is right.
4. It does not validate `v1` as tuned: the corpus-wide `v1` figures are contaminated by tuning on the same prompts.
5. A `v0` reconstructed from the current cards is an approximation of the first version, not the first version.

## Privacy

Prompt text and labels stay in a local scratch directory outside the repository. Only aggregate counts and rates go into `decision.md`, never wording.
