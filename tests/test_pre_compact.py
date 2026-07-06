"""Tests for pre_compact.py: pending task extraction + goals.md persistence
+ progressive summary compression."""

from pathlib import Path

import pytest


class TestExtractPendingItems:
    """pre_compact.extract_pending_items: regex matching."""

    def test_todo_items(self) -> None:
        from pre_compact import extract_pending_items

        content = "- TODO fix auth\n- done stuff\n- TODO add tests"
        result = extract_pending_items(content)
        assert len(result) == 2
        assert "TODO fix auth" in result[0]

    def test_next_and_pending(self) -> None:
        from pre_compact import extract_pending_items

        content = "* NEXT deploy v2\n- PENDING review\n- completed"
        result = extract_pending_items(content)
        assert len(result) == 2

    def test_blocked_and_wip(self) -> None:
        from pre_compact import extract_pending_items

        content = "- BLOCKED on infra\n- WIP refactor\n- IN PROGRESS migration"
        result = extract_pending_items(content)
        assert len(result) == 3

    def test_checkbox_format(self) -> None:
        from pre_compact import extract_pending_items

        content = "- [ ] TODO write docs\n- [x] done item"
        result = extract_pending_items(content)
        assert len(result) == 1
        assert "TODO" in result[0]

    def test_no_matches(self) -> None:
        from pre_compact import extract_pending_items

        content = "# Active Context\n## Updated: 2026-03-24\nJust notes"
        assert extract_pending_items(content) == []

    def test_empty_content(self) -> None:
        from pre_compact import extract_pending_items

        assert extract_pending_items("") == []

    def test_case_insensitive(self) -> None:
        from pre_compact import extract_pending_items

        content = "- todo lowercase\n- Todo mixed\n- Pending check"
        result = extract_pending_items(content)
        assert len(result) == 3


class TestSavePendingToGoals:
    """pre_compact.save_pending_to_goals: file persistence."""

    def test_creates_goals_file(self, tmp_path: Path) -> None:
        from pre_compact import save_pending_to_goals

        active = tmp_path / "activeContext.md"
        active.write_text("test")
        items = ["TODO fix auth", "NEXT deploy"]
        save_pending_to_goals(items, active)

        goals = tmp_path / "goals.md"
        assert goals.exists()
        content = goals.read_text()
        assert "# Goals" in content
        assert "TODO fix auth" in content
        assert "NEXT deploy" in content
        assert "compaction" in content

    def test_appends_to_existing_goals(self, tmp_path: Path) -> None:
        from pre_compact import save_pending_to_goals

        active = tmp_path / "activeContext.md"
        active.write_text("test")
        goals = tmp_path / "goals.md"
        goals.write_text("# Goals\n\n## Existing\n- old goal\n")

        save_pending_to_goals(["TODO new task"], active)
        content = goals.read_text()
        assert "old goal" in content
        assert "TODO new task" in content

    def test_empty_items_no_write(self, tmp_path: Path) -> None:
        from pre_compact import save_pending_to_goals

        active = tmp_path / "activeContext.md"
        active.write_text("test")
        save_pending_to_goals([], active)
        assert not (tmp_path / "goals.md").exists()

    def test_normalizes_leading_dash(self, tmp_path: Path) -> None:
        """extract_pending_items() returns the line with its own '- ' prefix
        intact; save_pending_to_goals must not double it into '- - Next: ...'."""
        from pre_compact import save_pending_to_goals

        active = tmp_path / "activeContext.md"
        active.write_text("test")
        save_pending_to_goals(["- Next: merge PR #57"], active)

        content = (tmp_path / "goals.md").read_text()
        assert "- Next: merge PR #57" in content
        assert "- - Next" not in content

    def test_skips_duplicate_item_already_in_goals(self, tmp_path: Path) -> None:
        """Regression: an item already recorded in goals.md must not be
        re-appended on a later compaction (was observed to duplicate 44x
        across 2026-06-21..2026-07-06 for a single stale PR reference)."""
        from pre_compact import save_pending_to_goals

        active = tmp_path / "activeContext.md"
        active.write_text("test")
        goals = tmp_path / "goals.md"
        goals.write_text(
            "# Goals\n\n### Carried from compaction (2026-06-21 08:22)\n- Next: merge PR #57\n"
        )

        saved = save_pending_to_goals(["- Next: merge PR #57"], active)

        assert saved == 0
        assert goals.read_text().count("Next: merge PR #57") == 1

    def test_saves_new_item_alongside_existing(self, tmp_path: Path) -> None:
        """Dedup must be per-item, not all-or-nothing for the whole batch."""
        from pre_compact import save_pending_to_goals

        active = tmp_path / "activeContext.md"
        active.write_text("test")
        goals = tmp_path / "goals.md"
        goals.write_text("# Goals\n\n- TODO already recorded\n")

        saved = save_pending_to_goals(["- TODO already recorded", "- NEXT genuinely new"], active)

        assert saved == 1
        content = goals.read_text()
        assert content.count("TODO already recorded") == 1
        assert "NEXT genuinely new" in content

    def test_prefix_of_existing_line_is_not_falsely_deduped(self, tmp_path: Path) -> None:
        """Regression (reviewer-caught P1): a naive substring check treats a
        new item as a duplicate whenever it happens to be a text-prefix of an
        already-saved longer line, silently dropping a genuinely different
        item. Dedup must compare whole bullet lines, not substrings."""
        from pre_compact import save_pending_to_goals

        active = tmp_path / "activeContext.md"
        active.write_text("test")
        goals = tmp_path / "goals.md"
        goals.write_text("# Goals\n\n- Next: merge PR #57 into main and deploy\n")

        saved = save_pending_to_goals(["- Next: merge PR #57"], active)

        assert saved == 1
        assert "- Next: merge PR #57\n" in goals.read_text() or goals.read_text().endswith(
            "- Next: merge PR #57\n"
        )

    def test_item_text_embedded_in_prose_is_not_falsely_deduped(self, tmp_path: Path) -> None:
        """Regression (reviewer-caught P1): the item text appearing inside an
        unrelated paragraph (not as its own bullet) must not count as
        already-recorded."""
        from pre_compact import save_pending_to_goals

        active = tmp_path / "activeContext.md"
        active.write_text("test")
        goals = tmp_path / "goals.md"
        goals.write_text("# Goals\n\nSome note mentions - Next: ship it in passing prose.\n")

        saved = save_pending_to_goals(["- Next: ship it"], active)

        assert saved == 1

    def test_strips_checkbox_marker(self, tmp_path: Path) -> None:
        """extract_pending_items() also matches "- [ ] TODO ..." checkbox
        lines; the checkbox marker must be stripped alongside the dash so
        goals.md doesn't end up with "- [ ] TODO ..." double-marked lines."""
        from pre_compact import save_pending_to_goals

        active = tmp_path / "activeContext.md"
        active.write_text("test")
        save_pending_to_goals(["- [ ] TODO write docs"], active)

        content = (tmp_path / "goals.md").read_text()
        assert "- TODO write docs" in content
        assert "[ ]" not in content


class TestPreCompactMain:
    """pre_compact.main: full flow with pending extraction."""

    def test_main_extracts_and_saves(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        from pre_compact import main

        mem_dir = tmp_path / ".claude" / "memory"
        mem_dir.mkdir(parents=True)
        active = mem_dir / "activeContext.md"
        active.write_text("## Updated: 2026-01-01\n- TODO fix auth\n- NEXT deploy\n- done stuff")
        (tmp_path / ".claude" / "logs").mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr("pre_compact.find_project_memory", lambda: active)
        monkeypatch.setattr(
            "pre_compact.os.path.expanduser",
            lambda p: str(tmp_path / p.replace("~/", "").replace("~\\", "")),
        )

        main()
        output = capsys.readouterr().out
        assert "2 pending items" in output
        assert "goals.md" in output

        goals = mem_dir / "goals.md"
        assert goals.exists()
        assert "TODO fix auth" in goals.read_text()

    def test_main_no_pending_no_goals(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        from pre_compact import main

        mem_dir = tmp_path / ".claude" / "memory"
        mem_dir.mkdir(parents=True)
        active = mem_dir / "activeContext.md"
        active.write_text("## Updated: 2026-01-01\n- all done")

        monkeypatch.setattr("pre_compact.find_project_memory", lambda: active)
        monkeypatch.setattr(
            "pre_compact.os.path.expanduser",
            lambda p: str(tmp_path / p.replace("~/", "").replace("~\\", "")),
        )

        main()
        assert not (mem_dir / "goals.md").exists()


# ──────────────────────────────────────────────────────────────────────────────
# New tests: _parse_sections, _summarize_lines, _create_progressive_summary
# ──────────────────────────────────────────────────────────────────────────────


class TestParseSections:
    """pre_compact._parse_sections: markdown H2 parsing."""

    def test_preamble_only(self) -> None:
        from pre_compact import _parse_sections

        preamble, sections = _parse_sections("# Title\nsome text")
        assert sections == []
        assert "# Title" in preamble

    def test_single_section(self) -> None:
        from pre_compact import _parse_sections

        content = "# Title\n## Section One\nline1\nline2"
        preamble, sections = _parse_sections(content)
        assert len(sections) == 1
        assert sections[0].heading == "## Section One"
        assert sections[0].lines == ["line1", "line2"]

    def test_multiple_sections(self) -> None:
        from pre_compact import _parse_sections

        content = "# Title\n## A\nalpha\n## B\nbeta\ngamma"
        _, sections = _parse_sections(content)
        assert len(sections) == 2
        assert sections[0].heading == "## A"
        assert sections[1].lines == ["beta", "gamma"]

    def test_empty_string(self) -> None:
        from pre_compact import _parse_sections

        preamble, sections = _parse_sections("")
        assert sections == []
        assert preamble == []


class TestSummarizeLines:
    """pre_compact._summarize_lines: representative one-liner."""

    def test_picks_first_nonempty(self) -> None:
        from pre_compact import _summarize_lines

        result = _summarize_lines(["", "  ", "First real line", "second line"])
        assert result == "First real line"

    def test_skips_bare_list_markers(self) -> None:
        from pre_compact import _summarize_lines

        result = _summarize_lines(["-", "*", "actual content"])
        assert result == "actual content"

    def test_truncates_long_lines(self) -> None:
        from pre_compact import _summarize_lines

        long = "x" * 200
        result = _summarize_lines([long])
        assert len(result) <= 123  # 120 chars + "..."
        assert result.endswith("...")

    def test_empty_fallback(self) -> None:
        from pre_compact import _summarize_lines

        assert _summarize_lines([]) == "(empty section)"
        assert _summarize_lines(["", "  "]) == "(empty section)"


class TestCreateProgressiveSummary:
    """pre_compact._create_progressive_summary: file compression."""

    def test_returns_false_when_file_missing(self, tmp_path: Path) -> None:
        from pre_compact import _create_progressive_summary

        assert _create_progressive_summary(tmp_path / "missing.md") is False

    def test_returns_false_when_no_sections(self, tmp_path: Path) -> None:
        from pre_compact import _create_progressive_summary

        f = tmp_path / "activeContext.md"
        f.write_text("# Just a title\nno h2 sections here")
        assert _create_progressive_summary(f) is False

    def test_short_section_unchanged(self, tmp_path: Path) -> None:
        from pre_compact import _create_progressive_summary

        f = tmp_path / "activeContext.md"
        f.write_text("# Title\n## Status\nline1\nline2\n")
        result = _create_progressive_summary(f)
        # 2 lines <= VERBATIM_TAIL=20, so content should not change meaningfully
        assert result is False

    def test_long_section_gets_compressed(self, tmp_path: Path) -> None:
        from pre_compact import _create_progressive_summary

        lines = [f"old line {i}" for i in range(25)]
        content = "# Title\n## Status\n" + "\n".join(lines) + "\n"
        f = tmp_path / "activeContext.md"
        f.write_text(content)

        result = _create_progressive_summary(f)
        assert result is True

        new_content = f.read_text()
        output_lines = new_content.splitlines()

        # The head (lines 0-4, i.e. 25 - VERBATIM_TAIL=20 = 5 lines) is
        # replaced by a single [summarized] marker.  Lines 1-4 must NOT
        # appear as standalone lines (line 0 may appear inside the summary).
        assert not any(line.strip() == "old line 3" for line in output_lines)
        assert not any(line.strip() == "old line 4" for line in output_lines)
        # The last 20 lines (indices 5-24) must survive verbatim
        assert any(line.strip() == "old line 5" for line in output_lines)
        assert any(line.strip() == "old line 24" for line in output_lines)
        assert any("[summarized]" in line for line in output_lines)

    def test_protected_section_kept_verbatim(self, tmp_path: Path) -> None:
        from pre_compact import _create_progressive_summary

        old_lines = "\n".join(f"detail {i}" for i in range(25))
        content = f"# Title\n## Error: DB timeout\n{old_lines}\n"
        f = tmp_path / "activeContext.md"
        f.write_text(content)

        _create_progressive_summary(f)
        new_content = f.read_text()

        # All original detail lines must survive for a protected section
        assert "detail 0" in new_content
        assert "detail 24" in new_content
        assert "[summarized]" not in new_content

    def test_decision_section_kept_verbatim(self, tmp_path: Path) -> None:
        from pre_compact import _create_progressive_summary

        body = "\n".join(f"rationale {i}" for i in range(30))
        content = f"# Title\n## Decision: use Postgres\n{body}\n"
        f = tmp_path / "activeContext.md"
        f.write_text(content)

        _create_progressive_summary(f)
        assert "rationale 0" in f.read_text()

    def test_correction_section_kept_verbatim(self, tmp_path: Path) -> None:
        from pre_compact import _create_progressive_summary

        body = "\n".join(f"note {i}" for i in range(25))
        content = f"# Title\n## Correction: never use X\n{body}\n"
        f = tmp_path / "activeContext.md"
        f.write_text(content)

        _create_progressive_summary(f)
        assert "note 0" in f.read_text()

    def test_bug_section_kept_verbatim(self, tmp_path: Path) -> None:
        from pre_compact import _create_progressive_summary

        body = "\n".join(f"trace {i}" for i in range(25))
        content = f"# Title\n## Bug: null pointer\n{body}\n"
        f = tmp_path / "activeContext.md"
        f.write_text(content)

        _create_progressive_summary(f)
        assert "trace 0" in f.read_text()

    def test_mixed_sections(self, tmp_path: Path) -> None:
        """Long normal section gets compressed; protected sections survive intact."""
        from pre_compact import _create_progressive_summary

        normal_body = "\n".join(f"work item {i}" for i in range(25))
        protected_body = "\n".join(f"decision detail {i}" for i in range(25))
        content = f"# Title\n## Status\n{normal_body}\n## Decision: chose Kafka\n{protected_body}\n"
        f = tmp_path / "activeContext.md"
        f.write_text(content)

        result = _create_progressive_summary(f)
        assert result is True
        output_lines = f.read_text().splitlines()

        # Normal section: head (items 0-4) replaced by [summarized]; tail kept
        assert not any(line.strip() == "work item 3" for line in output_lines)
        assert any(line.strip() == "work item 5" for line in output_lines)
        assert any(line.strip() == "work item 24" for line in output_lines)
        # Protected section: every line survives
        assert any(line.strip() == "decision detail 0" for line in output_lines)
        assert any(line.strip() == "decision detail 24" for line in output_lines)


class TestTrimOldEntries:
    """pre_compact._trim_old_entries: removes stale H2 sections by date."""

    def test_removes_section_aged_via_body_date(self, tmp_path: Path) -> None:
        from pre_compact import _trim_old_entries

        f = tmp_path / "activeContext.md"
        f.write_text("# Title\n## Status\nlast touched 2026-01-01\n## Recent\ntoday\n")

        removed = _trim_old_entries(f, max_age_days=90)

        assert removed == 1
        content = f.read_text()
        assert "## Status" not in content
        assert "## Recent" in content

    def test_removes_section_aged_via_heading_date(self, tmp_path: Path) -> None:
        """Regression: a date embedded only in the heading (e.g.
        "## Retrospective [2026-04-12]") was invisible to the old check,
        which only scanned body lines — such sections never aged out no
        matter how stale. Observed in production: a 2026-04-12 retrospective
        survived untrimmed through 2026-07-06."""
        from pre_compact import _trim_old_entries

        f = tmp_path / "activeContext.md"
        f.write_text("# Title\n## Retrospective [2026-01-01]\n- Next: merge PR #57\n")

        removed = _trim_old_entries(f, max_age_days=90)

        assert removed == 1
        assert "Retrospective" not in f.read_text()

    def test_keeps_recent_section(self, tmp_path: Path) -> None:
        from pre_compact import _trim_old_entries

        f = tmp_path / "activeContext.md"
        content = "# Title\n## Status\nupdated 2026-07-01\n"
        f.write_text(content)

        removed = _trim_old_entries(f, max_age_days=90)

        assert removed == 0
        assert f.read_text() == content

    def test_keeps_protected_section_regardless_of_age(self, tmp_path: Path) -> None:
        from pre_compact import _trim_old_entries

        f = tmp_path / "activeContext.md"
        f.write_text(
            "# Title\n## Decision: use Postgres [2026-01-01]\nold rationale from 2026-01-01\n"
        )

        removed = _trim_old_entries(f, max_age_days=90)

        assert removed == 0
        assert "Decision: use Postgres" in f.read_text()

    def test_keeps_section_with_no_date(self, tmp_path: Path) -> None:
        """Conservative default: no parseable date anywhere means we cannot
        judge age, so the section must be kept rather than guessed away."""
        from pre_compact import _trim_old_entries

        f = tmp_path / "activeContext.md"
        content = "# Title\n## Notes\nno dates in here at all\n"
        f.write_text(content)

        removed = _trim_old_entries(f, max_age_days=90)

        assert removed == 0
        assert f.read_text() == content

    def test_missing_file_returns_zero(self, tmp_path: Path) -> None:
        from pre_compact import _trim_old_entries

        assert _trim_old_entries(tmp_path / "missing.md") == 0

    def test_keeps_updated_marker_regardless_of_its_own_stale_timestamp(
        self, tmp_path: Path
    ) -> None:
        """Regression: including the heading in the date scan (see the
        heading-date test above) must NOT apply to the "## Updated:" line
        itself. main() rewrites that heading's timestamp at the end of every
        compaction, so at trim-time it still holds the PREVIOUS run's date —
        judging it stale by that not-yet-refreshed value would delete the
        one heading that is always meant to persist and be bumped forward."""
        from pre_compact import _trim_old_entries

        f = tmp_path / "activeContext.md"
        f.write_text("# Context\n## Updated: 2026-01-01 00:00\nSome content\n")

        removed = _trim_old_entries(f, max_age_days=90)

        assert removed == 0
        assert "## Updated:" in f.read_text()
