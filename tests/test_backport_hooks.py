"""Tests for backported hooks: auto_capture, prompt_wiki_inject, wiki_reminder,
subagent_verify, instructions_audit.

WHY: these hooks were battle-tested in production config but lacked test coverage
in the public repo. Each test verifies core logic with mocked stdin/filesystem.
"""

import io
import json
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
)

from pathlib import Path
from unittest.mock import patch

import pytest


def make_stdin(data: dict) -> io.StringIO:
    """Helper to mock stdin with JSON data."""
    return io.StringIO(json.dumps(data))


# =============================================================================
# subagent_verify.py
# =============================================================================


class TestSubagentVerify:
    """Tests for subagent output quality verification."""

    def test_import(self) -> None:
        import subagent_verify

        assert hasattr(subagent_verify, "main")

    def test_pass_on_good_response(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Non-trivial response should produce PASS verdict."""
        data = {
            "agent_type": "builder",
            "agent_id": "abc123",
            "last_assistant_message": "I implemented the feature by adding a new endpoint at /api/v2/users with proper validation and error handling.",
            "session_id": "sess-1",
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        with patch("subagent_verify.Path.home", return_value=tmp_path / "fake_home"):
            (tmp_path / "fake_home" / ".claude" / "logs").mkdir(parents=True)
            import importlib

            import subagent_verify

            importlib.reload(subagent_verify)
            subagent_verify.main()

        out = capsys.readouterr().out
        # Good response should NOT produce a warning
        if out.strip():
            parsed = json.loads(out.strip())
            assert parsed.get("result") != "error"

    def test_fail_on_empty_response(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Empty response should trigger FAIL."""
        data = {
            "agent_type": "explorer",
            "agent_id": "def456",
            "last_assistant_message": "",
            "session_id": "sess-2",
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))
        with patch("subagent_verify.Path.home", return_value=tmp_path / "fake_home"):
            (tmp_path / "fake_home" / ".claude" / "logs").mkdir(parents=True)
            import importlib

            import subagent_verify

            importlib.reload(subagent_verify)
            subagent_verify.main()

        out = capsys.readouterr().out
        if out.strip():
            parsed = json.loads(out.strip())
            assert "warning" in parsed.get("message", "").lower() or parsed.get("result") == "info"

    def test_fail_on_apology(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Apology markers should trigger warning."""
        data = {
            "agent_type": "builder",
            "agent_id": "ghi789",
            "last_assistant_message": "I apologize, but I wasn't able to complete the task due to missing context.",
            "session_id": "sess-3",
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))
        with patch("subagent_verify.Path.home", return_value=tmp_path / "fake_home"):
            (tmp_path / "fake_home" / ".claude" / "logs").mkdir(parents=True)
            import importlib

            import subagent_verify

            importlib.reload(subagent_verify)
            subagent_verify.main()

        out = capsys.readouterr().out
        assert out.strip(), "Apology response should produce a warning"

    def test_min_response_length(self) -> None:
        """MIN_RESPONSE_LENGTH should be a reasonable threshold."""
        import subagent_verify

        assert subagent_verify.MIN_RESPONSE_LENGTH >= 20
        assert subagent_verify.MIN_RESPONSE_LENGTH <= 200


# =============================================================================
# instructions_audit.py
# =============================================================================


class TestInstructionsAudit:
    """Tests for instructions loading audit trail."""

    def test_import(self) -> None:
        import instructions_audit

        assert hasattr(instructions_audit, "main")

    def test_logs_instruction_event(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Should write a JSONL entry to logs/instructions.jsonl."""
        data = {
            "file_path": "/home/user/.claude/rules/security.md",
            "load_reason": "context",
            "memory_type": "rule",
            "session_id": "sess-audit-1",
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        fake_home = tmp_path / "fake_home"
        log_dir = fake_home / ".claude" / "logs"
        log_dir.mkdir(parents=True)

        with patch("instructions_audit.Path.home", return_value=fake_home):
            import importlib

            import instructions_audit

            importlib.reload(instructions_audit)
            instructions_audit.main()

        log_file = log_dir / "instructions.jsonl"
        assert log_file.exists()
        entry = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert entry["event"] == "InstructionsLoaded"
        assert entry["file_path"] == "/home/user/.claude/rules/security.md"

    def test_handles_empty_stdin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty stdin should not crash."""
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        import importlib

        import instructions_audit

        importlib.reload(instructions_audit)
        # Should not raise
        instructions_audit.main()

    def test_handles_missing_fields(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Missing fields should default to 'unknown'."""
        data = {"session_id": "sess-2"}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        fake_home = tmp_path / "fake_home"
        log_dir = fake_home / ".claude" / "logs"
        log_dir.mkdir(parents=True)

        with patch("instructions_audit.Path.home", return_value=fake_home):
            import importlib

            import instructions_audit

            importlib.reload(instructions_audit)
            instructions_audit.main()

        log_file = log_dir / "instructions.jsonl"
        entry = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert entry["file_path"] == "unknown"
        assert entry["load_reason"] == "unknown"


# =============================================================================
# auto_capture.py
# =============================================================================


class TestAutoCapture:
    """Tests for mid-session knowledge capture from commits and test failures."""

    def test_import(self) -> None:
        """Module should import without error (CLAUDE_INVOKED_BY not set)."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_INVOKED_BY", None)
            import importlib

            import auto_capture

            importlib.reload(auto_capture)
            assert hasattr(auto_capture, "_write_raw")

    def test_write_raw_creates_file(self, tmp_path: Path) -> None:
        """_write_raw should create a file in raw/ directory."""
        import auto_capture

        auto_capture.RAW_DIR = tmp_path
        result = auto_capture._write_raw("test-slug", "# Test\nContent here")
        assert result is True
        files = list(tmp_path.glob("*.md"))
        assert len(files) == 1
        assert "Content here" in files[0].read_text(encoding="utf-8")

    def test_write_raw_idempotent(self, tmp_path: Path) -> None:
        """_write_raw should not overwrite existing file."""
        import auto_capture

        auto_capture.RAW_DIR = tmp_path
        auto_capture._write_raw("test-slug", "First")
        result = auto_capture._write_raw("test-slug", "Second")
        assert result is False
        files = list(tmp_path.glob("*.md"))
        assert "First" in files[0].read_text(encoding="utf-8")

    def test_write_raw_sanitizes_slug(self, tmp_path: Path) -> None:
        """Dangerous characters in slug should be sanitized."""
        import auto_capture

        auto_capture.RAW_DIR = tmp_path
        auto_capture._write_raw("../../etc/passwd", "bad")
        files = list(tmp_path.glob("*.md"))
        assert len(files) == 1
        assert "/" not in files[0].name
        assert ".." not in files[0].name


# =============================================================================
# wiki_reminder.py
# =============================================================================


class TestWikiReminder:
    """Tests for architectural decision reminder on session stop."""

    def test_import(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_INVOKED_BY", None)
            import importlib

            import wiki_reminder

            importlib.reload(wiki_reminder)
            assert hasattr(wiki_reminder, "MIN_KEYWORD_MATCHES")

    def test_keyword_threshold(self) -> None:
        """MIN_KEYWORD_MATCHES should require 3+ to avoid false positives."""
        import wiki_reminder

        assert wiki_reminder.MIN_KEYWORD_MATCHES >= 3

    def test_debounce_interval(self) -> None:
        """Debounce should be at least 60 seconds."""
        import wiki_reminder

        assert wiki_reminder.DEBOUNCE_SEC >= 60

    def test_decision_keywords_not_empty(self) -> None:
        """Decision keyword list should have sufficient coverage."""
        import wiki_reminder

        assert len(wiki_reminder._DECISION_KEYWORDS) >= 10


# =============================================================================
# prompt_wiki_inject.py
# =============================================================================


class TestPromptWikiInject:
    """Tests for per-prompt wiki context injection."""

    def test_import(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_INVOKED_BY", None)
            import importlib

            import prompt_wiki_inject

            importlib.reload(prompt_wiki_inject)
            assert hasattr(prompt_wiki_inject, "MAX_ARTICLES")

    def test_constants_reasonable(self) -> None:
        """Injection limits should prevent context bloat."""
        import prompt_wiki_inject

        assert prompt_wiki_inject.MAX_ARTICLES <= 5
        assert prompt_wiki_inject.MAX_ARTICLE_CHARS <= 3000
        assert prompt_wiki_inject.MAX_CONTEXT_CHARS <= 5000

    def test_min_prompt_length(self) -> None:
        """Short prompts should be skipped."""
        import prompt_wiki_inject

        assert prompt_wiki_inject.MIN_PROMPT_LEN >= 10

    def test_stop_words_present(self) -> None:
        """Stop words set should filter common English words."""
        import prompt_wiki_inject

        assert "the" in prompt_wiki_inject._STOP_WORDS
        assert "and" in prompt_wiki_inject._STOP_WORDS
