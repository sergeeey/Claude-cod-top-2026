"""Local vector store for wiki semantic search.

WHY: keyword grep in knowledge_librarian misses synonyms and related concepts.
vector_store provides semantic fallback: when fewer than 3 keyword matches are
found, it falls back to cosine similarity over TF-IDF (stdlib-only, zero deps).
Optional ChromaDB + sentence-transformers upgrade for higher-quality embeddings.

Architecture:
  - Primary:  ChromaDB + sentence-transformers (optional, local, no API cost)
  - Fallback: real TF-IDF cosine similarity (pure stdlib, JSON-backed index)
  - All public functions are fail-open: return [] / no-op on any exception.

WHY "real TF-IDF," named precisely (memory-retrieval-repair-tz.md PR-4,
fixes 0.5): `index_wiki_entry()` (the per-document write path) computes
plain TF only, by necessity -- corpus-wide IDF is a property of the WHOLE
corpus and cannot be computed correctly for one document in isolation
(adding, removing, or editing even one document changes it for every OTHER
document too). Real IDF is computed and applied exactly once per rebuild,
as a second pass inside `rebuild_index()` after every document's TF vector
is already built -- see that function's own WHY comment. `tf_index.json`
therefore stores real TF-IDF-weighted vectors once a rebuild has run under
this PR; `semantic_search_paths()`'s TF-IDF fallback applies the SAME idf
weights to the query before comparing, via the `idf_weights.json` sidecar.

Index location: _VECTOR_DB_DIR (monkeypatchable for tests).
"""

import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from lib.state import file_lock
from lib.wiki_types import RebuildReport, SearchHit, WikiRef

# WHY: module-level constant = monkeypatchable in tests (same pattern as
# cogniml_client._PUSHED_LEDGER). Never hardcode ~/.claude inside a function
# that tests can't redirect.
_VECTOR_DB_DIR: Path = Path.home() / ".claude" / "cache" / "vector_db"
_TFIDF_INDEX_FILE = "tf_index.json"
_FINGERPRINT_FILE = "corpus_fingerprint.txt"
# WHY a SEPARATE sidecar file, not a root-level key inside tf_index.json
# (memory-retrieval-repair-tz.md PR-4, fixes 0.5): the TZ's own draft
# schema nested corpus_fingerprint/idf/documents inside one JSON object --
# but _load_tfidf_index()/_cosine() treat every top-level key of
# tf_index.json as a document vector (exactly the shape PR-1's Codex
# review already caught once for the fingerprint). Rewriting those
# functions to understand a wrapper shape would touch ~30 existing tests
# that assert on the flat {rel_path: {"title","vector"}} shape for no
# functional gain -- a small dedicated sidecar delivers the identical
# observable behavior (real corpus-wide IDF applied to both documents and
# queries) with far less blast radius. Documented deviation from the TZ's
# literal schema, same pattern as PR-2's WikiRef-signature deviation.
_IDF_FILE = "idf_weights.json"
# WHY a bare version string, not a key inside tf_index.json (P2, Codex
# review on PR #334): see _corpus_fingerprint()'s own WHY comment. "1" =
# PR-1 shape (title-keyed, flat {token: weight} values). "2" = PR-2 shape
# (rel_path-keyed, {"title", "vector"} wrapped values). "3" = PR-4 (fixes
# 0.5): a separate corpus-wide IDF sidecar (idf_weights.json) now exists
# and is applied at search time -- stored document vectors THEMSELVES stay
# plain TF, unchanged in shape from "2" (an earlier version of this PR
# bumped this because it baked idf into stored vectors; redesigned after
# that was found to desynchronize from the sidecar under a partial write
# failure -- see decision.md). Bumped anyway so an installation upgrading
# from a "2" index gets a full rebuild, which is what actually populates
# the new idf sidecar for the first time (a "2" installation has no
# idf_weights.json at all, not a stale one). Bump this whenever
# index_wiki_entry()'s TF-IDF value shape (or its weighting semantics)
# changes again.
_TF_SCHEMA_VERSION = "3"
# WHY excluded from the corpus (memory-retrieval-repair-tz.md PR-1): matches
# _query_wiki_raw_titles()'s own exclusion list exactly -- daily/ is a
# temporal log, not a knowledge entry, and both scanners must agree on what
# "the corpus" means or PR-1's fingerprint (computed here) and the actual
# search corpus (scanned in knowledge_librarian.py) silently diverge.
_EXCLUDED_DIR_NAMES = frozenset({"daily"})
# WHY (MEDIUM, cross-model audit): index_wiki_entry() does a load-mutate-
# save on the TF-IDF index with no locking, so concurrent indexing of
# DIFFERENT wiki entries can lose each other's updates to last-writer-wins.
# _save_tfidf_index() also previously wrote directly via write_text() (not
# even atomic for a single write) -- switched to tmp+os.replace to match
# the pattern used elsewhere in this repo (doc_registry.py, etc).

# WHY: F12 — cap entries to prevent unbounded growth of TF-IDF index file
MAX_INDEX_ENTRIES = 5000

# Stopwords to skip during tokenisation (common EN + RU words)
_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "it",
        "in",
        "on",
        "at",
        "to",
        "of",
        "for",
        "and",
        "or",
        "but",
        "not",
        "be",
        "are",
        "was",
        "were",
        "with",
        "this",
        "that",
        "from",
        "by",
        "as",
        "if",
        "when",
        "than",
        "into",
        "over",
        "так",
        "это",
        "что",
        "как",
        "для",
        "при",
        "не",
        "или",
        "и",
        "в",
        "на",
        "по",
        "из",
        "до",
        "за",
        "от",
        "со",
        "без",
        "под",
        "над",
    }
)


# ---------------------------------------------------------------------------
# Tokenisation (stdlib-only, shared by both backends)
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Lowercase, split on non-word chars, remove stopwords and short tokens."""
    tokens = re.findall(r"[a-zA-Zа-яА-Я0-9_]+", text.lower())
    return [t for t in tokens if len(t) > 2 and t not in _STOPWORDS]


# ---------------------------------------------------------------------------
# TF-IDF index (pure stdlib, JSON-backed)
# ---------------------------------------------------------------------------


def _tfidf_index_path() -> Path:
    return _VECTOR_DB_DIR / _TFIDF_INDEX_FILE


def _tfidf_lock_path() -> Path:
    return _tfidf_index_path().with_suffix(".lock")


def _load_tfidf_index() -> dict[str, dict[str, Any]]:
    """Load {rel_path: {"title": str, "vector": {term: tfidf}}} from disk.

    WHY dict[str, Any] for the value, not dict[str, float] (PR-2): the
    value is now a small wrapper carrying display title alongside the
    term-weight vector, not a flat vector -- see index_wiki_entry()'s WHY
    comment for the reasoning. Returns {} on any error.
    """
    path = _tfidf_index_path()
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data  # type: ignore[return-value]
    except Exception:
        pass
    return {}


def _save_tfidf_index(index: dict[str, dict[str, Any]]) -> bool:
    """Persist TF-IDF index to disk. Fail-open. Trims to MAX_INDEX_ENTRIES.

    WHY tmp+os.replace, not a direct write_text() (MEDIUM, cross-model
    audit): a direct write_text() isn't atomic even for a single write --
    a crash mid-write leaves a truncated/corrupt index. Matches the
    tmp-file+os.replace pattern already used elsewhere in this repo.

    WHY return bool, not None (P1, reviewer-agent finding on
    memory-retrieval-repair-tz.md PR-1): index_wiki_entry() needs to tell
    rebuild_index() whether the save actually succeeded, without this
    function abandoning its own fail-open contract (it still never raises).
    """
    try:
        # WHY: F12 — trim if too large; simple LRU (Python dict preserves insertion order)
        if len(index) > MAX_INDEX_ENTRIES:
            keys = list(index.keys())[-MAX_INDEX_ENTRIES:]
            index = {k: index[k] for k in keys}
        _VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
        dest = _tfidf_index_path()
        tmp = dest.with_suffix(".tmp")
        tmp.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
        # WHY retry on PermissionError: same benign Windows os.replace()
        # race documented in doc_registry.py/expert_registry.py -- an
        # unlocked reader (semantic_search()) can transiently collide with
        # a concurrent locked writer's rename.
        last_exc: PermissionError | None = None
        for attempt in range(5):
            try:
                os.replace(str(tmp), str(dest))
                return True
            except PermissionError as exc:
                last_exc = exc
                if attempt < 4:
                    time.sleep(0.02 * (attempt + 1))
        raise last_exc  # type: ignore[misc]
    except Exception as exc:
        # WHY warn (P2, reviewer-agent parity note): retry exhaustion here
        # previously vanished silently -- the caller's own except block
        # (index_wiki_entry) can't see it either, since this function
        # already swallows it at this level. Still fail-open, just no
        # longer silent.
        print(f"[vector-store] WARNING: failed to save TF-IDF index: {exc}", file=sys.stderr)
        return False


def _compute_tf_normalized(tokens: list[str]) -> dict[str, float]:
    """Compute L2-normalised term frequency for a token list. TF only.

    WHY named TF, not TF-IDF (memory-retrieval-repair-tz.md PR-4, fixes
    0.5): this function computes ONE document's (or one query's) term
    frequency in isolation -- IDF requires corpus statistics across every
    document, which this function structurally cannot see. Real corpus-
    wide IDF is computed once per rebuild by `_compute_corpus_idf()` and
    applied via `_apply_idf()`, both in this same file -- see
    `rebuild_index()`'s TF branch for where that happens. This function's
    plain-TF output is the correct, honest input to that second pass, not
    a placeholder for a "future" IDF that was previously described here as
    not yet implemented.
    """
    if not tokens:
        return {}
    freq: dict[str, int] = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    total = len(tokens)
    tf = {t: c / total for t, c in freq.items()}
    # L2 normalise
    norm = math.sqrt(sum(v * v for v in tf.values())) or 1.0
    return {t: v / norm for t, v in tf.items()}


def _cosine(v1: dict[str, float], v2: dict[str, float]) -> float:
    """Dot product of two L2-normalised dicts (both are already unit vectors)."""
    if not v1 or not v2:
        return 0.0
    # Use smaller dict for iteration speed
    small, large = (v1, v2) if len(v1) <= len(v2) else (v2, v1)
    return sum(val * large.get(t, 0.0) for t, val in small.items())


def _l2_normalize(vec: dict[str, float]) -> dict[str, float]:
    """Re-normalize a term-weight dict to unit L2 length.

    WHY return {} for an all-zero vector, not raise (memory-retrieval-
    repair-tz.md PR-4): a document whose every term has IDF weight 0 (every
    term it contains also appears in every other document -- maximally
    uninformative relative to this corpus) has nothing left to normalize.
    {} is the correct degenerate case: _cosine() already returns 0.0 for an
    empty dict, so such a document correctly never matches any query.
    """
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0.0:
        return {}
    return {t: v / norm for t, v in vec.items()}


def _apply_idf(vec: dict[str, float], idf: dict[str, float]) -> dict[str, float]:
    """Multiply each term's TF weight by its corpus-wide IDF, then re-normalize.

    WHY both sides of a cosine comparison need the SAME idf weighting
    (memory-retrieval-repair-tz.md PR-4, fixes 0.5): real TF-IDF cosine
    similarity is undefined if only the documents are IDF-weighted and the
    query stays plain TF. This function is applied to BOTH the query vector
    and every document vector, freshly, in the SAME call to
    semantic_search_paths() at search time, using the SAME idf dict loaded
    once per search -- never at index time (an earlier version of this PR
    applied it once to documents inside rebuild_index() and persisted the
    result; redesigned after that was found to desynchronize from the idf
    sidecar under a partial write failure, producing silently wrong
    rankings -- see decision.md). A term absent from `idf` (out-of-
    vocabulary relative to the LAST REBUILT corpus) gets weight 0 -- this is
    only safe as long as a stale-but-incomplete idf never lingers next to a
    corpus it doesn't fully describe; see index_wiki_entry()'s own WHY
    comment for how a single-entry write keeps that invariant.
    """
    weighted = {t: w * idf.get(t, 0.0) for t, w in vec.items()}
    return _l2_normalize(weighted)


def _compute_corpus_idf(vectors: list[dict[str, float]]) -> dict[str, float]:
    """Compute real corpus-wide IDF: log((n+1)/(df+1)) + 1 per term, from
    the freshly-built TF vectors of every document this run.

    WHY this can only ever run as a whole-corpus operation, never
    incrementally (memory-retrieval-repair-tz.md PR-4, Codex review on
    PR #332, P1 -- an earlier draft's `idf` parameter design was wrong, not
    just incomplete): adding, removing, or editing even one document
    changes N (the document count) and every term's document frequency,
    which invalidates the stored IDF weight of every OTHER document already
    in the index, not just the one being written. There is no safe
    incremental update; this is why IDF is computed here, inside
    rebuild_index()'s whole-corpus write path, and nowhere else --
    index_wiki_entry() stays TF-only and untouched by this PR.

    WHY smoothed (log((n+1)/(df+1)) + 1), not plain log(n/df) (real bug,
    caught by CI after this PR's own review cycle was closed by the
    Evaluator-Optimizer Guard, verified with a tool before applying this
    fix): plain IDF is EXACTLY 0 whenever a term's document frequency
    equals the document count (df==n) -- which is trivially true for
    EVERY term in a single-document corpus (df=1=n for all of them). That
    zeroes the entire document vector, making it permanently unmatchable
    via TF-IDF cosine similarity -- confirmed by reproduction: a real
    single-document wiki (the normal case for a small or brand-new
    knowledge base) became completely unsearchable. This is the exact
    smoothing scikit-learn's TfidfVectorizer uses by default
    (`smooth_idf=True`): `(n+1)/(df+1)` is always >= 1, so `log(...) >= 0`,
    and the `+ 1` guarantees idf >= 1 for every term that appears in the
    corpus at all -- no term is EVER assigned exactly zero weight anymore,
    while rarer terms still correctly score higher than common ones.
    """
    n = len(vectors)
    if n == 0:
        return {}
    doc_freq: dict[str, int] = {}
    for vec in vectors:
        for term in vec:
            doc_freq[term] = doc_freq.get(term, 0) + 1
    return {term: math.log((n + 1) / (df + 1)) + 1.0 for term, df in doc_freq.items()}


# ---------------------------------------------------------------------------
# ChromaDB backend (optional upgrade)
# ---------------------------------------------------------------------------


def _get_chroma_collection():  # type: ignore[return]
    """Return ChromaDB collection or None if not installed / unavailable."""
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(_VECTOR_DB_DIR / "chroma"))
        return client.get_or_create_collection("wiki")
    except Exception:
        return None


def _get_embedder():  # type: ignore[return]
    """Return SentenceTransformer model or None if not installed."""
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def index_wiki_entry(ref: WikiRef, body: str, tags: list[str] | None = None) -> bool:
    """Add or update a wiki entry in the vector index.

    Tries ChromaDB + sentence-transformers first; falls back to TF-IDF.
    Always fail-open (never raises) -- but now reports whether it actually
    succeeded.

    WHY ref: WikiRef, not title: str (memory-retrieval-repair-tz.md PR-2,
    fixes 0.2): the index previously keyed everything by `title`
    (`ids=[title]` for Chroma, `index[title] = vec` for TF-IDF), while the
    file on disk is looked up by filename -- two files sharing an H1 title
    collided, and HOT-tier rendering could not open the file it just
    matched whenever title != filename stem (the normal case for dated
    slugs). `ref.rel_path` is now the real key everywhere; `ref.title` is
    carried as display metadata only, never a lookup key.

    WHY return bool, not None (P1, reviewer-agent finding on PR-1): this
    function's own internal try/except previously swallowed every failure
    (lock timeout, TF-IDF save failure) before it could reach
    rebuild_index()'s except-block -- so `RebuildReport.failed`, added by
    that PR specifically to make indexing failures visible, could never
    actually see one. Fail-open behavior (never raise) is unchanged; only
    the ability to report success/failure to the caller is new.

    WHY a successful TF-IDF write here deletes the idf sidecar and
    invalidates the corpus fingerprint (memory-retrieval-repair-tz.md PR-4
    follow-up, externally-pasted review, verified by reproduction): this
    function indexes exactly one document and never sees the rest of the
    corpus, so it cannot compute a real, complete corpus-wide IDF -- the
    existing idf sidecar (from the last rebuild_index() call) does not
    know about any term unique to this new document. Rather than leave
    that sidecar in place (which would make the new document unsearchable
    by its own distinctive terms until the next full rebuild), both the
    sidecar and the fingerprint are invalidated, forcing a consistent
    plain-TF state for the WHOLE corpus (including this new document)
    until the next rebuild_index() call restores real idf.

    Args:
        ref: WikiRef(rel_path, title) -- rel_path is the real join key.
        body: Full markdown body of the wiki entry.
        tags: Optional list of tags (appended to body for better matching).

    Returns:
        True if the entry was actually indexed (ChromaDB or TF-IDF), False
        on any failure (already logged to stderr).
    """
    try:
        combined = f"{ref.title}\n{body}\n{' '.join(tags or [])}"

        # --- ChromaDB path ---
        collection = _get_chroma_collection()
        if collection is not None:
            embedder = _get_embedder()
            if embedder is not None:
                embedding = embedder.encode(combined).tolist()
                collection.upsert(
                    ids=[ref.rel_path],
                    documents=[combined],
                    embeddings=[embedding],
                    metadatas=[{"title": ref.title, "tags": ",".join(tags or [])}],
                )
                return True  # success via ChromaDB

        # --- TF fallback (memory-retrieval-repair-tz.md PR-4: this
        # function stays plain-TF, never IDF-reweighted -- see its own WHY
        # comment above for why real IDF cannot be computed per-document) ---
        tokens = _tokenize(combined)
        vec = _compute_tf_normalized(tokens)
        # WHY lock (MEDIUM, cross-model audit): concurrent indexing of
        # DIFFERENT wiki entries previously raced on this load-mutate-save,
        # so one indexed entry could silently erase another.
        # WHY timeout=15.0 + acquired-check (real bug, found by a cross-file
        # concurrency test): file_lock()'s default 2.0s timeout yields False
        # rather than raising on timeout -- a bare `with file_lock(...):`
        # still enters the block unprotected. Raising here is safe: this
        # whole function is already wrapped in the fail-open try/except
        # below, so a genuine timeout is treated the same as any other
        # indexing failure (reported via the False return), not silent
        # corruption.
        with file_lock(_tfidf_lock_path(), timeout=15.0) as acquired:
            if not acquired:
                raise TimeoutError(f"Could not acquire vector_store lock: {_tfidf_lock_path()}")
            index = _load_tfidf_index()
            # WHY a {"title", "vector"} wrapper, not a flat {token: weight}
            # dict keyed straight off ref.rel_path (PR-2): the legacy
            # semantic_search() -> list[str] contract (kept for its existing
            # unit tests) must still return display titles, and the
            # rel_path key alone can't recover one without re-reading the
            # source file, which vector_store.py has no wiki_dir to do at
            # search time. Kept as a per-entry wrapper, not a second
            # top-level index, to avoid PR-1's own fingerprint-key lesson
            # (a stray root-level key gets misread as a document vector).
            index[ref.rel_path] = {"title": ref.title, "vector": vec}
            saved = _save_tfidf_index(index)
            if saved:
                # WHY delete the idf sidecar and invalidate the fingerprint
                # on a successful single-entry write (real bug, verified by
                # reproduction, externally-pasted review): the idf sidecar
                # is a snapshot of the corpus as of the LAST rebuild_index()
                # call. A term that appears only in the note just added
                # (e.g. "quantumtelemetry") is absent from that snapshot,
                # so _apply_idf() -- correctly, by its own contract -- gives
                # it weight 0 as an out-of-vocabulary term. A query for
                # that exact term then weights every one of its terms to 0,
                # `semantic_search_paths()` returns [] before it ever
                # reaches this brand-new, otherwise-matching document.
                # Deleting the sidecar forces the empty-idf-falls-back-to-
                # plain-TF path (already implemented, see
                # test_empty_idf_sidecar_falls_back_to_plain_tf) for EVERY
                # document, including this new one, until the next
                # rebuild_index() call restores a real, complete idf.
                # Invalidating the fingerprint too ensures that next call
                # actually happens rather than being skipped as "unchanged"
                # (rebuild_index()'s fingerprint is a pure function of file
                # stats, which this single-entry write doesn't change).
                _delete_idf_sidecar()
                _invalidate_fingerprint()
            return saved
    except Exception as exc:
        # WHY warn (P2, reviewer-agent parity note): the other 4 files in
        # this same audit batch (doc_registry/expert_registry/moc_autolink/
        # observation_capture) all warn to stderr on their lock/save
        # failure path -- this one silently swallowed it. Still fail-open
        # (indexing failure must not interrupt the session), just no
        # longer silent.
        print(f"[vector-store] WARNING: failed to index {ref.rel_path!r}: {exc}", file=sys.stderr)
        return False


def semantic_search_paths(query: str, top_k: int = 3) -> list[SearchHit]:
    """Find the most semantically similar wiki entries for a query.

    WHY this is the real entry point, not semantic_search() (PR-2): a
    title-only result can't be opened for HOT-tier rendering (0.2) and
    can't disambiguate two files sharing an H1 title. Returns SearchHit,
    each carrying the WikiRef (rel_path + title) the caller needs to
    actually read the file, plus a score tagged by which backend found it.

    Tries ChromaDB first; falls back to TF-IDF cosine similarity.
    Returns [] on any error.

    Args:
        query: Free-text search string (e.g. user prompt keywords).
        top_k: Maximum number of results to return.
    """
    if not query or top_k <= 0:
        return []
    try:
        # --- ChromaDB path ---
        collection = _get_chroma_collection()
        if collection is not None:
            embedder = _get_embedder()
            if embedder is not None:
                embedding = embedder.encode(query).tolist()
                results = collection.query(
                    query_embeddings=[embedding],
                    n_results=min(top_k, collection.count() or 1),
                )
                ids = results.get("ids", [[]])[0]
                metadatas = results.get("metadatas", [[]])[0]
                distances = results.get("distances", [[]])[0]
                hits = []
                for i, rel_path in enumerate(ids[:top_k]):
                    meta = metadatas[i] if i < len(metadatas) else {}
                    title = meta.get("title", rel_path) if isinstance(meta, dict) else rel_path
                    # WHY 1/(1+distance), not a precisely calibrated
                    # similarity (PR-2 note, revisited by PR-5): Chroma's
                    # distance metric is backend-config-dependent (L2 by
                    # default) -- this is a monotonic proxy (closer =
                    # higher score) good enough for ranking, not a value
                    # directly comparable to the TF-IDF cosine score below.
                    # Real HOT-tier calibration is PR-5's job (0.3), gated
                    # by the TZ's own §5.3 floor-ceiling measurement.
                    dist = distances[i] if i < len(distances) else 0.0
                    score = 1.0 / (1.0 + max(dist, 0.0))
                    hits.append(
                        SearchHit(ref=WikiRef(rel_path, title), score=score, source="dense")
                    )
                return hits

        # --- TF-IDF fallback ---
        index = _load_tfidf_index()
        if not index:
            return []

        query_vec = _compute_tf_normalized(_tokenize(query))
        if not query_vec:
            return []
        # WHY idf is applied fresh to BOTH the query AND each document HERE,
        # at search time, rather than being baked into the stored document
        # vectors at index time (memory-retrieval-repair-tz.md PR-4, fixes
        # 0.5 -- redesigned after CI caught a real bug in the first version:
        # baking IDF into stored documents meant a query and the documents
        # it's compared against could desynchronize -- e.g. if the idf
        # sidecar and tf_index.json ever fell out of sync -- producing
        # silently WRONG rankings, not just missing results, verified by
        # hand: an identical query/document pair went from a correct 1.0
        # cosine score to a wrong ~0.32 with a genuinely irrelevant document
        # OUTRANKING the relevant one). Documents in `index` are ALWAYS
        # plain TF on disk now (identical to what index_wiki_entry() itself
        # produces); idf is applied identically to both sides right here,
        # so the two can never desynchronize -- either both get real idf
        # (sidecar present, non-empty) or both stay plain TF (sidecar
        # absent/empty), never a mix of the two.
        idf = _load_idf()
        weighted_query = _apply_idf(query_vec, idf) if idf else query_vec
        if not weighted_query:
            return []

        scored: list[tuple[float, str, str]] = []
        for rel_path, entry in index.items():
            # WHY isinstance(entry.get("vector"), dict), not "vector" not in
            # entry (P1, isolated reviewer-agent finding on PR-2): a
            # presence check is not a shape check -- a pre-PR-2 legacy flat
            # {token: weight} entry that happens to contain the literal
            # term "vector" (very plausible in THIS repo's own wiki notes
            # about vector_store) would pass a bare "vector" not in entry
            # check, then hand _cosine() a float instead of a dict, which
            # crashes on `len()` inside the loop -- the exception escapes
            # to the OUTER try/except and blanks the ENTIRE search result
            # for that query, not just skips the one bad entry. Verified by
            # reproduction (float value under a "vector" key raises
            # TypeError in _cosine) before applying this fix.
            if not isinstance(entry, dict) or not isinstance(entry.get("vector"), dict):
                continue
            weighted_doc = _apply_idf(entry["vector"], idf) if idf else entry["vector"]
            sim = _cosine(weighted_query, weighted_doc)
            if sim > 0:
                scored.append((sim, rel_path, entry.get("title", rel_path)))

        scored.sort(key=lambda x: x[0], reverse=True)
        # WHY source="keyword", not "dense": TF-IDF cosine similarity is a
        # sparse lexical representation (bag-of-tokens), the fallback used
        # when Chroma's dense neural embeddings aren't available -- "dense"
        # is reserved for the ChromaDB branch above.
        return [
            SearchHit(ref=WikiRef(rel_path, title), score=sim, source="keyword")
            for sim, rel_path, title in scored[:top_k]
        ]
    except Exception:
        return []


def semantic_search(query: str, top_k: int = 3) -> list[str]:
    """DEPRECATED — kept only for its existing unit-test coverage. New code
    should call semantic_search_paths(), which returns the WikiRef needed
    to actually open the matched file (see 0.2 in memory-retrieval-repair-tz.md).

    Returns up to top_k display titles (plain strings, not [[wikilinks]]).
    Returns [] on any error.
    """
    return [hit.ref.title for hit in semantic_search_paths(query, top_k)]


def _fingerprint_path() -> Path:
    return _VECTOR_DB_DIR / _FINGERPRINT_FILE


def _idf_path() -> Path:
    return _VECTOR_DB_DIR / _IDF_FILE


def _load_idf() -> dict[str, float]:
    """Load the corpus-wide IDF weights sidecar. Returns {} on any error or
    missing file -- fail-open, matching _apply_idf()'s own out-of-vocabulary
    handling (a missing/empty idf dict just makes every term weight 0,
    which _cosine() already treats as no-match rather than crashing)."""
    try:
        path = _idf_path()
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {k: float(v) for k, v in data.items() if isinstance(v, int | float)}
    except Exception:
        pass
    return {}


def _save_idf(idf: dict[str, float]) -> bool:
    """Persist the corpus-wide IDF weights sidecar. Fail-open, atomic
    tmp+os.replace (same pattern as _save_tfidf_index()/_save_fingerprint()
    in this same file)."""
    try:
        _VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
        dest = _idf_path()
        tmp = dest.with_suffix(".tmp")
        tmp.write_text(json.dumps(idf, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(dest))
        return True
    except Exception as exc:
        print(f"[vector-store] WARNING: failed to save IDF weights: {exc}", file=sys.stderr)
        return False


def _invalidate_fingerprint() -> None:
    """Remove the corpus fingerprint sidecar. Fail-open.

    WHY (memory-retrieval-repair-tz.md PR-4 follow-up, externally-pasted
    review, verified by reproduction before fixing): called from
    index_wiki_entry()'s single-entry write path, alongside
    _delete_idf_sidecar(). Without this, a corpus whose fingerprint was
    last saved by rebuild_index() stays "unchanged" from that function's
    point of view even after index_wiki_entry() adds a note out-of-band --
    the next rebuild_index() call would see a fingerprint match and skip
    the real rebuild that would otherwise restore a consistent idf sidecar
    covering the new note's vocabulary. Deleting the fingerprint here forces
    the next rebuild_index() call to actually run, exactly as if the
    corpus had changed (which, from the idf sidecar's point of view, it
    has: index_wiki_entry() added a document the idf sidecar doesn't know
    about, even though rebuild_index()'s own file-stat-based fingerprint
    can't see that from stats alone).
    """
    try:
        _fingerprint_path().unlink(missing_ok=True)
    except OSError:
        pass


def _delete_idf_sidecar() -> None:
    """Remove the idf sidecar file. Fail-open.

    WHY (memory-retrieval-repair-tz.md PR-4): called when tf_index.json's
    write succeeds but idf_weights.json's write then fails. Documents are
    always stored as plain TF now (see rebuild_index()'s TF branch and
    semantic_search_paths()'s own WHY comment for the redesign this
    followed after CI caught a real mismatch bug in an earlier version
    that baked idf into stored documents) -- so a stale idf sidecar here
    is no longer a severe correctness risk, only a mild one (search would
    weight both the query and every document with an OUTDATED idf,
    reflecting a previous corpus snapshot rather than the current one, for
    however long it takes the next successful rebuild to refresh it).
    Deleting it anyway is a cheap, strictly-safer choice: it forces the
    already-implemented empty-idf-falls-back-to-plain-TF path (using the
    CURRENT corpus with no idf at all) instead of a stale-but-plausible
    idf from a corpus that may no longer match what's on disk.
    """
    try:
        _idf_path().unlink(missing_ok=True)
    except OSError:
        pass


def _iter_indexable_files(wiki_dir: Path) -> list[Path]:
    """Return .md files that belong to the searchable corpus, sorted for
    deterministic fingerprinting and indexing order.

    WHY rglob not glob (memory-retrieval-repair-tz.md §0.1): raw_to_wiki.py
    routes entries into wiki/{projects,areas,resources,archives}/ (PARA
    subdirs) -- a flat glob("*.md") never sees them. Exclusions mirror
    knowledge_librarian._query_wiki_raw_titles()'s own exclusion list
    exactly, so both scanners agree on what "the corpus" is.
    """
    result = []
    for f in sorted(wiki_dir.rglob("*.md")):
        if f.name == "index.md" or re.search(r"_\d+\.md$", f.name):
            continue
        if _EXCLUDED_DIR_NAMES & set(f.relative_to(wiki_dir).parts[:-1]):
            continue
        result.append(f)
    return result


def _corpus_fingerprint(files: list[Path], wiki_dir: Path, backend: str) -> str:
    """Hash (schema version, backend, rel_path, size, mtime_ns) for every indexable file.

    WHY (memory-retrieval-repair-tz.md PR-1): raw_to_wiki.main() calls
    rebuild_index() unconditionally on every Stop event, even when nothing
    changed -- with ChromaDB active this means re-embedding the entire wiki
    on every session end. A cheap fingerprint comparison lets an unchanged
    corpus skip re-embedding entirely, at the cost of one stat() per file.

    WHY _TF_SCHEMA_VERSION is baked into the hash (P2, Codex review on
    PR #334): the fingerprint is a pure function of FILE STATS, not of the
    code that reads them. An installation that already has PR-1's
    fingerprint saved, with no file changed since, upgrades straight to
    PR-2's rel_path-keyed/wrapped TF-IDF shape -- the fingerprint still
    matches, rebuild_index() returns early with changed=False, and every
    OLD title-keyed flat entry is left in tf_index.json forever (until some
    file happens to change). semantic_search_paths()'s defensive shape
    check then skips every one of them, so search silently returns nothing
    until an unrelated edit finally triggers a real rebuild. Salting the
    hash with the schema version forces a mismatch -- and therefore a full
    rebuild -- on any on-disk VALUE-shape change, independent of whether
    any file actually changed. Bump this constant whenever
    index_wiki_entry()'s TF-IDF value shape changes again (e.g. PR-4's
    real-IDF reweighting).

    WHY backend is also salted in (same class of gap, caught in external
    review of PR #334 after the schema-version fix above landed): a corpus
    indexed while ChromaDB was unavailable (backend="tf") gets its
    fingerprint saved; if Chroma later becomes available with the corpus
    still unchanged, the fingerprint would otherwise still match and
    rebuild_index() would return early -- leaving the Chroma collection
    permanently empty while semantic_search_paths()'s Chroma branch always
    returns first (no TF-IDF fallback when Chroma is merely empty, not
    unavailable), silently blanking search results until an unrelated file
    edit forces a real rebuild. Salting on backend forces a mismatch -- and
    therefore a real re-embed into the newly-available backend -- the
    moment backend availability changes, independent of file changes.
    """
    parts: list[str] = [f"schema:{_TF_SCHEMA_VERSION}", f"backend:{backend}"]
    for f in files:
        try:
            stat = f.stat()
        except OSError:
            continue
        rel = f.relative_to(wiki_dir).as_posix()
        parts.append(f"{rel}:{stat.st_size}:{stat.st_mtime_ns}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _load_fingerprint() -> str | None:
    try:
        path = _fingerprint_path()
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return None


def _save_fingerprint(fingerprint: str) -> None:
    """Persist the corpus fingerprint. Fail-open.

    WHY tmp+os.replace (P2, reviewer-agent finding on
    memory-retrieval-repair-tz.md PR-1): mirrors _save_tfidf_index()'s own
    atomicity fix in this same file -- a direct write_text() isn't atomic
    even for a single write, and a crash mid-write would leave a truncated
    fingerprint. Consequence of a truncated read is low (fail-safe: just
    forces a redundant re-index on the next call, not corruption), but the
    fix is one line different from the pattern already established here.
    """
    try:
        _VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
        dest = _fingerprint_path()
        tmp = dest.with_suffix(".tmp")
        tmp.write_text(fingerprint, encoding="utf-8")
        os.replace(str(tmp), str(dest))
    except OSError:
        pass


def rebuild_index(wiki_dir: Path) -> RebuildReport:
    """Re-index all .md files in wiki_dir, unless the corpus fingerprint is
    unchanged since the last rebuild.

    WHY: called by raw_to_wiki.py unconditionally on every Stop event so the
    vector index stays in sync with the file system -- "unconditional"
    previously meant a full re-embed every time regardless of whether
    anything actually changed (memory-retrieval-repair-tz.md PR-1). The
    fingerprint check makes a no-op rebuild a hash comparison, not a scan.

    Args:
        wiki_dir: Path to the wiki directory (e.g. ~/.claude/memory/_auto/wiki/).
    """
    if not wiki_dir.exists():
        return RebuildReport(
            scanned=0, indexed=0, deleted=0, failed=0, skipped=0, backend="tf", changed=False
        )

    try:
        _VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        return RebuildReport(
            scanned=0, indexed=0, deleted=0, failed=0, skipped=0, backend="tf", changed=False
        )

    # WHY call _get_chroma_collection()/_get_embedder() once and reuse them,
    # not twice (P2-adjacent hygiene, PR-3): _get_chroma_collection()
    # constructs a new PersistentClient on every call -- calling it again
    # below for the actual batch write would be wasteful and, in principle,
    # could observe a different result if availability flickered mid-function.
    #
    # WHY backend requires BOTH collection AND embedder, not just collection
    # (real bug, caught re-verifying an externally-pasted review's claim
    # after PR-3's own review cycle, reproduced with a tool: Chroma
    # available but the embedder model failing to load made every file
    # fail with backend="chroma" locked in, permanently skipping the
    # corpus instead of using the zero-dependency TF-IDF path that works
    # fine on its own): index_wiki_entry() -- still used by other callers
    # and its own unit tests -- already falls through to TF-IDF per-call
    # when `collection is not None but embedder is None` (see its own
    # ChromaDB path). rebuild_index()'s batch rewrite decided `backend`
    # once for the whole run and had lost that fallback; this restores it
    # at the whole-run level.
    collection = _get_chroma_collection()
    embedder = _get_embedder() if collection is not None else None
    backend: str = "chroma" if collection is not None and embedder is not None else "tf"
    files = _iter_indexable_files(wiki_dir)
    fingerprint = _corpus_fingerprint(files, wiki_dir, backend)

    if fingerprint == _load_fingerprint():
        return RebuildReport(
            scanned=len(files),
            indexed=0,
            deleted=0,
            failed=0,
            skipped=len(files),
            backend=backend,  # type: ignore[arg-type]
            changed=False,
        )

    # WHY build a batch first, write once, THEN delete stale entries
    # (memory-retrieval-repair-tz.md PR-3, fixes 0.4): the old loop called
    # index_wiki_entry() per file, which does its own load-mutate-save --
    # that never removes an entry for a file that no longer exists (0.4:
    # "rebuild_index() never removes stale entries in either backend"), and
    # a mid-rebuild crash after a destructive clear would leave a
    # genuinely empty index, worse than the stale one it replaced. New
    # ordering: (1) parse every file into memory, tolerating per-file
    # failures (unchanged fail-open philosophy: skip the bad file, keep
    # going); (2) write the successfully-parsed batch in ONE atomic
    # operation; (3) delete only entries whose rel_path is no longer
    # present in this run's file list, and only AFTER the write succeeds --
    # a write failure leaves the old, still-valid index/collection
    # untouched rather than partially cleared.
    count = 0
    failed = 0
    tf_batch: dict[str, dict[str, Any]] = {}
    chroma_ids: list[str] = []
    chroma_docs: list[str] = []
    chroma_embeds: list[list[float]] = []
    chroma_metas: list[dict[str, str]] = []

    for f in files:
        try:
            body = f.read_text(encoding="utf-8", errors="ignore")
            title_match = re.search(r"^# (.+)", body, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else f.stem
            tags_match = re.search(r"\*\*Tags:\*\*\s*(.+)", body)
            tags: list[str] = []
            if tags_match:
                raw = tags_match.group(1).strip().rstrip("\\").strip()
                tags = [t.strip() for t in raw.split(",") if t.strip()]
            # WHY WikiRef, not the bare title (PR-2, fixes 0.2): rel_path is
            # the real join key from here on -- see index_wiki_entry()'s
            # WHY comment.
            ref = WikiRef(rel_path=f.relative_to(wiki_dir).as_posix(), title=title)
            combined = f"{ref.title}\n{body}\n{' '.join(tags)}"

            if backend == "chroma":
                if embedder is None:
                    raise RuntimeError("embedder unavailable mid-rebuild")
                embedding = embedder.encode(combined).tolist()
                chroma_ids.append(ref.rel_path)
                chroma_docs.append(combined)
                chroma_embeds.append(embedding)
                chroma_metas.append({"title": ref.title, "tags": ",".join(tags)})
            else:
                vec = _compute_tf_normalized(_tokenize(combined))
                tf_batch[ref.rel_path] = {"title": ref.title, "vector": vec}
            count += 1
        except Exception:
            # WHY counted, not silently swallowed (memory-retrieval-repair-tz.md
            # PR-1): a per-file failure must not vanish into a plausible-looking
            # total. A file that fails to parse is simply absent from this
            # run's batch -- but its old entry, if any, is KEPT (last-known-
            # good), not deleted, as long as the file still exists on disk.
            # See this function's own merge step below for why (memory-
            # retrieval-repair-tz.md PR-3 follow-up, externally-pasted
            # review, verified by reproduction: a file that keeps failing to
            # parse across multiple runs previously lost its entry on the
            # FIRST failure and stayed unsearchable for as long as the
            # failure recurred -- a genuine availability gap, not corrected
            # by "self-heals on the next successful run" when the failure
            # itself doesn't resolve quickly).
            failed += 1

    deleted = 0
    # WHY data_written and cleanup_ok are two separate flags, not one
    # write_ok (real bug, caught re-verifying an externally-pasted review's
    # claim after PR-3's own review cycle: a single write_ok flag can't
    # distinguish "the new data never got written" -- which means these
    # files are NOT actually indexed and must be reclassified as failed in
    # the report below -- from "the new data DID get written, only the
    # separate stale-cleanup step afterward failed" -- which means the
    # files ARE indexed and searchable, only old stale entries linger a
    # bit longer. Conflating them would have made the delete-failure
    # regression test above wrongly report a successfully-indexed file as
    # failed.): `data_written` gates the indexed/failed reclassification
    # below; `write_ok = data_written and cleanup_ok` (unchanged meaning)
    # still gates the fingerprint save, so a cleanup failure still forces a
    # retry next time to finish the deletion.
    data_written = False
    cleanup_ok = True
    # WHY skip the write entirely on a total failure over a non-empty
    # corpus (P0, isolated reviewer-agent finding on PR-3, reproduced with
    # a tool: a fully-populated index wiped to empty by a single transient
    # failure -- e.g. sentence-transformers briefly unavailable -- with
    # `deleted` falsely reporting the wipe as legitimate cleanup): an EMPTY
    # batch is ambiguous between "the corpus is genuinely empty now" (files
    # really were deleted -- correct to clear everything) and "every file
    # failed to parse/embed THIS run" (files still exist on disk, we just
    # couldn't process any of them -- writing an empty batch would destroy
    # real data based on zero successful reads). `len(files) > 0 and count
    # == 0` can only be the second case (every one of a non-empty file list
    # failed), so the write is skipped and the existing index/collection is
    # left untouched -- exactly like a write-side I/O failure already was.
    total_failure = len(files) > 0 and count == 0
    if total_failure:
        print(
            f"[vector-store] WARNING: all {failed} file(s) failed to index this run -- "
            "skipping the write entirely rather than wiping the existing index/collection.",
            file=sys.stderr,
        )
    elif backend == "chroma" and collection is not None:
        try:
            if chroma_ids:
                collection.upsert(
                    ids=chroma_ids,
                    documents=chroma_docs,
                    embeddings=chroma_embeds,
                    metadatas=chroma_metas,
                )
            data_written = True
            # WHY delete only after upsert succeeds, in its OWN try/except
            # (P1, isolated reviewer-agent finding on PR-3, reproduced by
            # tracing: a single flag was previously set True right after
            # upsert, BEFORE this get()/delete() step -- a failure isolated
            # to the delete step was then masked, the fingerprint got saved
            # anyway, and the stale entry was permanently stranded since
            # the next call would see an unchanged fingerprint and never
            # retry): stale ids (present before this run, absent from it)
            # are only safe to remove once the new set is confirmed
            # written, and a cleanup-only failure must not be conflated
            # with the newly-written data being invalid.
            try:
                existing = collection.get()
                existing_ids = set(existing.get("ids") or [])
                stale_ids = existing_ids - set(chroma_ids)
                if stale_ids:
                    collection.delete(ids=list(stale_ids))
                    deleted = len(stale_ids)
            except Exception as exc:
                cleanup_ok = False
                print(
                    f"[vector-store] WARNING: Chroma stale-entry cleanup failed "
                    f"(new data was still written): {exc}",
                    file=sys.stderr,
                )
        except Exception as exc:
            print(f"[vector-store] WARNING: Chroma batch rebuild failed: {exc}", file=sys.stderr)
    elif backend == "tf":
        # WHY real corpus-wide IDF is computed HERE, but NOT baked into the
        # STORED document vectors (memory-retrieval-repair-tz.md PR-4,
        # fixes 0.5 -- redesigned after CI caught a real bug in the first
        # version of this PR, verified with a tool before applying this
        # fix): every document's TF vector for this run is already sitting
        # in tf_batch at this point, so this is the one place a real,
        # honest IDF can be computed (it needs to see the WHOLE corpus).
        # The FIRST version of this PR reweighted tf_batch's vectors here
        # and persisted the IDF-weighted result -- but that makes the
        # on-disk documents and a later query permanently coupled to
        # WHICHEVER idf produced them. If the idf sidecar and tf_index.json
        # ever fall out of sync (a partial write failure, or simply a
        # sidecar deleted as a safety measure -- see the old fix this
        # replaces), the stored documents are IDF-weighted while the query
        # reverts to plain TF (or vice versa): reproduced by hand, an
        # identical query/document pair went from a correct 1.0 cosine
        # score to a wrong ~0.32, and a genuinely irrelevant document
        # OUTRANKED the relevant one. Documents are now saved as PLAIN TF
        # (exactly what index_wiki_entry() already produces, unchanged),
        # and semantic_search_paths() applies the idf sidecar to BOTH the
        # query AND each document, freshly, at search time -- so the two
        # sides can never desynchronize: either both get real IDF (sidecar
        # present) or both stay plain TF (sidecar absent), never a mix.
        # WHY the same lock index_wiki_entry() uses (cross-model audit,
        # extended here for PR-3): a batch replace racing an unlocked
        # concurrent index_wiki_entry() call could let a stale single-entry
        # write silently clobber this run's full-corpus write, or vice
        # versa. Held only around the read-then-replace, matching the
        # existing pattern's scope.
        with file_lock(_tfidf_lock_path(), timeout=15.0) as acquired:
            if acquired:
                old_index = _load_tfidf_index()
                # WHY last-known-good merge, not a flat replace with
                # tf_batch (memory-retrieval-repair-tz.md PR-3 follow-up,
                # externally-pasted review, verified by reproduction before
                # fixing): a file that exists on disk but failed to parse
                # THIS run is not the same as a file that no longer exists
                # -- only entries whose rel_path is absent from the CURRENT
                # file list (physically deleted, renamed, or newly excluded)
                # get dropped. An entry for a file that still exists but
                # merely failed to parse this run keeps its last-known-good
                # vector, disjoint from tf_batch by construction (a file
                # can't both fail this loop's try/except AND land in
                # tf_batch). This closes the gap the flat-replace version
                # had: a file failing to parse across MULTIPLE consecutive
                # runs previously lost its entry on the very first failure
                # and stayed unsearchable for as long as the failure
                # recurred -- "the next successful run restores it" isn't a
                # real fix when the failure itself doesn't resolve quickly.
                current_rel_paths = {f.relative_to(wiki_dir).as_posix() for f in files}
                kept_stale = {
                    rel_path: entry
                    for rel_path, entry in old_index.items()
                    if rel_path in current_rel_paths and rel_path not in tf_batch
                }
                merged_index = {**kept_stale, **tf_batch}
                # WHY real corpus-wide IDF is computed HERE, but NOT baked
                # into the STORED document vectors (memory-retrieval-repair-
                # tz.md PR-4, fixes 0.5 -- redesigned after CI caught a real
                # bug in the first version of this PR, verified with a tool
                # before applying this fix): every document's TF vector for
                # this run is already sitting in tf_batch at this point,
                # this is the one place a real, honest IDF can be computed
                # (it needs to see the WHOLE corpus). The FIRST version of
                # this PR reweighted tf_batch's vectors here and persisted
                # the IDF-weighted result -- but that makes the on-disk
                # documents and a later query permanently coupled to
                # WHICHEVER idf produced them. If the idf sidecar and
                # tf_index.json ever fall out of sync (a partial write
                # failure, or simply a sidecar deleted as a safety measure
                # -- see the old fix this replaces), the stored documents
                # are IDF-weighted while the query reverts to plain TF (or
                # vice versa): reproduced by hand, an identical
                # query/document pair went from a correct 1.0 cosine score
                # to a wrong ~0.32, and a genuinely irrelevant document
                # OUTRANKED the relevant one. Documents are now saved as
                # PLAIN TF (exactly what index_wiki_entry() already
                # produces, unchanged), and semantic_search_paths() applies
                # the idf sidecar to BOTH the query AND each document,
                # freshly, at search time -- so the two sides can never
                # desynchronize: either both get real IDF (sidecar present)
                # or both stay plain TF (sidecar absent), never a mix.
                #
                # WHY computed over merged_index, not tf_batch alone (PR-3
                # follow-up): a kept-stale document is still part of the
                # searchable corpus (see above) -- excluding its terms from
                # the corpus-wide document-frequency count would undercount
                # both the corpus size and every term's document frequency,
                # making the idf applied to it (and to every other
                # document, since idf is a whole-corpus quantity) less
                # accurate than the actual on-disk corpus warrants.
                idf = _compute_corpus_idf([entry["vector"] for entry in merged_index.values()])
                # WHY the idf save is only ATTEMPTED after the documents
                # save succeeds, and the idf sidecar is DELETED (not left
                # alone) on a partial failure: documents are always plain
                # TF now (see this branch's own WHY comment above for the
                # redesign), so a partial failure here is a mild staleness
                # risk, not the severe silent-wrong-ranking bug an earlier
                # version of this PR had -- but deleting the sidecar is
                # still strictly safer than leaving a stale one paired with
                # a corpus that may have moved on. See _delete_idf_sidecar()'s
                # own WHY comment. Both saving and deleting are fail-open.
                tf_saved = _save_tfidf_index(merged_index)
                idf_saved = _save_idf(idf) if tf_saved else False
                if tf_saved and not idf_saved:
                    _delete_idf_sidecar()
                if tf_saved and idf_saved:
                    # WHY a single flag covers both concerns here (unlike
                    # Chroma): _save_tfidf_index() is one atomic replace --
                    # writing the new data IS the deletion of stale entries,
                    # there is no separate cleanup step that can fail
                    # independently.
                    data_written = True
                    # WHY len(old_index) - current_rel_paths, not
                    # - set(merged_index) (PR-3 follow-up): a kept-stale
                    # entry is still present in merged_index, so comparing
                    # against merged_index's keys would wrongly exclude
                    # nothing new -- comparing against the CURRENT file
                    # list directly counts exactly the entries dropped
                    # because their file is genuinely gone (or newly
                    # excluded), not the ones kept because they merely
                    # failed to parse this run.
                    #
                    # WHY this count can still be inflated by unrelated
                    # legacy-schema debris (P2, isolated reviewer-agent
                    # finding on PR-3, cosmetic/observability only, no
                    # data-loss consequence -- unchanged by this follow-up):
                    # if a PRIOR run failed partway through a schema/backend
                    # transition (PR-2's fingerprint salts), old_index can
                    # still hold stale entries from before that transition
                    # alongside genuinely-deleted-file entries -- both get
                    # counted here as "deleted" even though only
                    # genuinely-removed files should be. The actual replace
                    # is still correct either way; only the reported number
                    # can overcount.
                    deleted = len(set(old_index) - current_rel_paths)
            else:
                print(
                    f"[vector-store] WARNING: could not acquire lock for batch "
                    f"rebuild: {_tfidf_lock_path()}",
                    file=sys.stderr,
                )
    write_ok = data_written and cleanup_ok

    # WHY reclassify count into failed when the NEW DATA itself didn't get
    # written -- keyed on data_written, not write_ok (real bug, caught
    # re-verifying an externally-pasted review's claim after PR-3's own
    # review cycle, reproduced with a tool: a TF-IDF save failure -- e.g.
    # disk full, retry-exhausted os.replace() -- left `indexed=2, failed=0`
    # in the report while the on-disk index was completely empty). `count`
    # only ever meant "successfully parsed and prepared this run," never
    # "actually persisted" -- those are the same thing when the write
    # succeeds, but diverge when data_written is False for a reason OTHER
    # than the total-failure skip above (which already has count=0). Using
    # data_written rather than write_ok here matters: a Chroma
    # cleanup-only failure (data_written=True, cleanup_ok=False) must NOT
    # reclassify successfully-indexed files as failed -- they genuinely
    # are indexed, only stale entries linger a bit longer.
    if not data_written and not total_failure:
        failed += count
        count = 0

    # WHY only save the fingerprint when nothing failed AND the batch write
    # actually succeeded (P1, reviewer-agent finding on PR-1; extended for
    # PR-3's write_ok): the fingerprint is keyed on file stats, not on
    # indexing success -- saving it unconditionally would let a
    # permanently-failing file, or a write that never actually landed (lock
    # timeout, Chroma error), get treated as "corpus is up to date" forever.
    # Skipping the save forces every subsequent rebuild_index() call to
    # retry until it succeeds -- a redundant re-index of already-good files
    # is an acceptable cost for never silently losing data.
    if failed == 0 and write_ok:
        _save_fingerprint(fingerprint)
    return RebuildReport(
        scanned=len(files),
        indexed=count,
        deleted=deleted,
        failed=failed,
        skipped=0,
        backend=backend,  # type: ignore[arg-type]
        changed=True,
    )


if __name__ == "__main__":
    # Quick smoke test: index current wiki and search
    wiki = Path.home() / ".claude" / "memory" / "_auto" / "wiki"
    report = rebuild_index(wiki)
    print(f"[vector-store] {report}", file=sys.stderr)
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        results = semantic_search(query, top_k=5)
        print(f"Top results for '{query}':", file=sys.stderr)
        for r in results:
            print(f"  - {r}", file=sys.stderr)
