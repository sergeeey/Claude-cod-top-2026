"""Unit tests for hooks/pre_commit_guard.py."""

from __future__ import annotations

import io
import json
import sys

import pre_commit_guard
import pytest


def _run_main_with_stdin(payload: dict) -> None:
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        pre_commit_guard.main()
    finally:
        sys.stdin = old_stdin


class TestPreCommitGuard:
    def test_blocks_commit_to_main(self, monkeypatch):
        def fake_run_git(args: list[str], timeout: int = 10) -> str:
            if args[:3] == ["rev-parse", "--abbrev-ref", "HEAD"]:
                return "main"
            return ""

        monkeypatch.setattr(pre_commit_guard, "run_git", fake_run_git)

        payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m \"x\""}}
        with pytest.raises(SystemExit) as e:
            _run_main_with_stdin(payload)
        assert e.value.code == 2

    def test_allows_commit_to_feature_branch_emits_context(self, monkeypatch, capsys):
        def fake_run_git(args: list[str], timeout: int = 10) -> str:
            if args[:3] == ["rev-parse", "--abbrev-ref", "HEAD"]:
                return "feature/x"
            if args[:3] == ["diff", "--cached", "--name-only"]:
                return ""
            if args[:2] == ["diff", "--cached"]:
                return ""
            return ""

        monkeypatch.setattr(pre_commit_guard, "run_git", fake_run_git)

        payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m \"x\""}}
        _run_main_with_stdin(payload)

        out = capsys.readouterr().out.strip()
        assert out
        parsed = json.loads(out)
        assert parsed["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert "REMINDER" in parsed["hookSpecificOutput"]["additionalContext"]

    def test_blocks_push_to_public_main(self, capsys):
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "git push public main"},
        }
        with pytest.raises(SystemExit) as e:
            _run_main_with_stdin(payload)
        assert e.value.code == 2
        err = capsys.readouterr().err
        assert "Direct push to 'public' remote is not allowed" in err

    def test_non_commit_bash_is_fast_exit(self, monkeypatch, capsys):
        # If command isn't git commit, it should exit without git calls or output.
        monkeypatch.setattr(pre_commit_guard, "run_git", lambda *_a, **_k: "SHOULD_NOT_BE_USED")
        payload = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        _run_main_with_stdin(payload)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_skips_invalid_json(self, capsys):
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO("")  # empty stdin
            pre_commit_guard.main()
        finally:
            sys.stdin = old_stdin

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_warns_on_sensitive_staged_files(self, monkeypatch, capsys):
        def fake_run_git(args: list[str], timeout: int = 10) -> str:
            if args[:3] == ["rev-parse", "--abbrev-ref", "HEAD"]:
                return "feature/x"
            if args[:3] == ["diff", "--cached", "--name-only"]:
                return ".env\nsrc/ok.py\ncredentials.json"
            if args[:2] == ["diff", "--cached"]:
                return ""
            return ""

        monkeypatch.setattr(pre_commit_guard, "run_git", fake_run_git)

        payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m \"x\""}}
        _run_main_with_stdin(payload)

        parsed = json.loads(capsys.readouterr().out)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "Potentially sensitive files staged" in ctx
        assert ".env" in ctx
        assert "credentials.json" in ctx

    def test_warns_on_debug_statements_in_diff(self, monkeypatch, capsys):
        def fake_run_git(args: list[str], timeout: int = 10) -> str:
            if args[:3] == ["rev-parse", "--abbrev-ref", "HEAD"]:
                return "feature/x"
            if args[:3] == ["diff", "--cached", "--name-only"]:
                return ""
            if args[:2] == ["diff", "--cached"]:
                return "+++ b/app.py\n+print('debug')\n+console.log('x')\n"
            return ""

        monkeypatch.setattr(pre_commit_guard, "run_git", fake_run_git)

        payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m \"x\""}}
        _run_main_with_stdin(payload)

        parsed = json.loads(capsys.readouterr().out)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "Debug statements found" in ctx
        assert "print(" in ctx or "console.log(" in ctx

