"""Local vector store for wiki semantic search.

WHY: keyword grep in knowledge_librarian misses synonyms and related concepts.
vector_store provides semantic fallback: when fewer than 3 keyword matches are
found, it falls back to cosine similarity over TF-IDF (stdlib-only, zero deps).
Optional ChromaDB + sentence-transformers upgrade for higher-quality embeddings.

Architecture:
  - Primary:  ChromaDB + sentence-transformers (optional, local, no API cost)
  - Fallback: TF-IDF cosine similarity (pure stdlib, JSON-backed index)
  - All public functions are fail-open: return [] / no-op on any exception.

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
# WHY a bare version string, not a key inside tf_index.json (P2, Codex
# review on PR #334): see _corpus_fingerprint()'s own WHY comment. "1" =
# PR-1 shape (title-keyed, flat {token: weight} values). "2" = PR-2 shape
# (rel_path-keyed, {"title", "vector"} wrapped values). Bump this whenever
# index_wiki_entry()'s TF-IDF value shape changes again.
_TF_SCHEMA_VERSION = "2"
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
    """Compute L2-normalised term frequency for a token list.

    WHY: named TF (not TF-IDF) because IDF requires corpus statistics across
    all documents. We index incrementally (one doc at a time), so IDF is not
    available at index time. L2-normalised TF gives cosine similarity that
    degrades gracefully vs full TF-IDF. See issue #F10 in audit log.

    If corpus-wide IDF is needed in future: collect DF counts at index time
    and recompute weights. For now, TF-only is sufficient for wiki-scale search.
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

        # --- TF-IDF fallback ---
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
            return _save_tfidf_index(index)
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
            sim = _cosine(query_vec, entry["vector"])
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

    backend: str = "chroma" if _get_chroma_collection() is not None else "tf"
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

    count = 0
    failed = 0
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
            # WHY check the return value, not just catch an exception
            # (P1, reviewer-agent finding): index_wiki_entry() is itself
            # fail-open and never raises -- an internal failure (lock
            # timeout, TF-IDF save failure) previously vanished as a
            # "successful" count += 1 because nothing here ever saw it.
            if index_wiki_entry(ref, body, tags):
                count += 1
            else:
                failed += 1
        except Exception:
            # WHY counted, not silently swallowed (memory-retrieval-repair-tz.md
            # PR-1): a per-file failure must not vanish into a plausible-looking
            # total -- atomicity/stale-deletion refinements land in PR-3, this
            # PR only makes the count honest. This branch now covers read/parse
            # failures only; index_wiki_entry() failures are covered above.
            failed += 1

    # WHY only save the fingerprint when nothing failed (P1, reviewer-agent
    # finding): the fingerprint is keyed on file stats, not on indexing
    # success -- saving it unconditionally would let a permanently-failing
    # file's stat get captured once, then never retried on any later call
    # (the corpus "looks unchanged" forever). Skipping the save on any
    # failure forces every subsequent rebuild_index() call to retry the
    # whole corpus until it succeeds -- a redundant re-index of already-good
    # files is an acceptable cost for never silently losing a failed one.
    if failed == 0:
        _save_fingerprint(fingerprint)
    return RebuildReport(
        scanned=len(files),
        indexed=count,
        deleted=0,
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
