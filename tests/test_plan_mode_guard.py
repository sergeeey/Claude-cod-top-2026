"""Tests for plan_mode_guard.py.

WHY: plan_mode_guard tracks the number of unique files touched in a session.
At 3+ files — a soft reminder, at 5+ — a hard warning. Tests isolate
the logic via mocking stdin, the tracker temp file, and has_active_plan().
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path  # noqa: E402
from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402


def make_stdin(data: dict) -> io.StringIO:
    """Helper function to mock stdin with JSON data."""
    return io.StringIO(json.dumps(data))


def make_edit_input(file_path: str, session_id: str = "test-session-001") -> dict:
    """Create PostToolUse hook data for an Edit/Write operation."""
    return {
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path},
        "session_id": session_id,
    }


class TestPlanModeGuardMain:
    """Tests for main() via mocking stdin and the file tracker."""

    def test_skips_no_file_path(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """If tool_input does not contain file_path — hook stays silent."""
        data = {
            "tool_name": "Edit",
            "tool_input": {},
            "session_id": "test-session-001",
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import plan_mode_guard

        plan_mode_guard.main()

        captured = capsys.readouterr()
        # WHY: early return when file_path is empty — nothing to track
        assert captured.out == ""

    def test_no_warning_under_3_files(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path: Path
    ) -> None:
        """2 unique files per session — no warnings."""
        session_id = "sess-under3"

        # WHY: we use tmp_path to isolate the tracker between tests.
        # We patch tempfile.gettempdir() so get_tracker_path() writes to tmp_path.
        monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))

        with patch("plan_mode_guard.has_active_plan", return_value=False):
            import plan_mode_guard

            for i in range(1, 3):  # files 1 and 2
                data = make_edit_input(f"/project/file{i}.py", session_id)
                monkeypatch.setattr("sys.stdin", make_stdin(data))
                plan_mode_guard.main()

        captured = capsys.readouterr()
        assert "plan" not in captured.out.lower()

    def test_warns_at_3_files(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path: Path
    ) -> None:
        """3 unique files — soft Plan-First reminder."""
        session_id = "sess-at3"
        monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))

        with patch("plan_mode_guard.has_active_plan", return_value=False):
            import plan_mode_guard

            for i in range(1, 4):  # files 1, 2, 3
                data = make_edit_input(f"/project/file{i}.py", session_id)
                monkeypatch.setattr("sys.stdin", make_stdin(data))
                plan_mode_guard.main()

        captured = capsys.readouterr()
        # WHY: at count==3 the hook outputs JSON with "plan-mode-guard" in additionalContext
        assert "plan-mode-guard" in captured.out
        assert "3 unique files" in captured.out

    def test_stronger_warning_at_5_files(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path: Path
    ) -> None:
        """5 unique files — stronger WARNING."""
        session_id = "sess-at5"
        monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))

        with patch("plan_mode_guard.has_active_plan", return_value=False):
            import plan_mode_guard

            for i in range(1, 6):  # files 1..5
                data = make_edit_input(f"/project/file{i}.py", session_id)
                monkeypatch.setattr("sys.stdin", make_stdin(data))
                plan_mode_guard.main()

        captured = capsys.readouterr()
        # WHY: at count==5 the hook outputs a Milestone message — more insistent than the 3-file notice
        assert "Milestone" in captured.out or "WARNING" in captured.out
        assert "plan-mode-guard" in captured.out

    def test_suppressed_when_plan_exists(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path: Path
    ) -> None:
        """When an active plan exists warnings are suppressed even at 5+ files."""
        session_id = "sess-with-plan"
        monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))

        # WHY: has_active_plan() = True → hook does early return after writing tracker,
        # emitting no warnings — the agent is working according to the plan
        with patch("plan_mode_guard.has_active_plan", return_value=True):
            import plan_mode_guard

            for i in range(1, 6):
                data = make_edit_input(f"/project/file{i}.py", session_id)
                monkeypatch.setattr("sys.stdin", make_stdin(data))
                plan_mode_guard.main()

        captured = capsys.readouterr()
        assert captured.out == ""
