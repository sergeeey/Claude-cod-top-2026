"""Tests for pre_commit_guard.py.

WHY: pre_commit_guard is a security-critical hook. It blocks commits to main/master
and pushes to public repos. Tests guarantee that critical checks work
via mocking stdin and run_git, without real git operations.
"""

import io
import json
import os
import sys

# WHY: hooks live one level above tests/. insert(0) ensures priority
# over site-packages during import.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402


def make_stdin(data: dict) -> io.StringIO:
    """Helper function to mock stdin with JSON data."""
    return io.StringIO(json.dumps(data))


def make_bash_input(command: str) -> dict:
    """Create typical hook data for a Bash command."""
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


class TestPreCommitGuardMain:
    """Tests for main() via mocking stdin and run_git."""

    def test_skips_non_git_commit(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Command 'ls' — not git commit, hook should exit without output."""
        data = make_bash_input("ls -la")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import pre_commit_guard

        pre_commit_guard.main()

        captured = capsys.readouterr()
        # WHY: hook does early return — no output to stdout/stderr
        assert captured.out == ""
        assert captured.err == ""

    def test_blocks_commit_to_main(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Commit to main should block execution with exit(2)."""
        data = make_bash_input('git commit -m "feat: some change"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        # WHY: mock run_git returns "main" for rev-parse --abbrev-ref HEAD
        with patch("pre_commit_guard.run_git", return_value="main"):
            import pre_commit_guard

            with pytest.raises(SystemExit) as exc_info:
                pre_commit_guard.main()

        assert exc_info.value.code == 2

    def test_blocks_commit_to_master(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Commit to master should block execution with exit(2)."""
        data = make_bash_input('git commit -m "fix: hotfix"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        with patch("pre_commit_guard.run_git", return_value="master"):
            import pre_commit_guard

            with pytest.raises(SystemExit) as exc_info:
                pre_commit_guard.main()

        assert exc_info.value.code == 2

    def test_allows_commit_to_feature(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Commit to feature branch is allowed — hook does not call sys.exit(2)."""
        data = make_bash_input('git commit -m "feat: voice input"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        # WHY: run_git is called 3 times: rev-parse, diff --cached --name-only, diff --cached
        # Return feature branch and empty diffs — no branch warnings
        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/voice-input"
            return ""

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            # Should not raise SystemExit(2)
            pre_commit_guard.main()

        # Verify there was no blocking (no exit with code 2)
        # Test passes if main() completes without an exception

    def test_detects_sensitive_files(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Staged .env and credentials.json should generate a warning."""
        data = make_bash_input('git commit -m "feat: add config"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/test"
            if "--name-only" in args:
                return ".env\ncredentials.json"
            return ""  # diff --cached is empty

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            pre_commit_guard.main()

        captured = capsys.readouterr()
        # emit_hook_result writes JSON to stdout with additionalContext
        assert "sensitive" in captured.out.lower() or "WARNING" in captured.out

    def test_detects_debug_statements(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """An added line with print() in diff should generate a warning."""
        data = make_bash_input('git commit -m "feat: logging"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/test"
            if "--name-only" in args:
                return "app.py"
            # diff --cached contains the added print()
            return "+    print(foo)\n+    result = compute()"

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            pre_commit_guard.main()

        captured = capsys.readouterr()
        assert "print(" in captured.out or "Debug" in captured.out or "debug" in captured.out

    def test_ignores_removed_debug(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Removed lines with print() (starting with '-') should not trigger a warning."""
        data = make_bash_input('git commit -m "refactor: clean up"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/clean"
            if "--name-only" in args:
                return "app.py"
            # WHY: line starts with '-' — it is a removed line, hook ignores it
            return "-    print(foo)\n+    logger.debug('foo')"

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            pre_commit_guard.main()

        captured = capsys.readouterr()
        # The debug-statements warning should NOT contain "print("
        # (logger.debug is not in debug_patterns)
        output_data = json.loads(captured.out) if captured.out.strip() else {}
        context = output_data.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "print(" not in context

    def test_blocks_push_to_public_main(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """git push public main should be blocked with exit(2)."""
        data = make_bash_input("git push public main")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import pre_commit_guard

        with pytest.raises(SystemExit) as exc_info:
            pre_commit_guard.main()

        assert exc_info.value.code == 2

    def test_allows_push_feature_to_public(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """git push public feature/x is allowed — only main/master are blocked."""
        data = make_bash_input("git push public feature/voice-input")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import pre_commit_guard

        # Should not raise SystemExit(2)
        pre_commit_guard.main()

        captured = capsys.readouterr()
        assert captured.err == ""
