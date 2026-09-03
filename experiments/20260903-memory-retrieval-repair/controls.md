# controls.md — 20260903-memory-retrieval-repair (PR-1)

## Positive Control

**Input:** a raw note tagged `#project`, routed by `raw_to_wiki.process_raw_to_wiki()`
into `wiki/projects/` (a PARA sub-directory), then indexed via `rebuild_index()`.

**Expected output:** the note is found by `semantic_search()` on a query matching
its content — i.e. the exact §0.1 reproduction from the TZ's ground-truth table,
now passing.

**Command:**
```
python -m pytest tests/test_memory_retrieval_chain.py::TestFullRetrievalChain::test_para_routed_note_is_indexed_and_searchable -q
```

**Result:** [x] PASS

---

## Negative Control

**Input:** call `rebuild_index()` a second time with no new/changed files in the
corpus (fingerprint sidecar already matches).

**Expected output (rejection of unnecessary work):** `index_wiki_entry()` is NOT
called again — `RebuildReport.changed is False`, `indexed == 0`. If the fingerprint
gate were absent or broken, this control would show `changed=True`/re-indexing on
every call, which is the exact bug the gate exists to prevent.

**Command:**
```
python -m pytest tests/test_vector_store.py::TestRebuildIndex::test_unchanged_corpus_skips_reindex \
                  tests/test_memory_retrieval_chain.py::TestFullRetrievalChain::test_second_rebuild_with_no_new_notes_is_a_no_op -q
```

**Result:** [x] PASS

---

## No-Collapse Tests (Perelman audit, minimum 3 for Standard; this is Full so all applicable ones are run)

- **Data swap** — `daily/` notes vs `projects/` notes (different directory, same file type): `test_daily_notes_excluded_from_corpus`. Result: [x] PASS
- **Negative control** — corpus unchanged → no re-index (see Negative Control above): `test_unchanged_corpus_skips_reindex`. Result: [x] PASS
- **Convention flip** — `index.md` and `note_2.md`-style chunk files present alongside real notes: pre-existing `test_skips_index_md` / `test_skips_chunk_files`, unmodified by this PR, still green. Result: [x] PASS
- **Scale variation** — not applicable: PR-1 does not change indexing algorithm complexity, only file discovery + a skip-gate; deferred to PR-4 (real IDF) where corpus size is the whole point. Result: N/A (documented, not silently skipped, not counted toward the PASS minimum)
- **Adversarial** — missing `wiki_dir` entirely: pre-existing `test_missing_wiki_dir_returns_zero`. Result: [x] PASS

## Verification Substrate Gate (Step 2a)

| Check | Status |
|---|---|
| Environment reproducible | Yes — pytest run locally, Python 3.11 target confirmed via mypy `--ignore-missing-imports` on this repo's pinned config |
| Dependency provenance | stdlib only for the new `hooks/lib/wiki_types.py` (dataclasses + typing) |
| Test-harness sanity | full suite run: 3034 passed, 1 pre-existing unrelated failure (see caveats.md), 3 skipped, 2 xfailed — matches the repo's own documented Windows-vs-CI drift, not a new regression |
| Clean state | working tree checked with `git status` before every branch switch this session; PR-1's changes were stashed/restored intact across the PR #332 merge |

**Verdict: READY.**
