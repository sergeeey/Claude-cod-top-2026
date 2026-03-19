"""Tests for hooks/post_commit_memory.py — auto-logging commits to activeContext.md."""

import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))

import pytest
from pathlib import Path
from unittest.mock import patch

from post_commit_memory import extract_decision, find_decisions_file, log_decision, main


def make_stdin(data: dict):
    return io.StringIO(json.dumps(data))


# === extract_decision (already partially tested in test_hooks.py, add edge cases) ===


class TestExtractDecision:
    def test_arch_prefix(self):
        assert extract_decision("arch: use PostgreSQL") == ("arch", "use PostgreSQL")

    def test_conventional_plus_arch(self):
        assert extract_decision("feat: arch: new DB schema") == ("arch", "new DB schema")

    def test_security_prefix(self):
        assert extract_decision("security: enable MFA") == ("security", "enable MFA")

    def test_no_decision_prefix(self):
        assert extract_decision("feat: add button") is None

    def test_pattern_prefix(self):
        assert extract_decision("pattern: retry with backoff") == ("pattern", "retry with backoff")


# === log_decision ===


class TestLogDecision:
    def test_no_decision_returns_none(self):
        assert log_decision("abc1234", "feat: add button") is None

    def test_decision_no_file_returns_message(self):
        with patch("post_commit_memory.find_decisions_file", return_value=None):
            result = log_decision("abc1234", "arch: use Redis")
        assert "no decisions.md found" in result
        assert "arch" in result

    def test_decision_writes_to_file(self, tmp_path):
        decisions_file = tmp_path / "decisions.md"
        decisions_file.write_text("# Decisions\n", encoding="utf-8")

        with patch("post_commit_memory.find_decisions_file", return_value=decisions_file):
            result = log_decision("abc1234", "arch: use Redis for caching")

        assert "Auto-recorded" in result
        content = decisions_file.read_text(encoding="utf-8")
        assert "use Redis for caching" in content
        assert "`abc1234`" in content


# === main() ===


class TestMain:
    def test_skips_non_commit(self, monkeypatch):
        data = {"tool_input": {"command": "ls -la"}}
        monkeypatch.setattr("sys.stdin", make_stdin(data))
        # Should return without output
        main()

    def test_skips_failed_commit(self, monkeypatch):
        data = {
            "tool_input": {"command": "git commit -m 'test'"},
            "tool_response": {"stdout": "nothing to commit"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))
        main()

    def test_skips_empty_commit_hash(self, monkeypatch):
        data = {
            "tool_input": {"command": "git commit -m 'test'"},
            "tool_response": {"stdout": "1 file changed"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))
        with patch("post_commit_memory.run_git", return_value=""):
            main()

    def test_warns_when_no_active_context(self, monkeypatch, capsys):
        data = {
            "tool_input": {"command": "git commit -m 'test'"},
            "tool_response": {"stdout": "1 file changed"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_git(args, **kwargs):
            if "--format=%h" in args:
                return "abc1234"
            if "--format=%s" in args:
                return "feat: something"
            return ""

        with (
            patch("post_commit_memory.run_git", side_effect=mock_git),
            patch("post_commit_memory.find_project_memory", return_value=None),
        ):
            main()

        output = capsys.readouterr().out
        assert "no activeContext.md found" in output

    def test_creates_new_section_in_active_context(self, monkeypatch, capsys, tmp_path):
        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text("# Active Context\n\nSome content\n", encoding="utf-8")

        data = {
            "tool_input": {"command": "git commit -m 'feat: add feature'"},
            "tool_response": {"stdout": "1 file changed, 5 insertions"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_git(args, **kwargs):
            if "--format=%h" in args:
                return "def5678"
            if "--format=%s" in args:
                return "feat: add feature"
            return ""

        with (
            patch("post_commit_memory.run_git", side_effect=mock_git),
            patch("post_commit_memory.find_project_memory", return_value=ctx_file),
            patch("post_commit_memory.log_decision", return_value=None),
        ):
            main()

        content = ctx_file.read_text(encoding="utf-8")
        assert "## Auto-commit log" in content
        assert "`def5678`" in content
        assert "feat: add feature" in content

        output = capsys.readouterr().out
        assert "Auto-logged commit def5678" in output

    def test_appends_to_existing_section(self, monkeypatch, capsys, tmp_path):
        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text(
            "# Active Context\n\n## Auto-commit log\n- [2026-03-18] `old123`: old commit\n",
            encoding="utf-8",
        )

        data = {
            "tool_input": {"command": "git commit -m 'fix: bug'"},
            "tool_response": {"stdout": "2 files changed"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_git(args, **kwargs):
            if "--format=%h" in args:
                return "new456"
            if "--format=%s" in args:
                return "fix: bug"
            return ""

        with (
            patch("post_commit_memory.run_git", side_effect=mock_git),
            patch("post_commit_memory.find_project_memory", return_value=ctx_file),
            patch("post_commit_memory.log_decision", return_value=None),
        ):
            main()

        content = ctx_file.read_text(encoding="utf-8")
        assert "`new456`" in content
        assert "`old123`" in content
        # New entry should be inserted after header, before old
        lines = content.split("\n")
        new_idx = next(i for i, l in enumerate(lines) if "new456" in l)
        old_idx = next(i for i, l in enumerate(lines) if "old123" in l)
        assert new_idx < old_idx

    def test_decision_message_appended(self, monkeypatch, capsys, tmp_path):
        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text("# Context\n", encoding="utf-8")

        data = {
            "tool_input": {"command": "git commit -m 'arch: switch to Redis'"},
            "tool_response": {"stdout": "1 file changed"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_git(args, **kwargs):
            if "--format=%h" in args:
                return "arch789"
            if "--format=%s" in args:
                return "arch: switch to Redis"
            return ""

        with (
            patch("post_commit_memory.run_git", side_effect=mock_git),
            patch("post_commit_memory.find_project_memory", return_value=ctx_file),
            patch(
                "post_commit_memory.log_decision",
                return_value="Auto-recorded [arch] decision to decisions.md",
            ),
        ):
            main()

        output = capsys.readouterr().out
        assert "Auto-recorded [arch]" in output

    def test_empty_stdin_exits_gracefully(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        main()  # Should not raise
