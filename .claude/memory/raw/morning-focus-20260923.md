# Morning Focus - 2026-09-23

## 🐸 A1 Task (eat the frog first)
Run `pytest --cov --cov-report=term-missing hooks/ scripts/`, identify the lowest-coverage modules, write targeted unit tests until coverage reaches ≥86%, push, and confirm CI green — do this BEFORE touching any other file or GitHub issue.

## Top-3 Priority
1. **Coverage 84% → ≥86%** — Signal: this is the literal "Done when" criterion in the Scope Fence; it has been the stated A1 since 2026-06-10 with zero progress days (see evening-snr-20260729 SNR 2/10). Reactive hook fixes, memory docs, and badge updates are all Noise until this gate closes.
2. **Semantic-search fusion decision** — Signal: Observed−Floor delta is +0.062, below the original PR-5 gate threshold of +0.10, with a concrete verified mechanism (PR-5's unconditional semantic top-up evicts correct keyword hits). Owner decision needed: leave as-is or investigate smarter fusion (e.g., don't let dense top-up evict an existing keyword hit). Prepare a one-paragraph proposal to surface for owner review.
3. **§8 hypothesis-arbiter kickoff brief** — Signal: the DEFAULT FOCUS BIAS decision (2026-09-02) explicitly chose "real §8 experimental-pack work NOW." Currently stalled because owner hasn't named a concrete hypothesis. Prepare a one-page brief with 3 candidate hypotheses to unblock the decision.

## Ignore Today
- Badge/readme count sync — Noise: no CI run triggered it, pure admin
- Reactive hook bug hunting — Noise: unless a specific failing test surfaces during the coverage run
- Memory/history archiving — Noise: activeContext.md is already under its size limit
- `ruff check` pin update — C-task, no consequence if skipped today
- New feature branches before CI is green — forbidden by Scope Fence until coverage gate closes

## SNR Score yesterday: 2/10
(Source: `.claude/memory/raw/evening-snr-20260729.md` — most recent evening SNR on file.
Pattern: A1 coverage gate avoided for 25+ consecutive days; all work was reactive, off-plan. Same frog
has been on the plate since 2026-06-10. Today is the day to eat it first.)

#morning-focus #focusos #tracy #snr
