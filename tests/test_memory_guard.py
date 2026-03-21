"""Tests for memory_guard.py.

WHY: memory_guard reminds to update activeContext.md after git commit.
Tests mock stdin, the filesystem, and time — without real git operations.
"""

import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402

import pytest  # noqa: E402


def make_stdin(data: dict) -> io.StringIO:
    """Helper function to mock stdin with JSON data."""
    return io.StringIO(json.dumps(data))


def make_commit_input(command: str = "git commit -m 'feat: x'", response_stdout: str = "") -> dict:
    """Create typical PostToolUse hook data for git commit."""
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"stdout": response_stdout},
    }


class TestMemoryGuardMain:
    """Tests for main() via mocking stdin and the filesystem."""

    def test_skips_non_commit(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Command 'ls' — not git commit, hook stays silent."""
        data = make_commit_input(command="ls -la")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import memory_guard

        memory_guard.main()

        captured = capsys.readouterr()
        # WHY: early return when "git commit" is not in the command
        assert captured.out == ""
        assert captured.err == ""

    def test_skips_failed_commit(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Failed commit ('nothing to commit') — hook stays silent."""
        data = make_commit_input(response_stdout="nothing to commit, working tree clean")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import memory_guard

        memory_guard.main()

        captured = capsys.readouterr()
        # WHY: is_failed_commit() returns True → early return
        assert captured.out == ""

    def test_warns_when_no_active_context(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Successful commit without activeContext.md — warning to create the file."""
        data = make_commit_input(response_stdout="[feature/x abc1234] feat: done")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        # WHY: find_project_memory() = None means the project has no
        # .claude/memory/activeContext.md — hook reminds to create it
        with patch("memory_guard.find_project_memory", return_value=None):
            import memory_guard

            memory_guard.main()

        captured = capsys.readouterr()
        assert "activeContext" in captured.out

    def test_warns_on_stale_context(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """activeContext.md older than 5 minutes after commit — UPDATE REQUIRED warning."""
        data = make_commit_input(response_stdout="[feature/x abc1234] feat: done")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        # WHY: we create a mock Path with st_mtime = 10 minutes ago
        mock_path = MagicMock(spec=Path)
        mock_stat = MagicMock()
        mock_stat.st_mtime = time.time() - 600  # 10 minutes ago
        mock_path.stat.return_value = mock_stat

        with patch("memory_guard.find_project_memory", return_value=mock_path):
            import memory_guard

            memory_guard.main()

        captured = capsys.readouterr()
        assert "UPDATE REQUIRED" in captured.out

    def test_silent_on_fresh_context(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """activeContext.md updated 2 minutes ago — hook stays silent."""
        data = make_commit_input(response_stdout="[feature/x abc1234] feat: done")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        # WHY: age = 2 min < threshold 5 min → hook does not emit a warning
        mock_path = MagicMock(spec=Path)
        mock_stat = MagicMock()
        mock_stat.st_mtime = time.time() - 120  # 2 minutes ago
        mock_path.stat.return_value = mock_stat

        with patch("memory_guard.find_project_memory", return_value=mock_path):
            import memory_guard

            memory_guard.main()

        captured = capsys.readouterr()
        assert captured.out == ""
