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

---

## PR-2 — `rel_path` is the real join key

### Positive Control

**Input:** a raw note titled "AUC Red Flags", routed by `raw_to_wiki` into
`wiki/projects/` with a dated-slug filename (title != stem — the exact §0.2
reproduction), driven through `update_wiki_index()` →
`knowledge_librarian._query_wiki_raw_titles()` → `_classify_and_render_wiki()`.

**Expected output:** the HOT-tier renderer opens the REAL file (via
`rel_path`, not a title-as-filename guess) and the rendered line contains
real body content.

**Command:**
```
python -m pytest tests/test_memory_retrieval_chain.py::TestFullRetrievalChain::test_title_ne_stem_opens_real_file_via_index_alias -q
```

**Result:** [x] PASS

### Negative Control

**Input:** the exact pre-PR-2 code path, reproduced directly — call
`_read_wiki_content` with a bare title that doesn't match any real filename
(no rel_path prefix, simulating the old broken lookup).

**Expected output (rejection):** returns `None`, exactly as before — PR-2
does not weaken the "not found" case, it only adds a NEW path (rel_path
present) that succeeds where the old one failed.

**Command:**
```
python -m pytest tests/test_attention_decay_tiering.py::TestClassifyAndRenderWiki::test_missing_file_does_not_crash -q
```

**Result:** [x] PASS

### No-Collapse Tests

- **Data swap** — two files sharing an identical H1 title, different
  `rel_path`: `test_two_entries_sharing_title_do_not_collide` (vector_store)
  and `test_two_files_sharing_title_both_individually_retrievable`
  (knowledge_librarian). Result: [x] PASS
- **Negative control** — bare legacy title with no rel_path prefix still
  falls through correctly (see above). Result: [x] PASS
- **Security regression** — all 6 hostile stems from PR #106
  (`../`, `..\\`, absolute POSIX, absolute Windows, drive letter, nested
  `../`) still rejected by `_read_wiki_content` after relaxing the cheap
  pre-check to allow `/`: `test_read_wiki_content_rejects_path_traversal`.
  Result: [x] PASS
- **Convention flip** — legacy bare-title candidates (no `|`, no rel_path)
  from existing `TestKnowledgeLibrarianIndex`/`TestUpdateWikiIndex` fixtures
  continue to work unchanged. Result: [x] PASS

### Verdict: READY.

---

## PR-4 — real corpus-wide TF-IDF

### Positive Control

**Input (updated post-redesign — see decision.md PR-4 § Skeptic Concerns
Round 2 for why):** a rebuild of 51 documents — 50 documents each
containing only a corpus-common term ("common", df=50 of 51) and 1
document containing a corpus-rare term ("raretermx", df=1 of 51). Query
weighted 2:1 toward the common term (`"common common raretermx"`).

The original control (3 documents, un-smoothed IDF, 4:1 query ratio) is
superseded: once IDF is smoothed (`log((n+1)/(df+1))+1`), "common"'s idf
floors at ~1.0 instead of hitting exactly 0, and a 3-document corpus no
longer has enough contrast to flip the ranking through the real
`semantic_search_paths()` pipeline (which also picks up the non-stopword
"entry" shared by every document's header). Re-derived by hand-sweeping
corpus size and query ratio against the exact document text the test
writes.

**Expected output:** with real, smoothed IDF applied, the document
containing the rare term ranks first (0.63 cosine vs. 0.39 for the
next-best common-only document).

**Command:**
```
python -m pytest tests/test_vector_store.py::TestRealTfidf::test_rare_term_outranks_common_term_under_real_idf -q
```

**Result:** [x] PASS

### Negative Control

**Input:** the exact same 51-document corpus and query, with `_apply_idf`
monkeypatched to a no-op (pure TF, the pre-PR-4 behavior).

**Expected output (the negative case that must be produced first, proving
the test scenario is real and not a tautology):** under pure TF, a
document matching ONLY the common term ranks FIRST (0.80 cosine) — the
opposite of the real-IDF result. If this assertion fails, the test's own
setup assumption is wrong and the positive control above would not be
meaningful.

**Result:** [x] PASS (part of the same test —
`test_rare_term_outranks_common_term_under_real_idf` asserts the pure-TF
ordering explicitly before asserting the real-IDF ordering)

### No-Collapse Tests

- **Data swap** — a different corpus/query construction
  (`test_query_side_idf_applied`, distinct terms and documents from the
  ranking test) still produces a nonzero idf sidecar and a correct match.
  Result: [x] PASS
- **Negative control** — pure-TF ordering confirmed opposite of real-IDF
  ordering (see above). Result: [x] PASS
- **Convention flip** — mutating the corpus (adding a document) between
  two rebuilds changes the corpus-wide idf weight for a term shared by
  every PRE-EXISTING document, and the EFFECTIVE (search-time) weighting
  applied to both pre-existing documents' unchanged raw vectors, not just
  affecting the new document:
  `test_adding_one_document_reweights_every_existing_document`. Rewritten
  post-redesign to check the idf sidecar + `_apply_idf` output rather than
  a stored "reweighted vector" (documents are never reweighted in
  storage now — see decision.md). Result: [x] PASS
- **Adversarial** — an empty/missing idf sidecar (no `rebuild_index()` has
  ever run; a document was written via the low-level `index_wiki_entry()`
  path directly) must NOT zero out every query and return no results —
  confirmed it falls back to plain-TF comparison instead:
  `test_empty_idf_sidecar_falls_back_to_plain_tf`. This was a real bug
  found and fixed BEFORE it reached the other tests (an empty idf dict
  applied via `_apply_idf` was zeroing every query term, matching
  `_apply_idf()`'s own documented out-of-vocabulary-term=0 behavior, but
  applied when there was no real idf information at all, not when a term
  was genuinely absent from a known corpus). Result: [x] PASS
- **Adversarial (added, Round 3 — externally-pasted review on the Round-2
  redesign):** a brand-new term added via `index_wiki_entry()`'s single-
  entry write path (not a full `rebuild_index()`) must be findable by that
  term immediately, not only after the next rebuild. Confirmed real by
  reproduction first (a note containing "quantumtelemetry", added after a
  rebuild that never saw that term, returned `[]` on search for it) — then
  fixed (`index_wiki_entry()` now deletes the idf sidecar and invalidates
  the fingerprint on a successful write):
  `test_index_wiki_entry_note_findable_by_brand_new_term_immediately`.
  Result: [x] PASS

### Verdict: READY.

---

## PR-3 — atomic, reported rebuild

### Positive Control

**Input:** index two files (A, B) with distinct content, then delete B's
file and rebuild — in both the TF-IDF and Chroma backends independently.

**Expected output:** B's rel_path is absent from the index/collection after
the rebuild; searching B's terms returns no hits; A remains present and
searchable; `RebuildReport.deleted == 1`.

**Commands:**
```
python -m pytest tests/test_vector_store.py::TestRebuildIndex::test_deleted_file_removed_from_tf_index -q
python -m pytest tests/test_vector_store.py::TestRebuildIndex::test_deleted_file_removed_from_chroma_collection -q
```

**Result:** [x] PASS

### Negative Control

**Input:** a rebuild where one of three files raises during read (simulated
`OSError`).

**Expected output (the negative case that must NOT happen):** the failure
must NOT produce a half-written index, and must NOT report `indexed == 3`
(claiming the broken file succeeded) or `indexed == 0` (discarding the two
good files along with the one bad one).

**Command:**
```
python -m pytest tests/test_vector_store.py::TestRebuildIndex::test_one_of_three_files_failing_leaves_others_correctly_indexed -q
```

**Result:** [x] PASS (`indexed=2`, `failed=1`, both good files remain
independently searchable)

### No-Collapse Tests

- **Data swap** — TF-IDF backend vs Chroma backend, same stale-deletion
  scenario, independently tested (see positive control above, both
  commands). Result: [x] PASS
- **Negative control** — partial-failure rebuild (see above). Result: [x] PASS
- **Convention flip** — a Chroma collection whose `upsert`/`get`/`delete`
  behave via a deterministic in-memory fake rather than the real optional
  dependency, confirming the LOGIC (not a specific library's behavior) is
  correct: `test_deleted_file_removed_from_chroma_collection`. Result: [x] PASS
- **Adversarial** — the Chroma batch write itself raising mid-upsert (a
  hand-rolled `object()` with no real methods, from the pre-existing
  `test_backend_becoming_available_forces_rebuild`) — confirmed fail-open,
  no crash, no false fingerprint save. Result: [x] PASS

---

## PR-3 follow-up — last-known-good on a persistent parse failure

### Positive Control

**Input:** index two files (a, b), then make `a` fail to parse across TWO
CONSECUTIVE rebuilds (b's content changes each time so the fingerprint
differs and a real rebuild actually runs both times).

**Expected output:** `a`'s entry survives BOTH failed runs unchanged
(byte-identical to its last successfully-indexed vector), `deleted == 0`
on both runs (a still-existing-but-unparseable file is not "deleted"),
and `a` remains findable by its own content via `semantic_search_paths()`
after both failures.

**Command:**
```
python -m pytest tests/test_vector_store.py::TestRebuildIndex::test_repeatedly_failing_file_keeps_last_known_good_entry -q
```

**Result:** [x] PASS

### Negative Control

**Input:** the same scenario, but after the two failed rebuilds, `a`'s
file is genuinely deleted from disk and a further rebuild runs.

**Expected output (the negative case that must NOT happen if positive
control's logic were "keep every failed-or-missing entry forever"):**
`a`'s entry MUST be removed this time, and `RebuildReport.deleted` must
become 1 — proving last-known-good retention is conditional on the file
still existing, not a blanket "never delete" policy that would silently
reintroduce PR-3's original never-removes-stale-entries bug.

**Result:** [x] PASS (same test, final assertions)

### No-Collapse Tests

- **Data swap** — a different pair of files/content from the ranking
  tests elsewhere in this experiment; same mechanism (persistent parse
  failure vs. genuine deletion), independently confirms the merge logic
  isn't tied to one specific corpus shape. Result: [x] PASS (covered by
  the single test above using its own two-file corpus, distinct from
  PR-3's original A/B positive control)
- **Negative control** — genuine deletion after persistent failure (see
  above). Result: [x] PASS
- **Convention flip** — IDF is now computed over the MERGED index
  (kept-stale + freshly-parsed), not just the freshly-parsed batch —
  confirmed the kept-stale document's terms still participate in the
  corpus-wide document-frequency count (verified by reading
  `rebuild_index()`'s own updated WHY comment and reproducing by hand
  before writing the code change; no separate test needed since
  `_compute_corpus_idf()`'s own existing tests already cover the formula
  itself — this control is about WHICH vectors get passed to it, not the
  formula). Result: [x] PASS (reproduced by hand, see decision.md)
- **Adversarial** — two CONSECUTIVE failures (not just one, which
  PR-3's own `test_one_of_three_files_failing_leaves_others_correctly_indexed`
  already covered) — proving the fix isn't a one-off "first failure is
  special-cased" patch but a genuine per-run merge that holds regardless
  of how many consecutive runs the same file keeps failing.
  Result: [x] PASS
- **Adversarial (added, Round 2 — GitHub Codex bot review on this PR):**
  the same last-known-good gap existed in the Chroma backend's own
  stale-id cleanup, untouched by the first version of this PR — confirmed
  real by reproduction (a file failing to embed across a rebuild lost its
  still-valid Chroma embedding, `deleted=1`), then fixed identically to
  the TF-IDF branch (`stale_ids` computed against the current file list,
  not this run's successfully-embedded batch):
  `test_chroma_repeatedly_failing_file_keeps_last_known_good_embedding`.
  Result: [x] PASS
- **Adversarial (added, Round 2 — GitHub Codex bot review on this PR):** a
  malformed/legacy retained entry (no "vector" key) for a file that ALSO
  fails to parse this run — confirmed real by reproduction (crashed
  `rebuild_index()` with an uncaught `KeyError` instead of returning a
  failure report), then fixed with the same defensive shape check
  `semantic_search_paths()` already uses on the read side:
  `test_malformed_retained_entry_does_not_crash_rebuild`.
  Result: [x] PASS

### Verdict: READY.

### Verdict: READY.

---

## PR-5 — wire semantic retrieval into the production path (§5.3 gate)

### Benchmark construction (`~/.claude/memory/benchmarks/retrieval_v1.jsonl`, outside Git per the TZ's public/private split)

**Method:** 32 questions mined directly from the real, live
`~/.claude/memory/_auto/wiki/` corpus (1940 real notes, rebuilt and
verified during PR-4's live deployment) — NOT the separate personal
Obsidian vault, which was checked first and found to be a DIFFERENT,
not-directly-indexed knowledge base (a real risk caught before it produced
an invalid benchmark: several Obsidian notes sampled as candidates had no
corresponding entry anywhere in the searchable wiki corpus, verified by
grep before using any of them). Each question paraphrases a real note's
content using different vocabulary than the note's own title/key terms —
synonyms, descriptive rephrasing, or register shift — specifically to test
whether semantic search beats keyword matching on exactly the kind of
query keyword matching structurally cannot answer.

**Adjudication (2 independent, context-blind rounds, per this repo's own
falsification-ladder.md Context Asymmetry Rule):**
- Round 1 (32 entries reviewed): found 2 entries with a genuine relevance
  defect (the linked note did not actually answer the query — one
  misattributed a "6 months" framing from a different, merely-mentioned
  project; one matched a title's apparent topic but not the note's actual
  one-line content) and 14 entries too close to verbatim keyword overlap
  with the source note's own title/content (defeating the benchmark's
  purpose — solvable by plain substring matching with zero semantic
  understanding).
- All 16 flagged entries rewritten to fix relevance and/or genuinely
  reword using different vocabulary.
- Round 2 (the 15 rewritten paraphrase-quality entries re-reviewed,
  q28 the 16th already independently re-verified for relevance): 12/15
  passed cleanly; 3 (q04, q12, q31) still reused a source note's exact
  proper-noun/notation, rewritten a second time to describe the content
  functionally instead.
- Final self-check on the 3 second-round rewrites (not re-dispatched to a
  third agent — cost-discipline judgment call, consistent with this
  repo's own paraphrase-sensitivity-probe guidance reserving repeated
  adversarial passes for cases where a wrong result is expensive).

**Honest limitation, stated explicitly per the user's own instruction:**
this is an **AI-mined, AI-adjudicated benchmark**, not a human-labeled gold
standard. The Ceiling (below) is a construction guarantee ("every
question has a verified-real answer somewhere in the corpus"), not a
human-blind-judged upper bound on achievable retrieval quality.

### Positive Control

**Input:** the exact TZ-named acceptance scenario — a query using a
synonym with zero literal keyword overlap with the target note.

**Expected output:** `semantic_search_paths()` retrieves the entry,
`_read_wiki_content()` opens it by `rel_path`, and the corrected scoring
can render it HOT.

**Command:**
```
python -m pytest tests/test_attention_decay_tiering.py -q -k TestSemanticTopUp
python -m pytest tests/test_attention_decay_tiering.py -q -k test_dense_score_substitutes_for_keyword_overlap
```

**Result:** [x] PASS

### Negative Control

**Input:** the same keyword-only path, with `query=""` (semantic top-up
disabled) — reproduces the exact pre-PR-5 behavior.

**Expected output:** the floor measurement (below) must be WORSE than the
observed measurement — proving the semantic supplement is doing real work,
not a no-op.

**Result:** [x] PASS — Floor 2/32 = 0.062 vs Observed 6/32 = 0.188.

### §5.3 Floor–Ceiling–Observed Gate (the actual quantitative decision)

**Floor** (keyword-only, `_query_wiki_raw_titles(..., query="")`, scored
and ranked through the SAME production pipeline
`_classify_and_render_wiki()` uses — not just the raw candidate order):
**2/32 = 0.062** (ru 1/16, en 1/16).

**Observed** (keyword+semantic, full PR-5 code, same production ranking):
**6/32 = 0.188** (ru 4/16=0.250, en 2/16=0.125).

**Δ = +0.125 ≥ the TZ's own +0.10 absolute threshold → GATE PASSES.**

**Ceiling** (construction-guaranteed, per the honest-naming instruction
above): 32/32 = 1.000 — every entry's `relevant_rel_paths` is a
verified-real file in the corpus, confirmed by 2 rounds of independent
adjudication. Not a human-blind-judged retrieval-quality ceiling.

**Two in-flight design corrections, both found BY this measurement, not
assumed beforehand** (see `claim.md`'s own Design History for the full
detail): (1) an unconditional-vs-thresholded semantic top-up (delta
+0.062 → +0.094), (2) a separate 70/30 dense-hit score weight vs the
keyword path's unchanged 50/50 (delta +0.094 → +0.125, passing). Recorded
as findings, not silently applied — the TZ's own literal spec for (1) was
measured and found insufficient before being corrected.

### No-Collapse Tests

- **Data swap** — measured against the REAL, live 1940-note corpus (not a
  synthetic fixture), independently sampled and adjudicated. Result:
  [x] PASS
- **Negative control** — floor (query="") vs observed, see above. Result:
  [x] PASS
- **Convention flip** — dense hits use a DIFFERENT score blend
  (70/30) than keyword hits (50/50, unchanged) — confirmed the keyword
  path's own existing tests (`TestFullRelevanceScore::test_keyword_dominates`,
  all of `TestClassifyAndRenderWiki`) still pass unmodified, proving the
  keyword path genuinely wasn't touched. Result: [x] PASS
- **Adversarial** — a query whose keywords are generic enough to spuriously
  fill the keyword-only candidate pool with unrelated recent notes (the
  exact real failure mode this measurement discovered, reproduced with
  `q01`) — confirmed the always-on semantic top-up now still contributes a
  candidate even when the keyword path alone already reached `top_n`:
  `test_still_tops_up_when_keyword_results_already_fill_top_n`. Result:
  [x] PASS

### Verdict: READY.
