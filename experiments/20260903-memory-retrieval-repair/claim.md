# claim.md — 20260903-memory-retrieval-repair (PR-1: corpus fingerprint + rglob)

> Scope note: this experiment folder covers the memory-retrieval-repair Full
> Ladder as a whole (`docs/memory-retrieval-repair-tz.md`, 7 PRs). This file's
> claim is scoped to **PR-1 only** — the fingerprint gate and the `glob`→`rglob`
> fix. PR-2 through PR-7 each get their own dated sub-claim appended below (or
> a fresh `decision.md` entry) as they land, per the TZ's own PR sequencing.

## Zero-Signal Gate

| Field | Value |
|-------|-------|
| **Entity** | `hooks/vector_store.py::rebuild_index()` and its corpus-scanning helper |
| **Falsifiable predicate** | Files under a PARA sub-directory of `wiki/` (e.g. `wiki/projects/`) are indexed and become searchable; an unchanged corpus produces no re-indexing work on a second call |
| **Measurable outcome** | `pytest tests/test_vector_store.py tests/test_memory_retrieval_chain.py -q` — specific tests named below either pass or fail |

Gate passes: entity, predicate, and outcome are all concrete.

## L0: Question Type

- [x] Descriptive — "does the indexing function, as changed, cover the actual file layout it is run against, and does it skip re-embedding an unchanged corpus?"
- [ ] Predictive
- [ ] Causal

This is a software-correctness claim about a deterministic function, not a
population estimate — no estimand.md / DAG is applicable (see TZ §2 Non-goals).

## Natural Language Statement

> We claim that `rebuild_index()`, after the PR-1 change, indexes every
> Markdown note under `wiki/` recursively (including PARA sub-directories),
> excludes `daily/` notes and index/chunk files exactly as before, and skips
> re-indexing entirely when the corpus fingerprint (SHA-256 over sorted
> `rel_path:size:mtime_ns` tuples, stored in a sidecar file) is unchanged.

## Claim Entropy

| Component | Count |
|---|---|
| Unsupported HIGH claims | 0 |
| Hidden assumptions | 0 — fingerprint sidecar is a separate file, never a key inside `tf_index.json` (this was the concrete crash risk Codex's review on PR #332 caught and this code already avoids) |
| Missing negative controls | 0 — see controls.md |
| Ambiguous definitions | 0 — "PARA sub-directory" = any directory under `wiki/` reachable by `rglob("*.md")` except `daily/` |
| Unresolved blockers | 0 |
| **Total claim_entropy** | **0** |

## What This Result Does NOT Mean

1. Does NOT mean semantic (dense-vector) search finds these notes with any
   particular ranking quality — that is PR-5's scope (HOT-tier scoring fix),
   gated by §5.3 of the TZ.
2. Does NOT mean the TF-IDF weights themselves are statistically correct
   across the whole corpus after an incremental add — that is PR-4's scope
   (real, corpus-wide IDF, applied at search time).
3. Does NOT establish anything about `knowledge_librarian.py`'s HOT/WARM/COLD
   tiering — PR-1 touches only `vector_store.py` and `raw_to_wiki.py`'s call
   site.

---

## PR-2 sub-claim — `rel_path` is the real join key (fixes 0.2)

**Entity:** `vector_store.index_wiki_entry()`/`semantic_search_paths()`,
`raw_to_wiki.update_wiki_index()`, `knowledge_librarian._score_entry()`/
`_read_wiki_content()`/`_classify_and_render_wiki()`.

**Falsifiable predicate:** an entry whose H1 title differs from its filename
stem (the normal case — dated slugs) can be opened by the HOT-tier renderer;
two files sharing an identical H1 title no longer collide in either the
vector index or the HOT-tier file lookup.

**Measurable outcome:** the exact `_read_wiki_content("AUC Red Flags") ->
None` reproduction from §0.2 now returns real content when the candidate
carries `[[rel_path|Title]]`; two `WikiRef`s sharing a title both index and
both retrieve their own distinct content.

**Natural language statement:** we claim that after PR-2, `rel_path` (not
`title`) is the real lookup key everywhere in the retrieval chain — Chroma
`ids`, the TF-IDF JSON key, and the HOT-tier file open — and `title` is
carried only as display metadata.

**What this does NOT mean:** does not fix stale-entry deletion (0.4, still
PR-3's scope — during the transition, old title-keyed TF entries from
pre-PR-2 runs may still linger in `tf_index.json` until a rebuild under
PR-3's atomic-clear logic removes them; `semantic_search_paths()` defensively
skips any entry missing the new `{"title", "vector"}` wrapper shape rather
than crashing on it). Does not change ranking quality (PR-4/PR-5).

---

## PR-4 sub-claim — real corpus-wide TF-IDF, not TF-only (fixes 0.5)

**Entity:** `vector_store.rebuild_index()`'s TF backend write path (which
computes a corpus-wide IDF sidecar, `idf_weights.json`, alongside the
unchanged plain-TF document write), `semantic_search_paths()`'s TF-IDF
fallback (which applies that idf to both sides at search time), and
`index_wiki_entry()`'s single-entry TF write path (which must keep the idf
sidecar from silently going stale relative to the corpus it describes).

**Falsifiable predicate:** a document containing a corpus-rare term ranks
above a document matching only a corpus-common term, even when the query
is weighted heavily toward the common term — a ranking real IDF produces
and plain TF does not. A note added via `index_wiki_entry()` containing a
term never seen by the last rebuild is findable by that term immediately,
not only after the next full `rebuild_index()`.

**Measurable outcome:** `test_rare_term_outranks_common_term_under_real_idf`
— the exact ranking is asserted with real, smoothed IDF applied AND
asserted to be the OPPOSITE under plain TF (proving the effect is real,
not incidental). `test_adding_one_document_reweights_every_existing_document`
— adding one document changes the corpus-wide idf weight for a term shared
by every PRE-EXISTING document, and the EFFECTIVE (search-time) weighting
applied to both pre-existing documents' unchanged raw vectors — proving the
reweight is a genuine whole-corpus operation, not a per-document patch
(which is mathematically impossible for real IDF — see
`_compute_corpus_idf()`'s own WHY comment). A new OOV-regression test
covers a note added via `index_wiki_entry()` being findable immediately by
a term absent from the last rebuild's idf.

**Natural language statement:** we claim that after PR-4, documents on disk
(`tf_index.json`) are, and remain, plain TF — unchanged in shape and
semantics from before this PR. A separate sidecar (`idf_weights.json`)
holds real, smoothed corpus-wide IDF (`log((n+1)/(df+1))+1`, floored at 1.0,
never exactly 0), computed exactly once per `rebuild_index()` call over the
whole freshly-built document set. `semantic_search_paths()` applies that
SAME idf, freshly and symmetrically, to BOTH the query vector and every
document vector at search time — never at index time — so the two sides
can never desynchronize: either both get real idf (sidecar present and
non-empty) or both fall back to plain TF (sidecar absent or empty).
`index_wiki_entry()`'s single-entry write path deletes the idf sidecar and
invalidates the corpus fingerprint on success, so a newly-added term is
never left permanently invisible behind an idf sidecar that predates it —
the corpus falls back to a consistent plain-TF state (including the new
note) until the next `rebuild_index()` call restores real idf.

**Design history — an earlier, superseded version of this claim, recorded
here rather than silently overwritten:** the first implementation of this
PR computed idf once per rebuild and REWEIGHTED `tf_index.json`'s stored
vectors in place, persisting the IDF-weighted result. CI, and separately an
externally-pasted review and the GitHub Codex bot, all independently
confirmed this was wrong in two ways: (1) the un-smoothed formula
`log(n/df)` gave every term in a single-document corpus (or any corpus
where a term appears in every document) exactly 0 weight, making such
documents permanently unsearchable; (2) baking idf into stored documents
meant the idf sidecar and the document index had to agree across two
separate file writes, which a partial write failure could break, producing
SILENTLY WRONG rankings (reproduced: an irrelevant document scored 0.949,
the relevant one 0.316). Both are fixed by the redesign this claim now
describes: smoothed idf, and idf applied only at search time, never baked
into storage. See `decision.md`'s PR-4 § Skeptic Concerns for the full
verification trail.

**Design deviation from the TZ, stated explicitly:** the TZ's own draft
schema nests `corpus_fingerprint`/`idf`/`documents` inside one JSON object
at `tf_index.json`'s root. Implemented instead: `idf` lives in its own
sidecar file (`idf_weights.json`), and `tf_index.json` keeps its existing
flat `{rel_path: {"title","vector"}}` shape unchanged. This delivers the
identical observable behavior (real corpus-wide IDF, applied to both
documents and queries) without rewriting `_load_tfidf_index()`/
`_save_tfidf_index()` to understand a wrapper shape, which would have
touched roughly 30 existing tests that assert on the current flat shape
for no functional gain. Same pattern as PR-2's documented `WikiRef`-
signature deviation. `corpus_fingerprint.txt` is NOT retired into this new
file in this PR (the TZ's stated follow-on tidy-up, not the falsifiable
core claim) — deferred, not silently dropped; recorded in decision.md.

**What this does NOT mean:** does not change what backend is selected
(PR-1/PR-2/PR-3's fingerprint-gate logic, untouched). Does not wire
`semantic_search_paths()` into the production HOT-tier path — that remains
PR-5's scope, gated by §5.3. Does not give `index_wiki_entry()` an `idf`
parameter — that design was explicitly rejected by the TZ itself (real
corpus-wide IDF cannot be computed correctly per-document; an earlier draft
proposing this was corrected before implementation began, per Codex review
on PR #332). Does not change ranking for the ChromaDB backend at all (IDF
only applies to the TF-IDF fallback path; Chroma's dense embeddings are a
different representation entirely). Does not fix PR-3's own stale/failed-
entry-deletion availability gap (a file that exists but fails to parse this
run loses its old entry until the next successful rebuild) — investigated
during PR-4's review but out of scope; tracked as a separate follow-on PR
per `decision.md`.

---

## PR-3 sub-claim — atomic, reported rebuild (fixes 0.4)

**Entity:** `vector_store.rebuild_index()`'s write path, for both the TF-IDF
and Chroma backends.

**Falsifiable predicate:** a wiki file that is deleted or renamed no longer
appears as a search hit after the next `rebuild_index()` call, in EITHER
backend; a per-file failure during a rebuild (e.g. an unreadable file) does
not prevent the other, successfully-parsed files in the same run from being
correctly indexed.

**Measurable outcome:** index A+B, delete B's file, rebuild — B's terms
return no hits and B's key is absent from the index (both backends,
independently tested). Index three files, make one unreadable mid-rebuild —
the other two are still indexed and searchable, and `RebuildReport.failed`
reflects exactly the one broken file, not zero and not three failures.

**Natural language statement:** we claim that after PR-3, `rebuild_index()`
builds a complete in-memory batch first (tolerating per-file failures), then
performs one atomic write, and only removes now-absent entries after that
write succeeds — so a partial or failed rebuild never leaves the index worse
than it started (an empty or half-cleared index), and a fully successful
rebuild always reflects exactly the current file set, with no stale
leftovers.

**What this does NOT mean:** does not change what gets indexed (still
`glob`→`rglob`'d files under `wiki/`, PR-1's scope) or how entries are keyed
(`rel_path`, PR-2's scope). Does not address real TF-IDF weighting (PR-4) or
production wiring of semantic search (PR-5). The concurrency lock added
around the TF-IDF batch write closes a *theoretical* race with a concurrent
`index_wiki_entry()` call — `index_wiki_entry()` has no production caller
after this PR (only `rebuild_index()`'s own internal logic and tests use the
write path now), so this is defense-in-depth, not a fix for an observed
production race.

---

## PR-3 follow-up sub-claim — last-known-good on a persistent parse failure

**Context:** PR-4's own review (Round 3, see `decision.md`'s PR-4 § Skeptic
Concerns) re-examined PR-3's stale/failed-entry-deletion behavior and
accepted a real refinement of it, deliberately kept out of PR-4 to avoid
bloating an already-large PR. This is that follow-on, landing after PR-4
merged (main commit `9b1e2ed`) and before PR-5.

**Entity:** `vector_store.rebuild_index()`'s TF-IDF write path (the
`old_index`/`tf_batch` merge step immediately before the atomic replace).

**Falsifiable predicate:** a file that exists on disk but fails to parse
across MULTIPLE CONSECUTIVE `rebuild_index()` calls keeps its last-known-
good index entry (and stays findable by that entry's content) for as long
as the failure recurs; a file that is genuinely deleted (or newly excluded)
still has its entry removed, exactly as PR-3 already established.

**Measurable outcome:**
`test_repeatedly_failing_file_keeps_last_known_good_entry` — index two
files, then make one of them fail to parse across TWO consecutive rebuilds
(not just one): its entry must survive both, `RebuildReport.deleted` must
be 0 on both runs (not counting a still-existing-but-failed file as
deleted), and the file must remain findable by its own content via
`semantic_search_paths()`. Then delete the file for real: its entry must
finally be removed and `deleted` must become 1.

**Natural language statement:** we claim that after this follow-up,
`rebuild_index()`'s TF-IDF write distinguishes three outcomes per file,
not two: (1) file physically absent from the current corpus (deleted,
renamed, or newly excluded) → its old entry is removed; (2) file present
but failed to parse THIS run → its old entry is KEPT unchanged
("last-known-good"), and its terms still count toward the corpus-wide IDF
computed for this run (it is still part of the searchable corpus); (3)
file parsed successfully → its entry is replaced with the fresh one.
Before this follow-up, outcomes (1) and (2) were conflated — any file
absent from this run's successfully-parsed batch had its entry dropped,
whether the file was gone or merely temporarily unparseable.

**Design history — what PR-3 originally got right, and the one thing it
missed:** PR-3's own claim (above) is still true and unchanged by this
follow-up — a single transient failure genuinely doesn't corrupt the
index, and (an unrelated, pre-existing mechanic) `rebuild_index()` never
caches the fingerprint after any per-file failure, forcing the very next
call to retry unconditionally. What PR-3 did not account for: "the next
call retries" is not the same as "the next call succeeds." If the SAME
file keeps failing — not a one-run blip but a recurring condition (a
consistently malformed file, a permissions issue that isn't transient) —
the file's entry was dropped on the FIRST failure and never came back
until a run where that specific file happened to parse. Verified by
reproduction: a file made to fail parsing on two consecutive runs lost
its entry after the first and stayed absent through the second, under
the pre-follow-up code.

**What this does NOT mean:** does not change what counts as "genuinely
deleted" (still: absent from `_iter_indexable_files(wiki_dir)`'s current
result, PR-1's scope). Does not change the Chroma backend's stale-entry
deletion (PR-3's `collection.delete(ids=stale_ids)` path, unaffected —
Chroma's per-document `upsert`/`delete` semantics don't have the same
flat-replace-drops-everything-not-in-the-batch failure mode the TF-IDF
backend's `_save_tfidf_index()` does). Does not change IDF correctness
(PR-4's scope) beyond the one accuracy improvement noted above (idf is
now computed over the FULL merged corpus, including kept-stale entries,
not just this run's freshly-parsed batch — a strictly more accurate
corpus-wide document-frequency count). Does not make last-known-good
retention permanent or unconditional — a genuinely deleted file's entry
is still removed exactly as before; only a file that still EXISTS but
merely failed to parse keeps its old entry.
