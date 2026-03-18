"""Unit tests for hooks/pattern_extractor.py."""

from __future__ import annotations

import io
import json
import sys

import pattern_extractor


def _run_main_with_stdin(payload: dict) -> None:
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        pattern_extractor.main()
    finally:
        sys.stdin = old_stdin


class TestExtractFixSubject:
    def test_extracts_subject_from_fix_commit(self):
        assert pattern_extractor.extract_fix_subject("fix: null check") == "null check"
        assert pattern_extractor.extract_fix_subject("Fix(scope): something") == "something"

    def test_ignores_non_fix_commit(self):
        assert pattern_extractor.extract_fix_subject("feat: new feature") is None
        assert pattern_extractor.extract_fix_subject("chore: bump") is None


class TestSanitizeCommitMsg:
    def test_handles_empty_commit_message(self):
        assert pattern_extractor.sanitize_commit_msg("") == ""

    def test_strips_newlines_and_limits_length(self):
        msg = "line1\nline2\rline3"
        out = pattern_extractor.sanitize_commit_msg(msg)
        assert "\n" not in out
        assert "\r" not in out


class TestMainFlow:
    def test_non_commit_is_skipped(self, capsys):
        _run_main_with_stdin({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        assert capsys.readouterr().out == ""

    def test_ignores_failed_commit(self, capsys):
        _run_main_with_stdin(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m x"},
                "tool_response": {"stdout": "error: something"},
            }
        )
        assert capsys.readouterr().out == ""

    def test_emits_reminder_for_fix_commit(self, tmp_path, monkeypatch, capsys):
        # Redirect global patterns file into tmp.
        patterns = tmp_path / "patterns.md"
        patterns.write_text("## Отладка и фиксы\n", encoding="utf-8")
        monkeypatch.setattr(pattern_extractor, "GLOBAL_PATTERNS_PATH", patterns)

        def fake_run_git(args: list[str], timeout: int = 10) -> str:
            if args[:3] == ["log", "-1", "--format=%h"]:
                return "abc123"
            if args[:3] == ["log", "-1", "--format=%s"]:
                return "fix: null check"
            return ""

        monkeypatch.setattr(pattern_extractor, "run_git", fake_run_git)

        _run_main_with_stdin(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m \"x\""},
                "tool_response": {"stdout": "[ok]"},
            }
        )

        out = capsys.readouterr().out
        parsed = json.loads(out)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "fix:-коммит обнаружен" in ctx
        assert "patterns.md" in ctx
        assert "[AVOID]" in ctx

    def test_matching_pattern_includes_counter_hint(self, tmp_path, monkeypatch, capsys):
        patterns = tmp_path / "patterns.md"
        patterns.write_text(
            "## Отладка и фиксы\n\n### [2026-01-01] [AVOID] null check [×3]\n- x\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(pattern_extractor, "GLOBAL_PATTERNS_PATH", patterns)

        def fake_run_git(args: list[str], timeout: int = 10) -> str:
            if args[:3] == ["log", "-1", "--format=%h"]:
                return "abc123"
            if args[:3] == ["log", "-1", "--format=%s"]:
                return "fix: null check"
            return ""

        monkeypatch.setattr(pattern_extractor, "run_git", fake_run_git)

        _run_main_with_stdin(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m \"x\""},
                "tool_result": {"stdout": "[ok]"},
            }
        )

        ctx = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
        assert "похожие существующие паттерны" in ctx
        assert "[×3]" in ctx
        assert "[×4]" in ctx

