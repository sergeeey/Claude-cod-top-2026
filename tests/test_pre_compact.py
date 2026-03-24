"""Tests for pre_compact.py: pending task extraction + goals.md persistence."""

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
