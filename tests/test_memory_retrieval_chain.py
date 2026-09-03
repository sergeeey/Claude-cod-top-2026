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

import knowledge_librarian
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

    def test_title_ne_stem_opens_real_file_via_index_alias(self, tmp_path, monkeypatch):
        """Regression (memory-retrieval-repair-tz.md PR-2, fixes 0.2): the
        full production chain, not just vector_store in isolation --
        raw_to_wiki routes the note into a PARA subdir with a dated-slug
        filename (title != stem, the normal case), update_wiki_index()
        writes the [[rel_path|Title]] index.md entry, and
        knowledge_librarian's own extraction + HOT-tier read must open the
        REAL file, not fail via the old title-as-filename guess.
        """
        vector_store._VECTOR_DB_DIR = tmp_path / "db"
        monkeypatch.setattr(raw_to_wiki.cogniml_client, "push_wiki_entry", lambda *a, **k: None)
        monkeypatch.setattr(knowledge_librarian, "WIKI_DIR", tmp_path / "wiki")
        monkeypatch.setattr(knowledge_librarian, "WIKI_INDEX", tmp_path / "wiki" / "index.md")

        raw_dir = tmp_path / "raw"
        wiki_dir = tmp_path / "wiki"
        raw_dir.mkdir()
        (raw_dir / "note.md").write_text(
            "# AUC Red Flags\n\n#project\n\n"
            "Common pitfalls when evaluating classifier AUC on imbalanced data.",
            encoding="utf-8",
        )

        raw_to_wiki.process_raw_to_wiki(raw_dir, wiki_dir)
        raw_to_wiki.update_wiki_index(wiki_dir)

        index_text = (wiki_dir / "index.md").read_text(encoding="utf-8")
        # The alias must carry a real rel_path distinct from the display title.
        assert "projects/" in index_text
        assert "|AUC Red Flags]]" in index_text

        candidates = knowledge_librarian._query_wiki_raw_titles(["auc", "classifier"])
        assert candidates, "note must be found via keyword match on index.md"

        hot, warm = knowledge_librarian._classify_and_render_wiki(
            candidates, ["auc", "classifier", "evaluating", "pitfalls"]
        )
        rendered = "\n".join(hot + warm)
        # Before PR-2 this failed: _read_wiki_content("AUC Red Flags") -> None
        # (guessed filename == title, real file is a dated slug), so the
        # entry would render with no snippet content at all.
        assert "AUC Red Flags" in rendered
        assert "pitfalls" in rendered.lower() or "imbalanced" in rendered.lower()
