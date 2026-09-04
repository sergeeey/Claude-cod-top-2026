# result_summary.md — 20260903-memory-retrieval-repair (PR-1)

## Classification

PROMOTE — positive control, negative control, and all applicable no-collapse
tests pass; the pre-existing single failure is confirmed unrelated (reproduced
identically with this PR's diff removed).

## Evidence

- New/changed tests, all green: `tests/test_vector_store.py` (`TestRebuildIndex`,
  `TestConcurrentIndexing` unchanged and still passing; 2 more tests added
  after an isolated-worktree reviewer found and this PR fixed a real P1 defect
  — internal indexing failures were counted as successes, see decision.md) and
  `tests/test_memory_retrieval_chain.py` (new file, 2 tests). 37 tests total
  across both files, all passing.
- Full local suite: 3034 passed, 1 pre-existing unrelated failure, 3 skipped,
  2 xfailed (see `controls.md` § Verification Substrate Gate).
- `ruff check`, `mypy --ignore-missing-imports`, `scripts/check_architecture.py --check`,
  `scripts/gen_hook_matrix.py --check` all clean on the touched files.

## External Reconstruction

[VERIFIED-REAL] source: https://github.com/sergeeey/Claude-cod-top-2026/pull/332 (commit 7a92193db3ed3b19008edbdb1989fceb41eebbf5)

A GitHub Codex bot automated review on `docs/memory-retrieval-repair-tz.md`
(the PR above) independently flagged the fingerprint-storage design risk this
PR-1 code already avoids (sidecar file `corpus_fingerprint.txt`, not a key
inside `hooks/vector_store.py`'s `tf_index.json`) — an independent party
checking the same failure mode this experiment's claim addresses. Direct code
citation: `hooks/vector_store.py::_fingerprint_path`.

## PR-4 addendum — real corpus-wide IDF, redesigned after external review

[VERIFIED-REAL] source: https://github.com/sergeeey/Claude-cod-top-2026/pull/336
CI run job https://github.com/sergeeey/Claude-cod-top-2026/actions/runs (job id
100768664892, fetched directly via `gh api
repos/sergeeey/Claude-cod-top-2026/actions/jobs/100768664892/logs`)

An externally-pasted review (2026-09-03/04) independently identified two real
defects in this PR's first version, both verified with tools before being
accepted (not on the review's prose alone), per `decision.md`'s PR-4 § Skeptic
Concerns Round 2:

1. Un-smoothed IDF (`log(n/df)`) zeroing every term in any corpus where a term
   appears in every document — confirmed by fetching the actual CI job log,
   which matched the review's cited failures byte-for-byte (`3 failed, 3054
   passed, 2 skipped, 2 xfailed`). Fixed with scikit-learn-style smoothed IDF.
2. The initial "delete the idf sidecar on partial write failure" fix left
   already-written, IDF-baked documents on disk mismatched against a
   plain-TF query — confirmed by reproducing a wrong ranking (irrelevant
   document scoring 0.949 vs. the relevant document's 0.316). Fixed by a
   redesign: documents are always stored as plain TF; IDF is applied fresh,
   symmetrically, to both the query and each document at search time.

Both fixes verified post-redesign: `tests/test_vector_store.py` full file (52
tests) and `tests/test_memory_retrieval_chain.py` (3 tests) all pass; full
local suite 3057 passed, 1 pre-existing unrelated failure, 3 skipped, 2
xfailed; `ruff`/`mypy` clean on touched files.
