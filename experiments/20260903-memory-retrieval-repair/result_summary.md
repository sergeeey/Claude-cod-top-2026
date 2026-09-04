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
xfailed; `ruff`/`mypy` clean on touched files. CI on PR #336 (job triggered
by the redesign push): green on Python 3.11 and 3.12.

## PR-4 addendum 2 — residual findings on the redesign, from a second
externally-pasted review

A second review, run against the Round-2 redesign itself, confirmed the two
math bugs above were genuinely fixed and found two smaller residual issues,
both verified with tools before being fixed — see `decision.md`'s PR-4 §
Skeptic Concerns Round 3 for the full trail:

1. `index_wiki_entry()`'s single-entry write path never invalidated the idf
   sidecar, so a brand-new term added out-of-band was out-of-vocabulary
   until the next full rebuild — confirmed by reproduction (a note added
   with the term "quantumtelemetry" was unfindable by that term), fixed by
   deleting the sidecar and invalidating the fingerprint on a successful
   single-entry write. Regression test:
   `test_index_wiki_entry_note_findable_by_brand_new_term_immediately`.
2. Several docstrings, test comments, and this experiment's `claim.md` still
   described the superseded (Round-1) architecture — documents reweighted
   at index time — as current; one test's assertion message still said
   "4:1" after the query ratio changed to "2:1". Confirmed by grep, fixed
   by rewriting each in place (with the superseded architecture kept as
   explicit history, not silently deleted).

A third finding (PR-3's stale/failed-entry deletion is better modeled as
"last known good" than as accept-and-self-heal) was accepted as a real
refinement but deliberately not bundled into PR-4 — tracked as a separate
follow-on PR to land after PR-4 merges and before PR-5.

Full suite re-verified after these fixes: `tests/test_vector_store.py`
(53 tests) and `tests/test_memory_retrieval_chain.py` (3 tests) all pass;
`ruff`/`mypy`/`check_architecture.py --check`/`gen_hook_matrix.py --check`
all clean.

## PR-5 addendum — semantic retrieval wired in, §5.3 gate measured and passed

[VERIFIED-REAL] source: `~/.claude/memory/benchmarks/retrieval_v1.jsonl`
(32 questions, 16 RU/16 EN, mined from the real, live
`~/.claude/memory/_auto/wiki/` corpus of 1940 notes — outside Git per the
TZ's own public/private split, since it names real personal note titles
and topics). Independently adjudicated in 2 rounds by a context-blind
agent (no session context, no reasoning chain) per this repo's
falsification-ladder.md Context Asymmetry Rule — Round 1 found and fixed
2 relevance defects + 14 paraphrase-quality issues across 32 entries;
Round 2 re-verified the 15 rewrites, found 3 still too close to verbatim
source-note vocabulary, rewritten a second time.

**§5.3 gate (the actual go/no-go), measured directly against this
benchmark using the real production ranking pipeline
(`_query_wiki_raw_titles()` → `_classify_and_render_wiki()` →
`_full_relevance_score()`), not a simplified proxy:**

- Floor (keyword-only, pre-PR-5 behavior): 2/32 = 0.062
- Observed (keyword+semantic, full PR-5 code): 6/32 = 0.188
- Δ = **+0.125 ≥ the TZ's own +0.10 absolute threshold → PASS**

Two design corrections were made DURING this measurement, not before it
(both recorded in `claim.md`'s Design History and `decision.md`'s own
"Design deviation from the TZ" section, not silently applied): (1) the
TZ's own literal "top up only when keyword hits < top_n" threshold was
measured and found to let generic query words spuriously fill the
candidate pool with keyword noise, blocking semantic search entirely —
fixed by always running the semantic top-up; (2) the keyword path's
existing 50/50 keyword-overlap/recency blend, applied unchanged to dense
hits, was measured and found to let a same-day noise match structurally
outrank a genuinely strong 2-month-old semantic match — fixed with a
separate 70/30 weight for dense hits only, keyword-path scoring completely
unchanged. The first correction alone raised Δ from +0.062 to +0.094
(still short of the gate); the second raised it to +0.125 (passing).

Full suite: 3070 passed (3066 + 4 new PR-5 regression tests), 1
pre-existing unrelated failure, 3 skipped, 2 xfailed.
`ruff`/`mypy`/`check_architecture.py --check`/`gen_hook_matrix.py --check`
all clean.
