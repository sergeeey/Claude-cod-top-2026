# Morning Focus - 2026-09-19

## 🐸 A1 Task (eat the frog first)
Submit PR for `test_check_global_hooks.py` machine-independent fix — committed 2026-09-04 on branch `fix/check-global-hooks-machine-dependent-test`, never PR'd. One committed fix with no PR is one invisible, unreviewed change. Run full suite locally first (`pytest tests/ -q`, `ruff check .`, `mypy --ignore-missing-imports hooks/ scripts/`, `check_architecture.py --check`, `gen_hook_matrix.py --check`), then `git push -u origin fix/check-global-hooks-machine-dependent-test` and open a draft PR.

## Top-3 Priority
1. **Submit `fix/check-global-hooks-machine-dependent-test` PR** — Signal: code is shipped when it is merged + reviewed, not when committed. A fix sitting unreviewed for 15 days is a workflow debt that compounds. One fix per PR is this repo's explicit rule; this fix has no PR yet.
2. **Propose concrete options for semantic search Δ regression** — Signal: Observed−Floor Δ is +0.062 vs the original +0.10 gate bar. Not a silent metric — the owner explicitly flagged it as an open engineering question. Write a brief decision note (≤200 words: keep as-is rationale vs. PR-5 fusion fix) so the owner can choose without deep-diving the bench numbers themselves.
3. **Draft one concrete §8 hypothesis for owner review** — Signal: the entire §8 direction (hypothesis-arbiter, claim-pipeline) is blocked on the owner naming a real hypothesis. Draft one candidate from the existing research corpus (e.g. a testable claim about memory retrieval quality vs corpus size) to give the owner something concrete to react to rather than an open-ended ask.

## Ignore Today
- **ANTHROPIC_API_KEY fix** — owner's credential, not the agent's to touch; already noted in context
- **`/release-scout` weekly scheduling** — owner's opt-in decision, no urgent consequence if deferred
- **Coverage badge/readme admin** — CI shows 84%, approaching the 86% target; legitimate but A3 at best, not a frog
- **Keyword-hit recency-decay investigation** — `next_check: 2026-10-04` per pearl_registry, not today
- **Any new hook/skills work not explicitly requested** — Default Focus Bias risk (owner flagged 2026-09-02); don't expand scope autonomously

## SNR Score yesterday: 2/10
(From evening-snr-20260729.md — last available SNR file; no SNR filed since 2026-07-29.
Pattern noted: SNR filing itself has gone dark for ~7 weeks. Consider re-enabling evening SNR routine.)

#morning-focus #focusos #tracy #snr
