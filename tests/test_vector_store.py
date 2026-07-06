"""Tests for hooks/vector_store.py — TF-IDF semantic search."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

import vector_store


class TestTokenize:
    def test_basic_split(self):
        assert "hello" in vector_store._tokenize("hello world")

    def test_removes_stopwords(self):
        tokens = vector_store._tokenize("the quick brown fox")
        assert "the" not in tokens
        assert "fox" in tokens

    def test_removes_short_tokens(self):
        tokens = vector_store._tokenize("a bb ccc dddd")
        assert "a" not in tokens
        assert "bb" not in tokens
        assert "ccc" in tokens

    def test_lowercases(self):
        tokens = vector_store._tokenize("Hello WORLD")
        assert "hello" in tokens
        assert "HELLO" not in tokens

    def test_empty_string(self):
        assert vector_store._tokenize("") == []


class TestComputeTfidf:
    def test_empty_tokens(self):
        assert vector_store._compute_tf_normalized([]) == {}

    def test_single_token_normalized(self):
        vec = vector_store._compute_tf_normalized(["hello"])
        assert "hello" in vec

        assert abs(vec["hello"] - 1.0) < 1e-6  # L2 norm of single element = 1.0

    def test_multiple_tokens(self):
        vec = vector_store._compute_tf_normalized(["a", "b", "a"])
        assert vec["a"] > vec["b"]  # 'a' appears more often

    def test_l2_normalised(self):
        import math

        vec = vector_store._compute_tf_normalized(["x", "y", "z"])
        norm = math.sqrt(sum(v * v for v in vec.values()))
        assert abs(norm - 1.0) < 1e-6


class TestCosine:
    def test_identical_vectors(self):
        v = {"hello": 0.6, "world": 0.8}
        assert abs(vector_store._cosine(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        v1 = {"hello": 1.0}
        v2 = {"world": 1.0}
        assert vector_store._cosine(v1, v2) == 0.0

    def test_empty_vector(self):
        v = {"hello": 1.0}
        assert vector_store._cosine({}, v) == 0.0
        assert vector_store._cosine(v, {}) == 0.0


class TestTfidfIndex:
    """Tests for TF-IDF index persistence and search."""

    def setup_method(self):
        self._orig_dir = vector_store._VECTOR_DB_DIR

    def teardown_method(self):
        vector_store._VECTOR_DB_DIR = self._orig_dir

    def test_empty_index_returns_empty_search(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path
        results = vector_store.semantic_search("anything", top_k=3)
        assert results == []

    def test_index_and_search_finds_matching_entry(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path
        vector_store.index_wiki_entry("Python Hooks", "hook session python code", ["hooks"])
        results = vector_store.semantic_search("python session", top_k=3)
        assert "Python Hooks" in results

    def test_search_returns_most_similar_first(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path
        vector_store.index_wiki_entry("Auth System", "authentication login token jwt security", [])
        vector_store.index_wiki_entry("Database", "postgres query schema migration table", [])
        results = vector_store.semantic_search("authentication security", top_k=2)
        assert results[0] == "Auth System"

    def test_top_k_respected(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path
        for i in range(5):
            vector_store.index_wiki_entry(f"Entry {i}", f"content topic keyword number {i}", [])
        results = vector_store.semantic_search("content topic keyword", top_k=2)
        assert len(results) <= 2

    def test_index_persists_across_calls(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path
        vector_store.index_wiki_entry("Persistent Entry", "memory storage persistence", [])
        # Reload from disk by calling search (which loads index)
        results = vector_store.semantic_search("memory storage", top_k=3)
        assert "Persistent Entry" in results

    def test_upsert_updates_existing_entry(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path
        vector_store.index_wiki_entry("My Entry", "original content hooks", [])
        vector_store.index_wiki_entry("My Entry", "completely different topic database", [])
        # New content should dominate
        results = vector_store.semantic_search("database topic", top_k=3)
        assert "My Entry" in results

    def test_index_wiki_entry_fails_open_on_bad_dir(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path / "nonexistent" / "nested"
        # Should not raise — fail-open
        vector_store.index_wiki_entry("Title", "body", [])

    def test_semantic_search_fails_open_without_chromadb(self, tmp_path, monkeypatch):
        """If ChromaDB raises ImportError, fall back to TF-IDF gracefully."""
        vector_store._VECTOR_DB_DIR = tmp_path
        vector_store.index_wiki_entry("Fallback Entry", "test fallback content", [])

        # Simulate ChromaDB unavailable
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        results = vector_store.semantic_search("fallback content", top_k=3)
        assert "Fallback Entry" in results

    def test_semantic_search_empty_query(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path
        assert vector_store.semantic_search("", top_k=3) == []

    def test_semantic_search_zero_top_k(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path
        vector_store.index_wiki_entry("X", "some content", [])
        assert vector_store.semantic_search("content", top_k=0) == []


class TestConcurrentIndexing:
    """Regression (MEDIUM, cross-model audit): index_wiki_entry() did a
    load-mutate-save on the TF-IDF index with no locking, so concurrent
    indexing of DIFFERENT wiki entries could lose each other's updates to
    last-writer-wins."""

    def setup_method(self):
        self._orig_dir = vector_store._VECTOR_DB_DIR

    def teardown_method(self):
        vector_store._VECTOR_DB_DIR = self._orig_dir

    def test_six_concurrent_indexings_all_persisted(self, tmp_path, monkeypatch):
        import threading

        vector_store._VECTOR_DB_DIR = tmp_path
        # WHY force the TF-IDF path deterministically: whether ChromaDB is
        # actually installed shouldn't decide if this race-condition test
        # runs against the code path it's meant to cover.
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)

        def index_one(i: int) -> None:
            vector_store.index_wiki_entry(f"Entry {i}", f"unique content number {i}", [])

        # WHY 6 threads, not a larger number: see doc_registry's sibling
        # test for the full explanation.
        threads = [threading.Thread(target=index_one, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final = vector_store._load_tfidf_index()
        # WHY exactly 6, not "at least 1": without the lock, concurrent
        # threads racing on the same read-modify-write would very likely
        # undercount here -- this is the actual failure mode the fix closes.
        assert len(final) == 6
        assert all(f"Entry {i}" in final for i in range(6))


class TestRebuildIndex:
    def setup_method(self):
        self._orig_dir = vector_store._VECTOR_DB_DIR

    def teardown_method(self):
        vector_store._VECTOR_DB_DIR = self._orig_dir

    def test_missing_wiki_dir_returns_zero(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path
        result = vector_store.rebuild_index(tmp_path / "nonexistent")
        assert result == 0

    def test_counts_indexed_entries(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "note1.md").write_text("# Note One\ncontent about hooks", encoding="utf-8")
        (wiki / "note2.md").write_text("# Note Two\ncontent about skills", encoding="utf-8")
        result = vector_store.rebuild_index(wiki)
        assert result == 2

    def test_skips_index_md(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "index.md").write_text("# Index\nnav content", encoding="utf-8")
        (wiki / "real.md").write_text("# Real\ncontent", encoding="utf-8")
        result = vector_store.rebuild_index(wiki)
        assert result == 1

    def test_skips_chunk_files(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "note_2.md").write_text("# Chunk\ncontent", encoding="utf-8")
        (wiki / "note.md").write_text("# Note\ncontent", encoding="utf-8")
        result = vector_store.rebuild_index(wiki)
        assert result == 1

    def test_indexed_entries_searchable(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "hooks.md").write_text(
            "# Hook System\n**Tags:** hooks, session\ncustom hook handler", encoding="utf-8"
        )
        vector_store.rebuild_index(wiki)
        results = vector_store.semantic_search("hook handler session", top_k=3)
        assert "Hook System" in results
