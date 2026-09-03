"""End-to-end integration test for the raw -> wiki -> vector-index -> search chain.

WHY (memory-retrieval-repair-tz.md §0.6): tests/test_vector_store.py (29 tests, before
this file) and tests/test_knowledge_librarian.py both test their own module in
isolation -- neither exercises the full pipeline a real Stop-event hook actually
runs. That gap is exactly how §0.1 (PARA sub-directories invisible to the vector
index) shipped behind a fully green suite: every unit test wrote its fixture
files directly into a flat wiki/ root, so glob("*.md") never had a PARA subdir
to miss. This file writes a RAW note and drives it through the real production
functions (process_raw_to_wiki -> rebuild_index -> semantic_search), the same
sequence raw_to_wiki.main() runs on every Stop event.
"""

from __future__ import annotations

import raw_to_wiki
import vector_store


class TestFullRetrievalChain:
    def setup_method(self):
        self._orig_dir = vector_store._VECTOR_DB_DIR

    def teardown_method(self):
        vector_store._VECTOR_DB_DIR = self._orig_dir

    def test_para_routed_note_is_indexed_and_searchable(self, tmp_path, monkeypatch):
        """The exact reproduction from the spec: a raw note tagged #project
        gets routed into wiki/projects/ (not the flat wiki root), and must
        still be indexed and retrievable by semantic_search().

        WHY monkeypatch cogniml_client.push_wiki_entry: that call reaches
        out to an external service by default -- this test only needs the
        local raw->wiki->vector-index chain, not network I/O.
        """
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        monkeypatch.setattr(raw_to_wiki.cogniml_client, "push_wiki_entry", lambda *a, **k: None)

        raw_dir = tmp_path / "raw"
        wiki_dir = tmp_path / "wiki"
        raw_dir.mkdir()
        (raw_dir / "note.md").write_text(
            "# AUC Red Flags\n\n#project\n\n"
            "Common pitfalls when evaluating classifier AUC on imbalanced data.",
            encoding="utf-8",
        )

        processed = raw_to_wiki.process_raw_to_wiki(raw_dir, wiki_dir)
        assert processed == 1

        # The note must have landed under wiki/projects/, not the flat root --
        # this is the exact PARA-routing behaviour §0.1 made invisible to search.
        projects_files = list((wiki_dir / "projects").glob("*.md"))
        assert len(projects_files) == 1

        report = vector_store.rebuild_index(wiki_dir)
        assert report.changed is True
        assert report.indexed == 1
        assert report.failed == 0

        results = vector_store.semantic_search("AUC classifier evaluation pitfalls", top_k=3)
        assert "AUC Red Flags" in results

    def test_second_rebuild_with_no_new_notes_is_a_no_op(self, tmp_path, monkeypatch):
        """The corpus-fingerprint fast path, exercised through the real
        raw_to_wiki entry point rather than calling rebuild_index directly."""
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        monkeypatch.setattr(raw_to_wiki.cogniml_client, "push_wiki_entry", lambda *a, **k: None)

        raw_dir = tmp_path / "raw"
        wiki_dir = tmp_path / "wiki"
        raw_dir.mkdir()
        (raw_dir / "note.md").write_text("# Note\n\n#project\n\nSome content.", encoding="utf-8")
        raw_to_wiki.process_raw_to_wiki(raw_dir, wiki_dir)
        first = vector_store.rebuild_index(wiki_dir)
        assert first.changed is True

        second = vector_store.rebuild_index(wiki_dir)
        assert second.changed is False
        assert second.indexed == 0
