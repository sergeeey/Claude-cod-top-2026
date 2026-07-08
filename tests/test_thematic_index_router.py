"""Tests for hooks/thematic_index_router.py — route wiki entries to thematic indices."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
)

from thematic_index_router import route_entry, update_thematic_index

# ── route_entry ────────────────────────────────────────────────────────────────


class TestRouteEntry:
    """route_entry() determines which thematic index a wiki entry belongs to."""

    # ── Lessons index ──────────────────────────────────────────────────────────

    def test_avoid_tag_routes_to_lessons(self):
        # ARRANGE: tag "avoid" indicates an anti-pattern entry
        result = route_entry("Some bug fix", ["avoid"], "Content")
        # ASSERT: goes to Lessons index
        assert result == "Lessons.index.md"

    def test_postmortem_tag_routes_to_lessons(self):
        result = route_entry("Postmortem entry", ["postmortem"], "Details")
        assert result == "Lessons.index.md"

    def test_avoid_marker_in_content_routes_to_lessons(self):
        # ARRANGE: content contains [AVOID] keyword (not just a tag)
        result = route_entry("Some note", [], "This is [AVOID] at all costs.")
        assert result == "Lessons.index.md"

    def test_repeat_marker_in_content_routes_to_lessons(self):
        result = route_entry("Good pattern", [], "[REPEAT] this approach.")
        assert result == "Lessons.index.md"

    def test_postmortem_cyrillic_in_content_routes_to_lessons(self):
        # ARRANGE: Russian word "постмортем" in content
        result = route_entry("Ретро", [], "постмортем сессии после PR #104")
        assert result == "Lessons.index.md"

    # ── Projects index ─────────────────────────────────────────────────────────

    def test_geomiro_tag_routes_to_projects(self):
        result = route_entry("GeoMiro sprint notes", ["geomiro"], "Content")
        assert result == "Projects.index.md"

    def test_reflexio_tag_routes_to_projects(self):
        result = route_entry("Reflexio retrospective", ["reflexio"], "Content")
        assert result == "Projects.index.md"

    def test_retrospective_title_prefix_routes_to_projects(self):
        # ARRANGE: title starts with "retrospective:" (case-insensitive)
        result = route_entry("Retrospective: Sprint 7", [], "Notes.")
        assert result == "Projects.index.md"

    # ── Claude Code index ──────────────────────────────────────────────────────

    def test_hooks_tag_routes_to_claude_code(self):
        result = route_entry("New hook", ["hooks"], "Added input_guard.")
        assert result == "Claude-Code.index.md"

    def test_feat_in_title_routes_to_claude_code(self):
        # ARRANGE: title starts with "feat:" (commit message style)
        result = route_entry("feat: add knowledge librarian", [], "Content")
        assert result == "Claude-Code.index.md"

    def test_fix_in_title_routes_to_claude_code(self):
        result = route_entry("fix: ruff import error", [], "Removed unused import.")
        assert result == "Claude-Code.index.md"

    def test_agents_tag_routes_to_claude_code(self):
        result = route_entry("Agent refactor", ["agents"], "Content")
        assert result == "Claude-Code.index.md"

    # ── No match → None ────────────────────────────────────────────────────────

    def test_unrecognised_tags_return_none(self):
        # ARRANGE: tags and content that don't match any routing rule
        result = route_entry("Random note", ["unrelated", "unknown"], "Nothing special here.")
        assert result is None

    def test_empty_everything_returns_none(self):
        result = route_entry("", [], "")
        assert result is None

    # ── Priority ordering ──────────────────────────────────────────────────────

    def test_lessons_beats_claude_code_when_both_match(self):
        # ARRANGE: "avoid" tag AND "hooks" tag — lessons is checked first in code
        result = route_entry("Bad hook pattern", ["avoid", "hooks"], "[AVOID]")
        # ASSERT: Lessons wins because it's checked first in route_entry()
        assert result == "Lessons.index.md"


# ── update_thematic_index ──────────────────────────────────────────────────────


class TestUpdateThematicIndex:
    def test_prepends_to_existing_recent_section(self, tmp_path):
        # ARRANGE: index file with ## Recent marker
        index_path = tmp_path / "Claude-Code.index.md"
        index_path.write_text(
            "# Claude Code\n\n## Recent\n\n- [[old entry]] — #old\n", encoding="utf-8"
        )

        # ACT: add new entry
        update_thematic_index(index_path, "[[new entry]]", "#hooks")

        # ASSERT: new entry appears before the old one
        content = index_path.read_text(encoding="utf-8")
        assert "[[new entry]]" in content
        new_pos = content.index("[[new entry]]")
        old_pos = content.index("[[old entry]]")
        assert new_pos < old_pos

    def test_creates_recent_section_if_absent(self, tmp_path):
        # ARRANGE: index without ## Recent section
        index_path = tmp_path / "Lessons.index.md"
        index_path.write_text("# Lessons\n\n## Archive\n\nOld stuff.\n", encoding="utf-8")

        # ACT
        update_thematic_index(index_path, "[[new lesson]]", "#avoid")

        # ASSERT: ## Recent section was created and entry added
        content = index_path.read_text(encoding="utf-8")
        assert "## Recent" in content
        assert "[[new lesson]]" in content

    def test_missing_index_file_does_not_crash(self, tmp_path):
        # ARRANGE: index file doesn't exist
        index_path = tmp_path / "NonExistent.index.md"

        # ACT / ASSERT: should silently do nothing (no crash)
        update_thematic_index(index_path, "[[entry]]", "#tag")
        # No exception = pass

    def test_uses_pinned_marker_when_present(self, tmp_path):
        # ARRANGE: index uses "## 📌 Recent" variant
        index_path = tmp_path / "Projects.index.md"
        index_path.write_text(
            "# Projects\n\n## 📌 Recent\n\n- [[old project]] — #geomiro\n",
            encoding="utf-8",
        )

        # ACT
        update_thematic_index(index_path, "[[new project]]", "#reflexio")

        # ASSERT: both the pinned marker and the new entry are present
        content = index_path.read_text(encoding="utf-8")
        assert "📌" in content
        assert "[[new project]]" in content

    def test_tags_string_appended_to_entry(self, tmp_path):
        # ARRANGE: minimal index
        index_path = tmp_path / "index.md"
        index_path.write_text("# Index\n\n## Recent\n\n", encoding="utf-8")

        # ACT
        update_thematic_index(index_path, "[[my entry]]", "#hooks, #feat")

        # ASSERT: tags are included in the appended line
        content = index_path.read_text(encoding="utf-8")
        assert "#hooks" in content or "hooks" in content

    def test_already_linked_entry_not_duplicated(self, tmp_path):
        """Regression (MEDIUM, cross-model audit): every SessionEnd within
        the 5-minute "recent" window re-globbed the same wiki entry and
        called update_thematic_index() unconditionally -- without an
        existing-link check the same entry was prepended again on every
        run."""
        index_path = tmp_path / "Claude-Code.index.md"
        index_path.write_text(
            "# Claude Code\n\n## Recent\n\n- [[my entry]] — #hooks\n", encoding="utf-8"
        )

        update_thematic_index(index_path, "[[my entry]]", "#hooks")

        content = index_path.read_text(encoding="utf-8")
        assert content.count("[[my entry]]") == 1

    def test_six_concurrent_updates_to_same_index_all_linked(self, tmp_path):
        """Regression (MEDIUM, cross-model audit): concurrent note writes
        routed to the SAME index previously raced on an unlocked
        read-modify-write, so one write could overwrite another's link."""
        import threading

        index_path = tmp_path / "Claude-Code.index.md"
        index_path.write_text("# Claude Code\n\n## Recent\n\n", encoding="utf-8")

        # WHY 6 threads, not a larger number: see doc_registry's sibling
        # test (tests/test_doc_registry.py) for the full explanation.
        def run_one(i: int) -> None:
            update_thematic_index(index_path, f"[[entry_{i}]]", "#hooks")

        threads = [threading.Thread(target=run_one, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final = index_path.read_text(encoding="utf-8")
        for i in range(6):
            assert f"[[entry_{i}]]" in final, (
                f"entry_{i} link missing -- lost to a concurrent write"
            )

    def test_write_failure_warns_on_stderr(self, tmp_path, capsys):
        """Regression (LOW, mirrors moc_autolink.py's sibling fix): a failed
        index write previously vanished with zero signal."""
        from unittest import mock

        index_path = tmp_path / "Claude-Code.index.md"
        index_path.write_text("# Claude Code\n\n## Recent\n\n", encoding="utf-8")

        with mock.patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
            update_thematic_index(index_path, "[[my entry]]", "#hooks")

        captured = capsys.readouterr()
        assert "thematic-index-router" in captured.err
        assert str(index_path) in captured.err
