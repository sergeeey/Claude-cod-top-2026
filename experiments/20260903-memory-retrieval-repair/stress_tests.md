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

## Result

4/4 stress cases PASS. No PARTIAL or FAIL outcomes on PR-1's scope.
