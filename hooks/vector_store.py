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

import json
import math
import re
import sys
from pathlib import Path

# WHY: module-level constant = monkeypatchable in tests (same pattern as
# cogniml_client._PUSHED_LEDGER). Never hardcode ~/.claude inside a function
# that tests can't redirect.
_VECTOR_DB_DIR: Path = Path.home() / ".claude" / "cache" / "vector_db"
_TFIDF_INDEX_FILE = "tfidf_index.json"

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
    return [t for t in tokens if len(t) > 2 and t not in _STOPWORDS]  # noqa: PLR2004


# ---------------------------------------------------------------------------
# TF-IDF index (pure stdlib, JSON-backed)
# ---------------------------------------------------------------------------


def _tfidf_index_path() -> Path:
    return _VECTOR_DB_DIR / _TFIDF_INDEX_FILE


def _load_tfidf_index() -> dict[str, dict[str, float]]:
    """Load {title: {term: tfidf}} from disk. Returns {} on any error."""
    path = _tfidf_index_path()
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data  # type: ignore[return-value]
    except Exception:
        pass
    return {}


def _save_tfidf_index(index: dict[str, dict[str, float]]) -> None:
    """Persist TF-IDF index to disk. Fail-open."""
    try:
        _VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
        _tfidf_index_path().write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _compute_tfidf(tokens: list[str]) -> dict[str, float]:
    """Compute normalised TF for a token list (no corpus IDF — single-doc TF).

    WHY: we index one document at a time (wiki entries arrive incrementally),
    so we can't compute IDF at index time. Using TF only with L2-normalisation
    gives cosine similarity that degrades gracefully versus full TF-IDF.
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
        import chromadb  # noqa: PLC0415

        client = chromadb.PersistentClient(path=str(_VECTOR_DB_DIR / "chroma"))
        return client.get_or_create_collection("wiki")
    except Exception:
        return None


def _get_embedder():  # type: ignore[return]
    """Return SentenceTransformer model or None if not installed."""
    try:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def index_wiki_entry(title: str, body: str, tags: list[str] | None = None) -> None:
    """Add or update a wiki entry in the vector index.

    Tries ChromaDB + sentence-transformers first; falls back to TF-IDF.
    Always fail-open.

    Args:
        title: Human-readable title (used as document ID).
        body: Full markdown body of the wiki entry.
        tags: Optional list of tags (appended to body for better matching).
    """
    try:
        combined = f"{title}\n{body}\n{' '.join(tags or [])}"

        # --- ChromaDB path ---
        collection = _get_chroma_collection()
        if collection is not None:
            embedder = _get_embedder()
            if embedder is not None:
                embedding = embedder.encode(combined).tolist()
                collection.upsert(
                    ids=[title],
                    documents=[combined],
                    embeddings=[embedding],
                    metadatas=[{"title": title, "tags": ",".join(tags or [])}],
                )
                return  # success via ChromaDB

        # --- TF-IDF fallback ---
        tokens = _tokenize(combined)
        vec = _compute_tfidf(tokens)
        index = _load_tfidf_index()
        index[title] = vec
        _save_tfidf_index(index)
    except Exception:
        pass  # WHY: fail-open — indexing failure must not interrupt the session


def semantic_search(query: str, top_k: int = 3) -> list[str]:
    """Find the most semantically similar wiki titles for a query.

    Returns up to top_k titles (plain strings, not [[wikilinks]]).
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
                return list(ids)[:top_k]

        # --- TF-IDF fallback ---
        index = _load_tfidf_index()
        if not index:
            return []

        query_vec = _compute_tfidf(_tokenize(query))
        if not query_vec:
            return []

        scores: list[tuple[float, str]] = []
        for title, doc_vec in index.items():
            sim = _cosine(query_vec, doc_vec)
            if sim > 0:
                scores.append((sim, title))

        scores.sort(key=lambda x: x[0], reverse=True)
        return [title for _, title in scores[:top_k]]
    except Exception:
        return []


def rebuild_index(wiki_dir: Path) -> int:
    """Re-index all .md files in wiki_dir from scratch.

    WHY: called by session_save after wiki updates so the vector index
    stays in sync with the file system. Skips index.md and chunk files.
    Returns number of entries indexed.

    Args:
        wiki_dir: Path to the wiki directory (e.g. ~/.claude/memory/_auto/wiki/).
    """
    if not wiki_dir.exists():
        return 0

    # Reset TF-IDF index (ChromaDB collection handles upsert natively)
    try:
        _VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        return 0

    count = 0
    for f in sorted(wiki_dir.glob("*.md")):
        # Skip navigation / chunk files
        if f.name in ("index.md",) or re.search(r"_\d+\.md$", f.name):
            continue
        try:
            body = f.read_text(encoding="utf-8", errors="ignore")
            title_match = re.search(r"^# (.+)", body, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else f.stem
            tags_match = re.search(r"\*\*Tags:\*\*\s*(.+)", body)
            tags: list[str] = []
            if tags_match:
                raw = tags_match.group(1).strip().rstrip("\\").strip()
                tags = [t.strip() for t in raw.split(",") if t.strip()]
            index_wiki_entry(title, body, tags)
            count += 1
        except Exception:
            pass  # fail-open

    return count


if __name__ == "__main__":
    # Quick smoke test: index current wiki and search
    wiki = Path.home() / ".claude" / "memory" / "_auto" / "wiki"
    n = rebuild_index(wiki)
    print(f"Indexed {n} entries", file=sys.stderr)
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        results = semantic_search(query, top_k=5)
        print(f"Top results for '{query}':", file=sys.stderr)
        for r in results:
            print(f"  - {r}", file=sys.stderr)
