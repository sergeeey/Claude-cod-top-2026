"""Tests for hooks/vector_store.py — TF-IDF semantic search."""

import os
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
        """If ChromaDB raises ImportError, fall back to TF-IDF gracefully.

        WHY (2026-09-02): the mock must be in place BEFORE index_wiki_entry
        too, not just before semantic_search. On a machine where chromadb +
        sentence-transformers are actually importable (this repo's own conda
        env among them -- confirmed via pip show), index_wiki_entry indexed
        for real into ChromaDB, leaving the TF-IDF index empty; the later
        mocked semantic_search then correctly found nothing in TF-IDF and
        returned []. The test only "passed" in environments lacking those
        packages -- it wasn't exercising the fallback path it claims to
        test. Mocking unavailability for both calls makes the test
        deterministic regardless of what's installed locally.
        """
        vector_store._VECTOR_DB_DIR = tmp_path
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        vector_store.index_wiki_entry("Fallback Entry", "test fallback content", [])

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

    def test_save_failure_warns_on_stderr(self, tmp_path, monkeypatch, capsys):
        """Regression (P2, reviewer-agent parity note): retry exhaustion in
        _save_tfidf_index() previously vanished silently -- unlike the
        sibling doc_registry/expert_registry/moc_autolink/observation_capture
        files fixed in this same audit batch, which all warn on stderr."""
        vector_store._VECTOR_DB_DIR = tmp_path
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(PermissionError))
        monkeypatch.setattr(vector_store.time, "sleep", lambda *_: None)

        vector_store.index_wiki_entry("Entry", "some content", [])

        captured = capsys.readouterr()
        assert "vector-store" in captured.err
        assert "TF-IDF" in captured.err


class TestRebuildIndex:
    """WHY these assert `result.indexed`, not `result == N` (memory-retrieval-
    repair-tz.md PR-1): rebuild_index() now returns a structured RebuildReport
    instead of a bare int -- a deliberate contract upgrade (a plain count could
    not distinguish "N indexed, 0 failed" from "N indexed, some failed
    silently"), not a weakened assertion. Every check below is equally or
    more specific than the int comparison it replaces."""

    def setup_method(self):
        self._orig_dir = vector_store._VECTOR_DB_DIR

    def teardown_method(self):
        vector_store._VECTOR_DB_DIR = self._orig_dir

    def test_missing_wiki_dir_returns_zero(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path
        result = vector_store.rebuild_index(tmp_path / "nonexistent")
        assert result.indexed == 0
        assert result.scanned == 0
        assert result.failed == 0

    def test_counts_indexed_entries(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "note1.md").write_text("# Note One\ncontent about hooks", encoding="utf-8")
        (wiki / "note2.md").write_text("# Note Two\ncontent about skills", encoding="utf-8")
        result = vector_store.rebuild_index(wiki)
        assert result.indexed == 2
        assert result.failed == 0
        assert result.changed is True

    def test_skips_index_md(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "index.md").write_text("# Index\nnav content", encoding="utf-8")
        (wiki / "real.md").write_text("# Real\ncontent", encoding="utf-8")
        result = vector_store.rebuild_index(wiki)
        assert result.indexed == 1

    def test_skips_chunk_files(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "note_2.md").write_text("# Chunk\ncontent", encoding="utf-8")
        (wiki / "note.md").write_text("# Note\ncontent", encoding="utf-8")
        result = vector_store.rebuild_index(wiki)
        assert result.indexed == 1

    def test_indexes_para_subdirectories(self, tmp_path):
        """Regression (memory-retrieval-repair-tz.md §0.1): glob("*.md") only
        saw the flat wiki root -- entries raw_to_wiki.py routes into PARA
        subdirs (projects/areas/resources/archives) were invisible to the
        vector index. Must fail before the glob->rglob fix, pass after."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        (wiki / "projects").mkdir(parents=True)
        (wiki / "projects" / "auc_red_flags.md").write_text(
            "# AUC Red Flags\ncontent about model evaluation pitfalls", encoding="utf-8"
        )
        result = vector_store.rebuild_index(wiki)
        assert result.indexed == 1
        results = vector_store.semantic_search("AUC evaluation pitfalls", top_k=3)
        assert "AUC Red Flags" in results

    def test_daily_notes_excluded_from_corpus(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        (wiki / "daily").mkdir(parents=True)
        (wiki / "daily" / "2026-09-03.md").write_text("# Daily\nhandoff note", encoding="utf-8")
        (wiki / "real.md").write_text("# Real\ncontent", encoding="utf-8")
        result = vector_store.rebuild_index(wiki)
        assert result.indexed == 1

    def test_unchanged_corpus_skips_reindex(self, tmp_path, monkeypatch):
        """The core PR-1 fix: a second rebuild_index() call with no
        filesystem change must not re-embed anything -- verified here by
        asserting index_wiki_entry (the expensive step) is not called."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "note.md").write_text("# Note\ncontent", encoding="utf-8")

        first = vector_store.rebuild_index(wiki)
        assert first.changed is True
        assert first.indexed == 1

        calls = []
        monkeypatch.setattr(
            vector_store,
            "index_wiki_entry",
            lambda *a, **k: calls.append(1),
        )
        second = vector_store.rebuild_index(wiki)
        assert second.changed is False
        assert second.skipped == 1
        assert calls == []

    def test_changed_corpus_triggers_reindex(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "note.md").write_text("# Note\ncontent", encoding="utf-8")
        vector_store.rebuild_index(wiki)

        (wiki / "note2.md").write_text("# Note Two\nmore content", encoding="utf-8")
        second = vector_store.rebuild_index(wiki)
        assert second.changed is True
        assert second.indexed == 2

    def test_internal_indexing_failure_is_counted_not_hidden(self, tmp_path, monkeypatch):
        """Regression (P1, reviewer-agent finding on PR-1): index_wiki_entry()
        is itself fail-open and never raises, so rebuild_index()'s old
        `except Exception: failed += 1` could never see an internal failure
        (lock timeout, TF-IDF save failure) -- it always landed in `count`
        instead. Simulating index_wiki_entry's own documented fail-open
        contract (print + return False, no raise) must now show up as
        `failed`, not `indexed`."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "note.md").write_text("# Note\ncontent", encoding="utf-8")

        monkeypatch.setattr(vector_store, "index_wiki_entry", lambda *a, **k: False)
        result = vector_store.rebuild_index(wiki)
        assert result.indexed == 0
        assert result.failed == 1

    def test_failed_rebuild_does_not_save_fingerprint_and_retries(self, tmp_path, monkeypatch):
        """Regression (P1, reviewer-agent finding on PR-1): the fingerprint
        is keyed on file stats, not indexing success -- saving it after a
        run with real failures would make the corpus "look unchanged" on
        every later call, permanently hiding the failed file from retry.
        The fix: skip the fingerprint save whenever failed > 0."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "note.md").write_text("# Note\ncontent", encoding="utf-8")

        monkeypatch.setattr(vector_store, "index_wiki_entry", lambda *a, **k: False)
        first = vector_store.rebuild_index(wiki)
        assert first.failed == 1

        monkeypatch.undo()  # restore the real index_wiki_entry
        second = vector_store.rebuild_index(wiki)
        assert second.changed is True  # no fingerprint was saved -> must retry, not skip
        assert second.indexed == 1
        assert second.failed == 0

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
