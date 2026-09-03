# stress_tests.md — 20260903-memory-retrieval-repair (PR-1)

**Experiment ID:** `20260903-memory-retrieval-repair`

## Adversarial Test Cases

### Case 1: Nested PARA sub-directory (the exact §0.1 reproduction)

**Input:** a note routed to `wiki/projects/2026-09-02_auc_red_flags.md` (one level
deep under `wiki/`), rather than the flat `wiki/` root every prior unit test used.

**Expected:** `rglob("*.md")` finds it; `glob("*.md")` (the pre-PR-1 code) would not.

**Actual:** found and indexed. `test_indexes_para_subdirectories` and the full
end-to-end `test_para_routed_note_is_indexed_and_searchable` both pass.

**Result:** PASS

---

### Case 2: `daily/` notes must stay excluded after the `rglob` widening

**Input:** a note under `wiki/daily/2026-09-03.md`.

**Expected:** `rglob` now walks every sub-directory, so without an explicit
exclusion, daily notes (previously excluded only because they lived outside a
flat `glob("*.md")`'s reach, or were never routed there in tests) would start
being indexed as a side effect of fixing Case 1 — an unintended scope expansion,
not a fix.

**Actual:** `_EXCLUDED_DIR_NAMES = frozenset({"daily"})` filters them out
regardless of nesting depth. `test_daily_notes_excluded_from_corpus` passes.

**Result:** PASS

---

### Case 3: Corpus-fingerprint gate must not falsely skip real changes

**Input:** rebuild once, then add a second note before rebuilding again.

**Expected:** the fingerprint (SHA-256 over sorted `rel_path:size:mtime_ns`) must
differ from the stored sidecar value, forcing `changed=True`.

**Actual:** `test_changed_corpus_triggers_reindex` passes — a changed corpus is
never mistaken for an unchanged one.

**Result:** PASS

---

### Case 4: Fingerprint sidecar must not corrupt the TF-IDF index format

**Input:** the TZ's own §0-adjacent concern — could a naively-implemented
fingerprint (stored as a root key inside `tf_index.json`) be misread by
`_load_tfidf_index()` / `_cosine()` as a malformed document vector?

**Expected:** no — the fingerprint must live in a separate sidecar file
(`corpus_fingerprint.txt`), never inside `tf_index.json`.

**Actual:** confirmed by direct code read (`_fingerprint_path()` returns a path
distinct from the TF-IDF index file) — this is a design property, not something
a unit test can regress-test on its own, so it is recorded here as a stress
case resolved by construction rather than by an assertion.

**Result:** PASS (by construction; see `hooks/vector_store.py::_fingerprint_path`)

---

### Case 5: Internal indexing failure must be counted, not silently absorbed into "indexed"

**Input:** `index_wiki_entry()` monkeypatched to reproduce its own documented
fail-open contract (print a warning, return failure, never raise) — the exact
shape a real lock timeout or TF-IDF save failure takes.

**Expected:** `RebuildReport.failed` reflects it; `indexed` does not.

**Actual (found by an isolated-worktree reviewer agent, NOT by the original
author, before this PR was merged):** initially FAILED — `index_wiki_entry()`
swallowed its own exceptions internally and returned `None`, so
`rebuild_index()`'s `except Exception: failed += 1` never fired; the file was
counted as `indexed`. Fixed by changing `index_wiki_entry()` (and
`_save_tfidf_index()` beneath it) to return `bool`, and having
`rebuild_index()`'s loop check that return value instead of relying only on
an exception. `test_internal_indexing_failure_is_counted_not_hidden` now
passes.

**Result:** PASS (after fix)

---

### Case 6: A failed rebuild must not be mistaken for "corpus unchanged" on the next call

**Input:** rebuild once with a simulated internal indexing failure (Case 5),
then rebuild again with the failure removed, corpus otherwise unchanged.

**Expected:** the second call must still retry the file — the corpus fingerprint
is keyed on file stats, not on indexing success, so saving it after a failing
run would make every later call see "fingerprint matches, changed=False" and
never retry the file that actually failed.

**Actual (same reviewer finding as Case 5):** initially FAILED for the same
underlying reason — the fingerprint was saved unconditionally after every
rebuild, including ones with `failed > 0`. Fixed: `rebuild_index()` now saves
the fingerprint only `if failed == 0`. `test_failed_rebuild_does_not_save_fingerprint_and_retries`
now passes.

**Result:** PASS (after fix)

---

## Result (PR-1)

6/6 stress cases PASS (4 in the original pass, 2 more added after an isolated-
worktree reviewer agent found and this PR fixed a real P1 defect before merge —
see decision.md § Skeptic Concerns for the review trail). No PARTIAL or
unresolved FAIL outcomes remain on PR-1's scope.

---

## PR-2 — `rel_path` join key stress cases

### Case 7: Title contains characters that look like path separators, but isn't one

**Input:** a candidate title containing a literal `|` with no real rel_path
before it (malformed/legacy edge case) — `title.split("|")[0]` on
`"|Orphaned Title"` yields an empty string.

**Expected:** `_read_wiki_content("")` returns `None` (the existing `not
stem` cheap-reject), not a crash or an accidental `WIKI_DIR/.md` open.

**Actual:** PASS — covered by the existing `not stem` guard, unaffected by
PR-2's relaxation of the `/` character check.

**Result:** PASS

### Case 8: Absolute-path and drive-letter injection via a hostile rel_path

**Input:** the 6 hostile stems already pinned in
`test_read_wiki_content_rejects_path_traversal` — `../`, `..\\`, an absolute
POSIX path, an absolute Windows path, a drive-letter path, and a nested
`../../../` traversal — re-run specifically BECAUSE PR-2 relaxed the cheap
pre-check to allow legitimate `/` (PARA sub-dirs). Relaxing one character
class must not silently widen the attack surface.

**Expected:** all 6 still rejected — the leading-`/`/`:`/`\\` checks plus
the authoritative `resolve()` + `relative_to(WIKI_DIR)` backstop.

**Actual:** PASS — all 6 rejected, confirmed by re-running the exact
pre-existing test (not a new one, since weakening/duplicating a security
test is itself a Test Protection violation) after the PR-2 code change.

**Result:** PASS

### Case 9: TF-IDF index transition — mixed old (flat) and new (wrapped) entry shapes

**Input:** a TF index containing one pre-PR-2 flat `{token: weight}` entry
(simulating a stale title-keyed entry not yet cleaned up — PR-3's job) and
one post-PR-2 `{"title", "vector"}` wrapped entry, both present at once.

**Expected:** `semantic_search_paths()` must not crash on the malformed
entry — it should skip it and still return the well-formed one.

**Actual:** PASS — the defensive `isinstance(entry, dict) and "vector" in
entry` check in `semantic_search_paths()`'s TF-IDF loop skips the flat
entry cleanly.

**Command:**
```
python -m pytest tests/test_vector_store.py::TestTfidfIndex::test_search_skips_stale_pre_pr2_flat_entries -q
```

**Result:** [x] PASS

## Result (PR-2)

3/3 new stress cases PASS. Combined with PR-1's 6/6, no PARTIAL or
unresolved FAIL outcomes remain on PR-1+PR-2's combined scope.
