"""Tests for hooks/vector_store.py — TF-IDF semantic search."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

import vector_store
from lib.wiki_types import WikiRef


def _ref(title: str, rel_path: str | None = None) -> WikiRef:
    """Test helper: build a WikiRef the way rebuild_index() would, without
    requiring every test to spell out a real file path (memory-retrieval-
    repair-tz.md PR-2 -- index_wiki_entry() now takes a WikiRef, not a bare
    title string)."""
    return WikiRef(rel_path=rel_path or f"{title}.md", title=title)


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
        vector_store.index_wiki_entry(_ref("Python Hooks"), "hook session python code", ["hooks"])
        results = vector_store.semantic_search("python session", top_k=3)
        assert "Python Hooks" in results

    def test_search_returns_most_similar_first(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path
        vector_store.index_wiki_entry(
            _ref("Auth System"), "authentication login token jwt security", []
        )
        vector_store.index_wiki_entry(_ref("Database"), "postgres query schema migration table", [])
        results = vector_store.semantic_search("authentication security", top_k=2)
        assert results[0] == "Auth System"

    def test_top_k_respected(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path
        for i in range(5):
            vector_store.index_wiki_entry(
                _ref(f"Entry {i}"), f"content topic keyword number {i}", []
            )
        results = vector_store.semantic_search("content topic keyword", top_k=2)
        assert len(results) <= 2

    def test_index_persists_across_calls(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path
        vector_store.index_wiki_entry(_ref("Persistent Entry"), "memory storage persistence", [])
        # Reload from disk by calling search (which loads index)
        results = vector_store.semantic_search("memory storage", top_k=3)
        assert "Persistent Entry" in results

    def test_upsert_updates_existing_entry(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path
        vector_store.index_wiki_entry(_ref("My Entry"), "original content hooks", [])
        vector_store.index_wiki_entry(_ref("My Entry"), "completely different topic database", [])
        # New content should dominate
        results = vector_store.semantic_search("database topic", top_k=3)
        assert "My Entry" in results

    def test_index_wiki_entry_fails_open_on_bad_dir(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path / "nonexistent" / "nested"
        # Should not raise — fail-open
        vector_store.index_wiki_entry(_ref("Title"), "body", [])

    def test_two_entries_sharing_title_do_not_collide(self, tmp_path, monkeypatch):
        """Regression (memory-retrieval-repair-tz.md PR-2, fixes 0.2): before
        PR-2, index_wiki_entry() keyed the TF-IDF index by `title` --
        two files sharing an H1 title silently overwrote each other's
        vector. rel_path is now the real key, so both must be indexed and
        both individually retrievable by their own distinguishing content."""
        vector_store._VECTOR_DB_DIR = tmp_path
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        vector_store.index_wiki_entry(
            WikiRef(rel_path="areas/a.md", title="Duplicate Title"),
            "unique alpha content",
            [],
        )
        vector_store.index_wiki_entry(
            WikiRef(rel_path="resources/b.md", title="Duplicate Title"),
            "unique beta content",
            [],
        )
        index = vector_store._load_tfidf_index()
        assert len(index) == 2
        assert "areas/a.md" in index and "resources/b.md" in index

        hits = vector_store.semantic_search_paths("unique alpha content", top_k=2)
        rel_paths = {h.ref.rel_path for h in hits}
        assert "areas/a.md" in rel_paths
        assert "resources/b.md" in rel_paths

    def test_search_skips_stale_pre_pr2_flat_entries(self, tmp_path, monkeypatch):
        """Regression (memory-retrieval-repair-tz.md PR-2 stress case 9):
        during the transition window before PR-3's stale-entry deletion
        lands, a pre-PR-2 flat {token: weight} entry (the OLD title-keyed
        shape) can still be sitting in tf_index.json alongside new
        {"title", "vector"}-wrapped entries. semantic_search_paths() must
        skip the malformed one, not crash on it."""
        vector_store._VECTOR_DB_DIR = tmp_path
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)

        vector_store.index_wiki_entry(
            WikiRef(rel_path="areas/new.md", title="New Entry"),
            "unique gamma content",
            [],
        )
        # Manually inject a stale flat-shape entry, simulating a pre-PR-2
        # leftover that PR-3's stale-entry cleanup hasn't removed yet.
        index = vector_store._load_tfidf_index()
        index["Stale Old Title"] = {"gamma": 1.0, "unique": 0.5}
        vector_store._save_tfidf_index(index)

        hits = vector_store.semantic_search_paths("unique gamma content", top_k=5)
        rel_paths = {h.ref.rel_path for h in hits}
        assert "areas/new.md" in rel_paths
        assert "Stale Old Title" not in rel_paths

    def test_search_skips_stale_entry_whose_term_collides_with_wrapper_key(
        self, tmp_path, monkeypatch
    ):
        """Regression (P1, isolated reviewer-agent finding on PR-2): a
        presence check ("vector" not in entry) is not a shape check. A
        stale pre-PR-2 flat entry that happens to contain the literal TF
        term "vector" (very plausible in THIS repo's own notes about
        vector_store) would pass a bare key-presence check, then hand
        _cosine() a float instead of a dict -- crashing the whole loop, not
        just skipping that one entry, since the exception propagates to
        semantic_search_paths()'s outer fail-open and blanks the ENTIRE
        result set for the query. The fix validates the value's shape
        (isinstance(..., dict)), not just the key's presence."""
        vector_store._VECTOR_DB_DIR = tmp_path
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)

        vector_store.index_wiki_entry(
            WikiRef(rel_path="areas/new.md", title="New Entry"),
            "unique delta content",
            [],
        )
        index = vector_store._load_tfidf_index()
        # "vector" is itself one of the stale flat entry's TF terms --
        # the exact collision the presence-only check missed.
        index["Stale Vector Note"] = {"vector": 0.62, "store": 0.44}
        vector_store._save_tfidf_index(index)

        # Must not raise, and must not silently blank the whole result set.
        hits = vector_store.semantic_search_paths("unique delta content", top_k=5)
        rel_paths = {h.ref.rel_path for h in hits}
        assert "areas/new.md" in rel_paths
        assert "Stale Vector Note" not in rel_paths

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
        vector_store.index_wiki_entry(_ref("Fallback Entry"), "test fallback content", [])

        results = vector_store.semantic_search("fallback content", top_k=3)
        assert "Fallback Entry" in results

    def test_semantic_search_empty_query(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path
        assert vector_store.semantic_search("", top_k=3) == []

    def test_semantic_search_zero_top_k(self, tmp_path):
        vector_store._VECTOR_DB_DIR = tmp_path
        vector_store.index_wiki_entry(_ref("X"), "some content", [])
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
            vector_store.index_wiki_entry(_ref(f"Entry {i}"), f"unique content number {i}", [])

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
        # WHY rel_path keys ("Entry {i}.md"), not title keys (PR-2): the
        # index is now keyed by WikiRef.rel_path, not by title -- title is
        # still recoverable per-entry via final[key]["title"].
        assert all(f"Entry {i}.md" in final for i in range(6))
        assert all(final[f"Entry {i}.md"]["title"] == f"Entry {i}" for i in range(6))

    def test_save_failure_warns_on_stderr(self, tmp_path, monkeypatch, capsys):
        """Regression (P2, reviewer-agent parity note): retry exhaustion in
        _save_tfidf_index() previously vanished silently -- unlike the
        sibling doc_registry/expert_registry/moc_autolink/observation_capture
        files fixed in this same audit batch, which all warn on stderr."""
        vector_store._VECTOR_DB_DIR = tmp_path
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(PermissionError))
        monkeypatch.setattr(vector_store.time, "sleep", lambda *_: None)

        vector_store.index_wiki_entry(_ref("Entry"), "some content", [])

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
        """Regression (P1, reviewer-agent finding on PR-1; mechanism updated
        for PR-3's batch rewrite): a per-file failure during indexing must
        show up as `failed`, not `indexed`. PR-3 moved the indexing logic
        inline into rebuild_index()'s own try/except (it no longer calls
        index_wiki_entry() per file at all -- see the batch-write WHY
        comment in rebuild_index() itself), so the failure is now simulated
        by making the TF vector computation itself raise, with the Chroma
        path forced off so the TF branch is deterministically exercised."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "note.md").write_text("# Note\ncontent", encoding="utf-8")

        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        monkeypatch.setattr(
            vector_store,
            "_compute_tf_normalized",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        result = vector_store.rebuild_index(wiki)
        assert result.indexed == 0
        assert result.failed == 1

    def test_failed_rebuild_does_not_save_fingerprint_and_retries(self, tmp_path, monkeypatch):
        """Regression (P1, reviewer-agent finding on PR-1; mechanism updated
        for PR-3's batch rewrite): the fingerprint is keyed on file stats,
        not indexing success -- saving it after a run with real failures
        would make the corpus "look unchanged" on every later call,
        permanently hiding the failed file from retry. The fix: skip the
        fingerprint save whenever failed > 0."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "note.md").write_text("# Note\ncontent", encoding="utf-8")

        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        monkeypatch.setattr(
            vector_store,
            "_compute_tf_normalized",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        first = vector_store.rebuild_index(wiki)
        assert first.failed == 1

        monkeypatch.undo()  # restore the real _compute_tf_normalized (and _get_chroma_collection)
        second = vector_store.rebuild_index(wiki)
        assert second.changed is True  # no fingerprint was saved -> must retry, not skip
        assert second.indexed == 1
        assert second.failed == 0

    def test_schema_version_change_forces_rebuild_of_unchanged_corpus(self, tmp_path):
        """Regression (P2, Codex review on PR #334): the fingerprint is a
        pure function of file stats, not of the code reading them. An
        installation upgrading from PR-1's fingerprint (saved when the TF
        index was still title-keyed/flat) to PR-2's rel_path-keyed/wrapped
        shape, with no wiki file touched in between, must NOT see
        changed=False -- that would leave every old-shape entry stranded in
        tf_index.json (silently skipped by the new shape-check) until an
        unrelated file edit finally forces a real rebuild. Simulates the
        upgrade by saving a fingerprint computed WITHOUT today's schema
        salt (the pre-fix behavior), then confirming the next call still
        rebuilds despite the corpus being byte-for-byte unchanged."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "note.md").write_text("# Note\ncontent", encoding="utf-8")

        files = vector_store._iter_indexable_files(wiki)
        parts = []
        for f in files:
            stat = f.stat()
            rel = f.relative_to(wiki).as_posix()
            parts.append(f"{rel}:{stat.st_size}:{stat.st_mtime_ns}")
        import hashlib

        pre_fix_fingerprint = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
        vector_store._save_fingerprint(pre_fix_fingerprint)

        result = vector_store.rebuild_index(wiki)
        assert result.changed is True
        assert result.indexed == 1

    def test_backend_becoming_available_forces_rebuild(self, tmp_path, monkeypatch):
        """Regression (same class of gap as the schema-version fix above,
        caught in external review after that fix landed): a corpus indexed
        while ChromaDB was unavailable (backend="tf") saves its fingerprint.
        If Chroma later becomes available with the corpus still unchanged,
        the fingerprint must NOT still match -- otherwise rebuild_index()
        returns early, the Chroma collection stays permanently empty, and
        semantic_search_paths()'s Chroma branch (which never falls back to
        TF-IDF just because Chroma is empty) silently returns nothing until
        an unrelated file edit forces a real rebuild."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "note.md").write_text("# Note\ncontent", encoding="utf-8")

        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        first = vector_store.rebuild_index(wiki)
        assert first.backend == "tf"
        assert first.changed is True

        monkeypatch.undo()  # Chroma "becomes available"
        # WHY also mock _get_embedder, not just _get_chroma_collection (real
        # CI failure caught after the embedder-fallback fix above: backend
        # now correctly requires BOTH collection AND embedder to choose
        # "chroma" -- this test's environment-dependent real _get_embedder()
        # happened to succeed locally (sentence-transformers installed) but
        # failed in CI (not installed/no model access), silently falling
        # back to "tf" and failing this assertion. Mocking both makes the
        # test deterministic regardless of what's installed, matching the
        # pattern already used elsewhere in this file for the same reason.
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: object())
        monkeypatch.setattr(vector_store, "_get_embedder", lambda: object())
        second = vector_store.rebuild_index(wiki)
        assert second.backend == "chroma"
        assert second.changed is True  # must re-embed into the new backend, not skip

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

    def test_deleted_file_removed_from_tf_index(self, tmp_path, monkeypatch):
        """Regression (memory-retrieval-repair-tz.md PR-3, fixes 0.4):
        rebuild_index() never removed stale entries in either backend --
        a deleted or renamed wiki file kept returning as a search hit
        forever. Index A and B, delete B's file, rebuild: B's terms must
        no longer be found, and B's rel_path must be gone from the index."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "a.md").write_text("# Entry A\nunique alpha content", encoding="utf-8")
        (wiki / "b.md").write_text("# Entry B\nunique beta content", encoding="utf-8")
        first = vector_store.rebuild_index(wiki)
        assert first.indexed == 2

        (wiki / "b.md").unlink()
        second = vector_store.rebuild_index(wiki)
        assert second.indexed == 1
        assert second.deleted == 1

        index = vector_store._load_tfidf_index()
        assert "b.md" not in index
        assert "a.md" in index
        results = vector_store.semantic_search("unique beta content", top_k=5)
        assert "Entry B" not in results

    def test_deleted_file_removed_from_chroma_collection(self, tmp_path, monkeypatch):
        """Same as test_deleted_file_removed_from_tf_index, but for the
        Chroma backend -- 0.4 explicitly named both backends as broken.
        Uses a small deterministic in-memory fake collection (real
        upsert/get/delete semantics, no optional chromadb/sentence-
        transformers dependency needed) so this test runs the same way in
        every environment, rather than depending on what happens to be
        installed."""

        class _FakeVector(list):
            def tolist(self):
                return list(self)

        class _FakeEmbedder:
            def encode(self, text):
                return _FakeVector([float(len(text))])

        class _FakeCollection:
            def __init__(self):
                self._store: dict[str, dict] = {}

            def upsert(self, ids, documents, embeddings, metadatas):
                for rid, doc, emb, meta in zip(ids, documents, embeddings, metadatas, strict=True):
                    self._store[rid] = {"document": doc, "embedding": emb, "metadata": meta}

            def get(self):
                return {"ids": list(self._store.keys())}

            def delete(self, ids):
                for rid in ids:
                    self._store.pop(rid, None)

            def count(self):
                return len(self._store)

            def query(self, query_embeddings, n_results):
                ids = list(self._store.keys())[:n_results]
                return {
                    "ids": [ids],
                    "metadatas": [[self._store[i]["metadata"] for i in ids]],
                    "distances": [[0.0 for _ in ids]],
                }

        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        fake_collection = _FakeCollection()
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: fake_collection)
        monkeypatch.setattr(vector_store, "_get_embedder", lambda: _FakeEmbedder())

        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "a.md").write_text("# Entry A\nunique gamma content", encoding="utf-8")
        (wiki / "b.md").write_text("# Entry B\nunique delta content", encoding="utf-8")
        first = vector_store.rebuild_index(wiki)
        assert first.backend == "chroma"
        assert first.indexed == 2
        assert "a.md" in fake_collection._store
        assert "b.md" in fake_collection._store

        (wiki / "b.md").unlink()
        second = vector_store.rebuild_index(wiki)
        assert second.backend == "chroma"
        assert second.indexed == 1
        assert second.deleted == 1
        assert "b.md" not in fake_collection._store
        assert "a.md" in fake_collection._store

    def test_one_of_three_files_failing_leaves_others_correctly_indexed(
        self, tmp_path, monkeypatch
    ):
        """Regression (memory-retrieval-repair-tz.md PR-3 acceptance
        criterion): a rebuild where file 2 of 3 raises during read must
        leave files 1 and 3 correctly indexed and report failed=1 -- not a
        half-written index, and not a report claiming indexed=3."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "one.md").write_text("# Entry One\nunique first content", encoding="utf-8")
        (wiki / "two.md").write_text("# Entry Two\nunique second content", encoding="utf-8")
        (wiki / "three.md").write_text("# Entry Three\nunique third content", encoding="utf-8")

        real_read_text = Path.read_text

        def flaky_read_text(self, *args, **kwargs):
            if self.name == "two.md":
                raise OSError("simulated read failure")
            return real_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", flaky_read_text)
        result = vector_store.rebuild_index(wiki)
        assert result.indexed == 2
        assert result.failed == 1

        # WHY setattr, not monkeypatch.undo() (real bug caught writing this
        # test): undo() would also restore _get_chroma_collection to the
        # real (importable in this env) chromadb -- semantic_search_paths()
        # would then query a real but EMPTY Chroma collection and return []
        # without ever falling back to the TF-IDF index this test actually
        # wrote to, since the Chroma branch never falls back just because
        # it's empty (a pre-existing, documented limitation, not something
        # this test should trip over).
        monkeypatch.setattr(Path, "read_text", real_read_text)
        results_one = vector_store.semantic_search("unique first content", top_k=5)
        results_three = vector_store.semantic_search("unique third content", top_k=5)
        assert "Entry One" in results_one
        assert "Entry Three" in results_three

    def test_total_failure_does_not_wipe_existing_index(self, tmp_path, monkeypatch):
        """Regression (P0, isolated reviewer-agent finding on PR-3,
        reproduced with a tool before fixing): a run where EVERY file fails
        to parse/embed (a transient failure -- the files themselves are
        untouched on disk) must NOT wipe a previously-good, fully populated
        index down to empty. An empty batch is ambiguous between "corpus is
        genuinely empty" and "every file failed this run" -- only the first
        is safe to write. Confirmed broken before the fix: a real run with
        2 good entries, followed by a run where every file's TF vector
        computation raised, left the index completely empty and reported
        deleted=2 as if it were legitimate cleanup."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "a.md").write_text("# Entry A\ngood content", encoding="utf-8")
        (wiki / "b.md").write_text("# Entry B\nmore good content", encoding="utf-8")
        first = vector_store.rebuild_index(wiki)
        assert first.indexed == 2

        (wiki / "c.md").write_text("# Entry C\ntriggers a rescan", encoding="utf-8")
        monkeypatch.setattr(
            vector_store,
            "_compute_tf_normalized",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        second = vector_store.rebuild_index(wiki)
        assert second.indexed == 0
        assert second.failed == 3
        assert (
            second.deleted == 0
        )  # nothing was actually removed -- it's a skipped write, not a wipe

        index_after = vector_store._load_tfidf_index()
        assert "a.md" in index_after
        assert "b.md" in index_after

    def test_chroma_delete_failure_does_not_falsely_mark_write_ok(self, tmp_path, monkeypatch):
        """Regression (P1, isolated reviewer-agent finding on PR-3): write_ok
        was previously set True right after a successful upsert, BEFORE the
        stale-entry get()/delete() step -- masking a failure isolated to
        that step. The fingerprint would then get saved anyway, and the
        stale entry would be permanently stranded (the next call sees an
        unchanged fingerprint and never retries). write_ok must only be set
        after delete() also succeeds."""

        class _FakeVector(list):
            def tolist(self):
                return list(self)

        class _FakeEmbedder:
            def encode(self, text):
                return _FakeVector([float(len(text))])

        class _FlakyDeleteCollection:
            def __init__(self):
                self._store: dict[str, dict] = {"stale.md": {}}

            def upsert(self, ids, documents, embeddings, metadatas):
                for rid, doc, emb, meta in zip(ids, documents, embeddings, metadatas, strict=True):
                    self._store[rid] = {"document": doc, "embedding": emb, "metadata": meta}

            def get(self):
                return {"ids": list(self._store.keys())}

            def delete(self, ids):
                raise RuntimeError("simulated delete failure")

            def count(self):
                return len(self._store)

        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        fake_collection = _FlakyDeleteCollection()
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: fake_collection)
        monkeypatch.setattr(vector_store, "_get_embedder", lambda: _FakeEmbedder())
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "a.md").write_text("# Entry A\ncontent", encoding="utf-8")

        result = vector_store.rebuild_index(wiki)
        assert result.failed == 0  # the file itself indexed fine
        assert result.indexed == 1  # and must be REPORTED as indexed, not reclassified
        assert result.changed is True

        # The fingerprint must NOT have been saved -- the delete failed, so
        # the run as a whole did not succeed. A second call on the exact
        # same (unchanged) corpus must retry, not silently skip.
        second = vector_store.rebuild_index(wiki)
        assert second.changed is True

    def test_write_failure_reclassifies_indexed_as_failed(self, tmp_path, monkeypatch):
        """Regression (real bug, caught re-verifying an externally-pasted
        review's claim after PR-3's own review cycle, reproduced with a
        tool before fixing): when the batch write itself fails (not a
        per-file parse error), the report previously still claimed
        `indexed=N, failed=0` while nothing was actually persisted to
        disk. `count` only ever meant "successfully parsed this run," not
        "actually written" -- those must be reclassified into `failed`
        when the write itself doesn't land."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        monkeypatch.setattr(vector_store, "_save_tfidf_index", lambda index: False)
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "a.md").write_text("# Entry A\ngood content", encoding="utf-8")
        (wiki / "b.md").write_text("# Entry B\nmore good content", encoding="utf-8")

        result = vector_store.rebuild_index(wiki)
        assert result.indexed == 0
        assert result.failed == 2

        monkeypatch.undo()
        index_after = vector_store._load_tfidf_index()
        assert index_after == {}  # nothing was actually written

    def test_chroma_available_but_embedder_unavailable_falls_back_to_tf(
        self, tmp_path, monkeypatch
    ):
        """Regression (real bug, caught re-verifying an externally-pasted
        review's claim after PR-3's own review cycle, reproduced with a
        tool before fixing): rebuild_index()'s batch rewrite decided
        `backend` once, based only on Chroma collection availability --
        unlike index_wiki_entry() (still used elsewhere), which already
        falls through to TF-IDF per-call when the embedder model fails to
        load even though a Chroma collection exists. Without this fix, a
        transient embedder-loading failure would permanently skip the
        whole corpus (all files "fail," backend stays locked to "chroma")
        instead of using the zero-dependency TF-IDF path that works fine
        on its own."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: object())
        monkeypatch.setattr(vector_store, "_get_embedder", lambda: None)
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "a.md").write_text("# Entry A\ngood content", encoding="utf-8")
        (wiki / "b.md").write_text("# Entry B\nmore good content", encoding="utf-8")

        result = vector_store.rebuild_index(wiki)
        assert result.backend == "tf"
        assert result.indexed == 2
        assert result.failed == 0

        index_after = vector_store._load_tfidf_index()
        assert "a.md" in index_after
        assert "b.md" in index_after


class TestRealTfidf:
    """Regression tests for memory-retrieval-repair-tz.md PR-4 (fixes 0.5):
    rebuild_index() now computes real corpus-wide IDF as a second pass and
    reweights every document before the atomic write; semantic_search_paths()
    applies the same IDF to the query. Before this PR, "TF-IDF" was TF-only."""

    def setup_method(self):
        self._orig_dir = vector_store._VECTOR_DB_DIR

    def teardown_method(self):
        vector_store._VECTOR_DB_DIR = self._orig_dir

    def test_rare_term_outranks_common_term_under_real_idf(self, tmp_path, monkeypatch):
        """The acceptance criterion from the spec: a query whose relevant
        term is rare corpus-wide must rank above a document match on a
        common term with the same raw count.

        WHY 50 common-only documents and a 2:1 (not 4:1) query ratio,
        recomputed by hand TWICE after CI caught real bugs: (1) the
        un-smoothed IDF formula this PR originally shipped gave "common"
        exactly 0 weight for any corpus where it appears in every
        document -- smoothing means it now floors at ~1.0 instead, so a
        small 3-document corpus is no longer enough contrast to flip the
        ranking; (2) a subsequent hand-verification used isolated term
        vectors ("raretermx" alone) instead of the actual document text
        ("# Rare Entry\nraretermx"), missing that "entry" is not a
        stopword and appears in EVERY document (both common- and
        rare-only), diluting the vectors enough that a 4:1 query ratio
        no longer flips the ranking through the real
        semantic_search_paths() pipeline -- only caught by re-verifying
        against the exact document strings the test actually writes, not
        an idealized approximation of them. With idf(common)=~1.02 (a
        floor, appears in every document) and idf(raretermx)=~4.26
        (appears in only 1 of 51 documents), a query weighted 2:1 toward
        "common" favors a pure "common" match under plain TF (0.80) but
        favors the document containing the rare, distinctive term under
        real IDF (0.63 vs 0.39) -- a genuine ranking flip. This test also
        confirms the pure-TF failure mode exists first, by disabling the
        reweight step.
        """
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        for i in range(50):
            (wiki / f"common{i}.md").write_text(f"# Common Entry {i}\ncommon", encoding="utf-8")
        (wiki / "rare.md").write_text("# Rare Entry\nraretermx", encoding="utf-8")

        # Query weighted toward the common term -- 2 "common" to 1
        # "raretermx" -- deliberately constructed so plain TF favors a
        # document that matches ONLY the common term (see docstring).
        query = "common common raretermx"

        # --- Pure TF (real IDF disabled): confirms the failure mode exists ---
        monkeypatch.setattr(vector_store, "_apply_idf", lambda vec, idf: vec)
        vector_store.rebuild_index(wiki)
        pure_tf_hits = vector_store.semantic_search_paths(query, top_k=1)
        assert pure_tf_hits[0].ref.rel_path != "rare.md", (
            "setup assumption failed: plain TF was expected to favor a "
            "common-term-only document first -- adjust the scenario, don't "
            "weaken this assertion"
        )

        # --- Real IDF (restored): must favor the rare-term document ---
        monkeypatch.undo()
        vector_store._VECTOR_DB_DIR = tmp_path / "db2"
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        wiki2 = tmp_path / "wiki2"
        wiki2.mkdir()
        for i in range(50):
            (wiki2 / f"common{i}.md").write_text(f"# Common Entry {i}\ncommon", encoding="utf-8")
        (wiki2 / "rare.md").write_text("# Rare Entry\nraretermx", encoding="utf-8")
        vector_store.rebuild_index(wiki2)
        real_idf_hits = vector_store.semantic_search_paths(query, top_k=1)
        assert real_idf_hits[0].ref.rel_path == "rare.md", (
            "real IDF must rank the document containing the rare, "
            "distinctive term first once idf(raretermx) is large enough "
            "to overcome the query's 4:1 bias toward the common term"
        )

    def test_adding_one_document_reweights_every_existing_document(self, tmp_path, monkeypatch):
        """Regression (memory-retrieval-repair-tz.md PR-4 acceptance
        criterion, closing the design gap directly): mutating the corpus
        (adding one document) between two rebuild_index() calls must
        change the corpus-wide IDF weight applied to a term that appears
        in every PRE-EXISTING document too, not just affect the new
        document -- proving the whole-corpus reweight actually ran, not
        a per-document patch (which is structurally impossible for real
        IDF).

        WHY this checks the idf sidecar plus the EFFECTIVE (search-time)
        weighting rather than the documents' STORED vectors: a CI run
        caught a real bug in an earlier version of this PR that baked
        idf into stored documents at index time -- if the idf sidecar
        and the document index ever desynchronized (partial write
        failure, or a stale/deleted sidecar), stored documents and a
        fresh query could be weighted by two DIFFERENT idf models,
        silently producing wrong rankings (verified by hand: an
        identical query/document pair that should score 1.0 scored as
        low as ~0.01, and in one case an irrelevant document outranked
        the relevant one). Fixed by never baking idf into storage --
        see rebuild_index()'s TF branch and semantic_search_paths()'s
        own WHY comments. Documents are always saved as plain TF; this
        test proves the reweight happens entirely inside _load_idf() +
        _apply_idf(), applied fresh and symmetrically."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        # "shared" appears in both initial documents -> df=2, N=2 ->
        # smoothed idf = log((2+1)/(2+1)) + 1 = 1.0 (the smoothed floor
        # -- never exactly 0, unlike the un-smoothed formula CI caught
        # as a bug for single-document/every-doc-shares-term corpora).
        (wiki / "a.md").write_text("# Entry A\nshared", encoding="utf-8")
        (wiki / "b.md").write_text("# Entry B\nshared", encoding="utf-8")
        vector_store.rebuild_index(wiki)

        index_before = vector_store._load_tfidf_index()
        raw_a = index_before["a.md"]["vector"]
        raw_b = index_before["b.md"]["vector"]
        # Documents are stored as plain TF, never idf-weighted at index
        # time -- "shared" is present at its raw TF weight, not zeroed.
        assert raw_a.get("shared", 0.0) > 0.0
        assert raw_b.get("shared", 0.0) > 0.0

        idf_before = vector_store._load_idf()
        assert idf_before["shared"] == 1.0

        # Add a THIRD document that does NOT contain "shared" -> df stays 2,
        # but N becomes 3 -> idf(shared) = log(4/3) + 1 ≈ 1.288, now higher.
        (wiki / "c.md").write_text("# Entry C\nunrelated", encoding="utf-8")
        vector_store.rebuild_index(wiki)

        index_after = vector_store._load_tfidf_index()
        # The stored (raw TF) vectors for the PRE-EXISTING documents must
        # be byte-for-byte unchanged -- reweighting never touches storage.
        assert index_after["a.md"]["vector"] == raw_a
        assert index_after["b.md"]["vector"] == raw_b

        idf_after = vector_store._load_idf()
        assert idf_after["shared"] > idf_before["shared"]

        # The EFFECTIVE weighting applied to each PRE-EXISTING document's
        # raw vector (via _apply_idf, exactly as semantic_search_paths()
        # applies it at search time) must reflect the new idf --
        # symmetrically for BOTH pre-existing documents, proving the
        # whole-corpus reweight actually happened and isn't special-cased
        # to just the new document c.md getting indexed.
        weighted_a_before = vector_store._apply_idf(raw_a, idf_before)
        weighted_a_after = vector_store._apply_idf(raw_a, idf_after)
        weighted_b_before = vector_store._apply_idf(raw_b, idf_before)
        weighted_b_after = vector_store._apply_idf(raw_b, idf_after)
        assert weighted_a_before != weighted_a_after
        assert weighted_b_before != weighted_b_after
        assert weighted_a_after["shared"] > 0.0
        assert weighted_b_after["shared"] > 0.0

    def test_query_side_idf_applied(self, tmp_path, monkeypatch):
        """Sanity: the idf sidecar is actually written and actually
        consulted at search time, not just at index time."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "a.md").write_text("# Entry A\ndistinctive content here", encoding="utf-8")
        (wiki / "b.md").write_text("# Entry B\nunrelated other text", encoding="utf-8")
        vector_store.rebuild_index(wiki)

        idf = vector_store._load_idf()
        assert idf  # sidecar must exist and be non-empty after a real rebuild
        assert "distinctive" in idf or "content" in idf

        results = vector_store.semantic_search_paths("distinctive content", top_k=3)
        rel_paths = {h.ref.rel_path for h in results}
        assert "a.md" in rel_paths

    def test_empty_idf_sidecar_falls_back_to_plain_tf(self, tmp_path):
        """Regression (real bug caught before it reached other tests): an
        empty/missing idf sidecar must NOT zero out the query vector
        entirely (which would return [] even for a real match) -- it must
        fall back to plain-TF comparison, matching the pre-PR-4 behavior
        used by callers of the low-level index_wiki_entry() path directly
        (which stays TF-only by design and never writes an idf sidecar)."""
        vector_store._VECTOR_DB_DIR = tmp_path
        vector_store.index_wiki_entry(
            WikiRef(rel_path="direct.md", title="Direct Entry"),
            "hook session python code",
            ["hooks"],
        )
        assert vector_store._load_idf() == {}  # no rebuild_index() ran -> no sidecar

        results = vector_store.semantic_search_paths("python session", top_k=3)
        rel_paths = {h.ref.rel_path for h in results}
        assert "direct.md" in rel_paths

    def test_partial_write_failure_deletes_idf_sidecar_not_leaves_it_stale(
        self, tmp_path, monkeypatch
    ):
        """Regression (real bug, found by hand-tracing before any reviewer
        saw this diff): if tf_index.json's write succeeds but
        idf_weights.json's write then fails, leaving a STALE idf paired
        with FRESHLY-reweighted documents produces SILENTLY WRONG
        similarity scores at search time (verified by hand: a document and
        query with identical term content scored 1.0 under a consistent
        idf but only ~0.01 under a mismatched one -- worse than returning
        no results, because it looks like a real answer). The fix deletes
        the idf sidecar on a partial failure, forcing the safe
        empty-idf-falls-back-to-plain-TF path instead of a mismatched pair."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "a.md").write_text("# Entry A\nalpha beta", encoding="utf-8")
        (wiki / "b.md").write_text("# Entry B\nalpha alpha alpha", encoding="utf-8")
        first = vector_store.rebuild_index(wiki)
        assert first.indexed == 2
        idf_before = vector_store._load_idf()
        assert idf_before  # a real, non-empty idf exists after the first rebuild

        # Simulate the tf_index write succeeding but the idf sidecar write
        # failing on a SECOND rebuild (corpus changed, so it isn't skipped
        # as unchanged).
        (wiki / "c.md").write_text("# Entry C\ngamma", encoding="utf-8")
        monkeypatch.setattr(vector_store, "_save_idf", lambda idf: False)
        second = vector_store.rebuild_index(wiki)
        # WHY indexed==0, failed==3, not indexed==3 (matches PR-3's own
        # report-accuracy reclassification: data_written requires BOTH
        # files to succeed, so a partial write correctly reports "not
        # trustworthy this run" even though tf_index.json itself DID get
        # written -- checked directly below).
        assert second.indexed == 0
        assert second.failed == 3
        assert second.changed is True  # fingerprint not saved -> next call retries

        # The documents themselves WERE physically written to tf_index.json...
        index_on_disk = vector_store._load_tfidf_index()
        assert len(index_on_disk) == 3
        # ...but the stale idf from the FIRST rebuild must be gone, not left
        # mismatched against these freshly-reweighted documents.
        assert vector_store._load_idf() == {}

        monkeypatch.undo()  # restore the real _save_idf and _get_chroma_collection
        monkeypatch.setattr(vector_store, "_get_chroma_collection", lambda: None)
        # A subsequent rebuild (nothing changed -- but data_written was
        # False last time, so the fingerprint wasn't saved) must retry and
        # restore a consistent, non-empty idf.
        third = vector_store.rebuild_index(wiki)
        assert third.changed is True
        assert vector_store._load_idf()  # a real idf exists again
