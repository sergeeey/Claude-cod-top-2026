"""Tests for checkpoint_guard.py.

# WHY: checkpoint_guard warns before risky operations (rebase, rm -rf,
# DROP TABLE, etc.). Tests mock stdin and the filesystem — no real git calls.
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch  # noqa: E402

import pytest  # noqa: E402


def make_stdin(data: dict) -> io.StringIO:
    """Helper function for mocking stdin with JSON data."""
    return io.StringIO(json.dumps(data))


def make_bash_input(command: str) -> dict:
    """Build typical PostToolUse hook data for a Bash command."""
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"stdout": ""},
    }


class TestCheckpointGuardMain:
    """Tests for main() via mocking stdin and the filesystem."""

    def test_skips_non_risky_command(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """The 'ls' command is not risky — hook stays silent."""
        data = make_bash_input("ls -la")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import checkpoint_guard

        checkpoint_guard.main()

        captured = capsys.readouterr()
        # WHY: early return when is_risky=False — no output at all
        assert captured.out == ""
        assert captured.err == ""

    def test_warns_on_git_rebase(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """git rebase is a risky command — with no checkpoints a warning is emitted."""
        data = make_bash_input("git rebase main")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        # WHY: mock find_checkpoints_dir to return a path,
        # and latest_checkpoint_age to return None (no checkpoint files).
        mock_dir = MagicMock()
        mock_dir.__str__ = lambda self: "/fake/.claude/checkpoints"

        with (
            patch("checkpoint_guard.find_checkpoints_dir", return_value=mock_dir),
            patch("checkpoint_guard.latest_checkpoint_age", return_value=None),
        ):
            import checkpoint_guard

            checkpoint_guard.main()

        captured = capsys.readouterr()
        assert "checkpoint" in captured.out.lower()
        assert "git rebase main" in captured.out

    def test_warns_on_rm_rf(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """rm -rf is a risky command — warning emitted when no fresh checkpoints exist."""
        data = make_bash_input("rm -rf dir")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        mock_dir = MagicMock()

        with (
            patch("checkpoint_guard.find_checkpoints_dir", return_value=mock_dir),
            patch("checkpoint_guard.latest_checkpoint_age", return_value=None),
        ):
            import checkpoint_guard

            checkpoint_guard.main()

        captured = capsys.readouterr()
        assert "checkpoint" in captured.out.lower()

    def test_allows_with_recent_checkpoint(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """A fresh checkpoint (<10 min) — hook stays silent, operation is allowed."""
        data = make_bash_input("git rebase main")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        mock_dir = MagicMock()

        # WHY: age=5 minutes < threshold of 60 minutes → hook emits no warning
        with (
            patch("checkpoint_guard.find_checkpoints_dir", return_value=mock_dir),
            patch("checkpoint_guard.latest_checkpoint_age", return_value=5.0),
        ):
            import checkpoint_guard

            checkpoint_guard.main()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_warns_when_no_checkpoints_dir(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Regression (LOW, cross-model audit): find_checkpoints_dir
        returning None previously meant complete silence for a risky
        command -- exactly the case where a checkpoint suggestion is most
        useful (no established save-point mechanism exists yet). Must now
        emit a fallback warning instead of silently returning."""
        data = make_bash_input("git rebase main")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        with patch("checkpoint_guard.find_checkpoints_dir", return_value=None):
            import checkpoint_guard

            checkpoint_guard.main()

        captured = capsys.readouterr()
        assert "checkpoint" in captured.out.lower()
        assert "git rebase main" in captured.out


class TestPreToolUseTiming:
    """Regression (HIGH, cross-model audit): this hook previously fired on
    PostToolUse, so a risky command like `rm -rf` had ALREADY RUN by the
    time the checkpoint suggestion appeared. Moved to PreToolUse."""

    def test_emits_pretooluse_event_name(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        data = make_bash_input("git rebase main")
        monkeypatch.setattr("sys.stdin", make_stdin(data))
        mock_dir = MagicMock()

        with (
            patch("checkpoint_guard.find_checkpoints_dir", return_value=mock_dir),
            patch("checkpoint_guard.latest_checkpoint_age", return_value=None),
        ):
            import checkpoint_guard

            checkpoint_guard.main()

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["hookSpecificOutput"]["hookEventName"] == "PreToolUse"


class TestPowerShellDeleteDetection:
    """Regression (MEDIUM, cross-model audit): `Remove-Item -Recurse -Force`
    (PowerShell's `rm -rf` equivalent, relevant since this repo runs on
    Windows) was completely unmatched by the old literal pattern list."""

    def _warns(self, monkeypatch, capsys, command: str) -> bool:
        data = make_bash_input(command)
        monkeypatch.setattr("sys.stdin", make_stdin(data))
        mock_dir = MagicMock()

        with (
            patch("checkpoint_guard.find_checkpoints_dir", return_value=mock_dir),
            patch("checkpoint_guard.latest_checkpoint_age", return_value=None),
        ):
            import checkpoint_guard

            checkpoint_guard.main()

        return capsys.readouterr().out != ""

    def test_remove_item_recurse_force(self, monkeypatch, capsys):
        assert self._warns(monkeypatch, capsys, "Remove-Item -Recurse -Force build/")

    def test_remove_item_flags_reversed_order(self, monkeypatch, capsys):
        assert self._warns(monkeypatch, capsys, "Remove-Item -Force -Recurse build/")

    def test_remove_item_abbreviated_flags(self, monkeypatch, capsys):
        assert self._warns(monkeypatch, capsys, "Remove-Item -r -f build/")

    def test_ri_alias(self, monkeypatch, capsys):
        assert self._warns(monkeypatch, capsys, "ri -Recurse -Force build/")

    def test_remove_item_without_force_not_flagged(self, monkeypatch, capsys):
        """Sanity check: a non-destructive Remove-Item (no -Force, would
        prompt for confirmation) shouldn't need a checkpoint suggestion."""
        assert not self._warns(monkeypatch, capsys, "Remove-Item -Recurse build/")

    def test_git_switch_main(self, monkeypatch, capsys):
        assert self._warns(monkeypatch, capsys, "git switch main")

    def test_git_switch_master(self, monkeypatch, capsys):
        assert self._warns(monkeypatch, capsys, "git switch master")

    def test_git_push_force(self, monkeypatch, capsys):
        assert self._warns(monkeypatch, capsys, "git push --force origin main")

    def test_git_branch_delete_force(self, monkeypatch, capsys):
        assert self._warns(monkeypatch, capsys, "git branch -D feature/old")
