"""Tests for hooks/session_start.py.

WHY: session_start.py is responsible for printing project context at Claude session start.
0% coverage → critical paths (auto_update, scope fence, project memory) are not tested.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))

from unittest.mock import MagicMock, patch  # noqa: E402

import pytest  # noqa: E402


class TestAutoUpdateConfigRepo:
    """Tests for auto_update_config_repo(): auto-update of config repo via git pull."""

    def test_auto_update_no_marker(self, tmp_path: pytest.TempdirFactory) -> None:
        """If marker file does not exist — early return, subprocess is not called.

        WHY: marker = ~/.claude/.claude-code-config-repo. If the file is absent —
        config was installed without --link, nothing to update. subprocess must not be called.
        """
        import session_start

        # WHY: patch Path.home() so the marker points to a non-existent tmp_path
        fake_home = tmp_path  # tmp_path has no .claude/.claude-code-config-repo

        with (
            patch("session_start.Path") as MockPath,
            patch("subprocess.run") as mock_run,
        ):
            # Simulate Path.home() / ".claude" / CONFIG_REPO_MARKER → does not exist
            mock_marker = MagicMock()
            mock_marker.exists.return_value = False
            MockPath.home.return_value = fake_home
            # Path(str) constructor — needed for Path(repo_path).is_dir()
            MockPath.side_effect = lambda *args, **kw: mock_marker if args == () else MagicMock()
            # Chain: Path.home() / ".claude" / marker → mock_marker
            fake_home_mock = MagicMock()
            fake_home_mock.__truediv__ = lambda self, other: (
                fake_home_mock if other == ".claude" else MagicMock()
            )
            MockPath.home.return_value = fake_home_mock
            claude_dir_mock = MagicMock()
            fake_home_mock.__truediv__ = MagicMock(return_value=claude_dir_mock)
            claude_dir_mock.__truediv__ = MagicMock(return_value=mock_marker)

            session_start.auto_update_config_repo()

        # WHY: marker.exists() → False → function does early return
        mock_run.assert_not_called()

    def test_auto_update_no_marker_via_real_path(self, tmp_path: "pytest.TempdirFactory") -> None:
        """Alternative approach: patch Path.home() returns tmp_path without marker file."""
        import session_start

        with (
            patch("session_start.Path.home", return_value=tmp_path),
            patch("subprocess.run") as mock_run,
        ):
            session_start.auto_update_config_repo()

        # tmp_path does not contain .claude/.claude-code-config-repo → early return
        mock_run.assert_not_called()


class TestPrintScopeFence:
    """Tests for print_scope_fence(): printing Scope Fence status at session start."""

    def test_print_scope_fence_no_fence(self, capsys: pytest.CaptureFixture) -> None:
        """find_scope_fence returns None → prints 'No Scope Fence'.

        WHY: no .scope-fence.md and no activeContext.md → the user
        has not configured session focus, needs to be informed.
        """
        import session_start

        with patch("session_start.find_scope_fence", return_value=None):
            session_start.print_scope_fence()

        captured = capsys.readouterr()
        # WHY: function explicitly prints "No Scope Fence found" when fence_source is None
        assert "No Scope Fence" in captured.out

    def test_print_scope_fence_with_goal(
        self, tmp_path: "pytest.TempdirFactory", capsys: pytest.CaptureFixture
    ) -> None:
        """fence file contains Goal: 'Build MVP' → prints the goal.

        WHY: main happy-path — the user set a Scope Fence,
        Claude should see the goal at the start of the session.
        """
        import session_start

        fence_file = tmp_path / ".scope-fence.md"
        fence_file.write_text(
            "## Scope Fence\nGoal: Build MVP\nNOT NOW: refactoring\n",
            encoding="utf-8",
        )

        with patch("session_start.find_scope_fence", return_value=fence_file):
            session_start.print_scope_fence()

        captured = capsys.readouterr()
        # WHY: parse_scope_fence returns {"goal": "Build MVP", "not_now": "refactoring"}
        assert "Build MVP" in captured.out
        assert "Scope Fence active" in captured.out

    def test_print_scope_fence_not_now_printed(
        self, tmp_path: "pytest.TempdirFactory", capsys: pytest.CaptureFixture
    ) -> None:
        """If NOT NOW is set — it is printed together with Goal."""
        import session_start

        fence_file = tmp_path / ".scope-fence.md"
        fence_file.write_text(
            "## Scope Fence\nGoal: Ship auth feature\nNOT NOW: dashboard redesign\n",
            encoding="utf-8",
        )

        with patch("session_start.find_scope_fence", return_value=fence_file):
            session_start.print_scope_fence()

        captured = capsys.readouterr()
        assert "Ship auth feature" in captured.out
        assert "NOT NOW" in captured.out
        assert "dashboard redesign" in captured.out


class TestMain:
    """Tests for main(): full session_start run with all dependencies mocked."""

    def test_main_no_project_memory(self, capsys: pytest.CaptureFixture) -> None:
        """find_project_claude_dir returns None → prints fallback message.

        WHY: if the project has no .claude/memory/ — Claude must not crash,
        but inform that memory is not found and continue.
        """
        import session_start

        with (
            patch("session_start.auto_update_config_repo"),
            patch("session_start.find_project_claude_dir", return_value=None),
            patch("session_start.print_scope_fence"),
        ):
            session_start.main()

        captured = capsys.readouterr()
        # WHY: the line in session_start.py: "No project .claude/memory/ found in path hierarchy."
        assert "No project" in captured.out
        assert ".claude/memory/" in captured.out

    def test_main_with_project_memory(
        self, tmp_path: "pytest.TempdirFactory", capsys: pytest.CaptureFixture
    ) -> None:
        """If activeContext.md exists — its content is printed to stdout."""
        import session_start

        mem_dir = tmp_path / ".claude" / "memory"
        mem_dir.mkdir(parents=True)
        active = mem_dir / "activeContext.md"
        active.write_text("# Active Context\nWorking on feature X\n", encoding="utf-8")

        with (
            patch("session_start.auto_update_config_repo"),
            patch("session_start.find_project_claude_dir", return_value=mem_dir),
            patch("session_start.print_scope_fence"),
        ):
            session_start.main()

        captured = capsys.readouterr()
        # WHY: function reads and prints the content of activeContext.md
        assert "Working on feature X" in captured.out
        assert "PROJECT ACTIVE CONTEXT" in captured.out
