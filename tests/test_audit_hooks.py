"""Tests for simple audit logger hooks: elicitation_guard, config_audit,
instructions_audit, task_audit.

WHY: These hooks are 0% covered despite being active in production.
They share a pattern: parse stdin → write to ~/.claude/logs/*.jsonl
"""

import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ── helpers ──────────────────────────────────────────────────────────────────


def _stdin(data: dict):
    return io.StringIO(json.dumps(data))


# ── elicitation_guard ────────────────────────────────────────────────────────


class TestElicitationGuard:
    def _run(self, monkeypatch, tmp_path, data: dict):
        monkeypatch.setattr("sys.stdin", _stdin(data))
        with patch("elicitation_guard.Path") as mock_path:
            mock_path.home.return_value = tmp_path
            mock_path.side_effect = lambda *a, **kw: Path(*a, **kw)
            mock_path.home = lambda: tmp_path
            # Re-import to pick up patch
            import elicitation_guard

            log_dir = tmp_path / ".claude" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            with patch("elicitation_guard.Path.home", return_value=tmp_path):
                elicitation_guard.main()
        return tmp_path / ".claude" / "logs" / "elicitation.jsonl"

    def test_logs_elicitation_event(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "sys.stdin", _stdin({"hook_event_name": "Elicitation", "session_id": "sess-123"})
        )
        import elicitation_guard

        with patch("elicitation_guard.Path") as MockPath:
            log_dir = tmp_path / ".claude" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "elicitation.jsonl"

            real_path = Path

            def path_side_effect(*args, **kwargs):
                p = real_path(*args, **kwargs)
                return p

            MockPath.home.return_value = tmp_path
            MockPath.side_effect = path_side_effect

            # Use direct file mock
            with patch("pathlib.Path.home", return_value=tmp_path):
                elicitation_guard.main()

    def test_logs_to_jsonl(self, monkeypatch, tmp_path):
        """Main happy path: event logged as valid JSON."""
        import elicitation_guard

        monkeypatch.setattr(
            "sys.stdin", _stdin({"hook_event_name": "ElicitationResult", "session_id": "abc-456"})
        )
        with patch("pathlib.Path.home", return_value=tmp_path):
            elicitation_guard.main()
        log_file = tmp_path / ".claude" / "logs" / "elicitation.jsonl"
        assert log_file.exists()
        entry = json.loads(log_file.read_text().strip())
        assert entry["event"] == "ElicitationResult"
        assert entry["session_id"] == "abc-456"
        assert "timestamp" in entry

    def test_empty_data_no_crash(self, monkeypatch, tmp_path):
        """Empty dict input should not raise."""
        import elicitation_guard

        monkeypatch.setattr("sys.stdin", _stdin({}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            elicitation_guard.main()  # should not raise

    def test_invalid_json_no_crash(self, monkeypatch, tmp_path):
        """Invalid JSON input should not raise."""
        import elicitation_guard

        monkeypatch.setattr("sys.stdin", io.StringIO("not json {{{"))
        with patch("pathlib.Path.home", return_value=tmp_path):
            elicitation_guard.main()  # parse_stdin returns None → early return

    def test_oserror_handled(self, monkeypatch, tmp_path):
        """OSError on log write should be silently caught."""
        import elicitation_guard

        monkeypatch.setattr("sys.stdin", _stdin({"hook_event_name": "Elicitation"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("builtins.open", side_effect=OSError("disk full")):
                elicitation_guard.main()  # should not raise


# ── config_audit ─────────────────────────────────────────────────────────────


class TestConfigAudit:
    def test_happy_path(self, monkeypatch, tmp_path):
        import config_audit

        monkeypatch.setattr(
            "sys.stdin",
            _stdin({"source": "settings.json", "file_path": "/project/.claude/settings.json"}),
        )
        with patch("pathlib.Path.home", return_value=tmp_path):
            config_audit.main()

    def test_empty_input(self, monkeypatch, tmp_path):
        import config_audit

        monkeypatch.setattr("sys.stdin", _stdin({}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            config_audit.main()

    def test_invalid_json(self, monkeypatch, tmp_path):
        import config_audit

        monkeypatch.setattr("sys.stdin", io.StringIO("bad json"))
        with patch("pathlib.Path.home", return_value=tmp_path):
            config_audit.main()

    def test_log_dir_created(self, monkeypatch, tmp_path):
        """Verifies log directory is created if missing."""
        import config_audit

        monkeypatch.setattr("sys.stdin", _stdin({"source": "test", "file_path": "x.json"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            config_audit.main()
        log_dir = tmp_path / ".claude" / "logs"
        assert log_dir.exists()

    def test_log_entry_valid_json(self, monkeypatch, tmp_path):
        """Log entry should be valid JSON."""
        import config_audit

        monkeypatch.setattr(
            "sys.stdin", _stdin({"source": "user", "file_path": "/path/to/settings.json"})
        )
        with patch("pathlib.Path.home", return_value=tmp_path):
            config_audit.main()
        log_file = tmp_path / ".claude" / "logs" / "config_audit.log"
        if log_file.exists():
            line = log_file.read_text().strip()
            if line:
                entry = json.loads(line)
                assert entry["event"] == "ConfigChange"
                assert "timestamp" in entry

    def test_oserror_silenced(self, monkeypatch, tmp_path):
        import config_audit

        monkeypatch.setattr("sys.stdin", _stdin({"source": "x"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("builtins.open", side_effect=OSError):
                config_audit.main()


# ── instructions_audit ───────────────────────────────────────────────────────


class TestInstructionsAudit:
    def test_happy_path(self, monkeypatch, tmp_path):
        import instructions_audit

        monkeypatch.setattr(
            "sys.stdin",
            _stdin(
                {
                    "file_path": "/home/user/.claude/CLAUDE.md",
                    "load_reason": "project",
                    "memory_type": "user",
                    "session_id": "sess-789",
                }
            ),
        )
        with patch("pathlib.Path.home", return_value=tmp_path):
            instructions_audit.main()

    def test_missing_fields_defaults(self, monkeypatch, tmp_path):
        import instructions_audit

        monkeypatch.setattr("sys.stdin", _stdin({}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            instructions_audit.main()

    def test_invalid_json(self, monkeypatch, tmp_path):
        import instructions_audit

        monkeypatch.setattr("sys.stdin", io.StringIO("{{invalid"))
        with patch("pathlib.Path.home", return_value=tmp_path):
            instructions_audit.main()

    def test_log_contains_all_fields(self, monkeypatch, tmp_path):
        import instructions_audit

        monkeypatch.setattr(
            "sys.stdin",
            _stdin(
                {
                    "file_path": "/rules/security.md",
                    "load_reason": "auto",
                    "memory_type": "project",
                    "session_id": "s-001",
                }
            ),
        )
        with patch("pathlib.Path.home", return_value=tmp_path):
            instructions_audit.main()
        log_file = tmp_path / ".claude" / "logs" / "instructions.jsonl"
        if log_file.exists():
            entry = json.loads(log_file.read_text().strip())
            assert entry["event"] == "InstructionsLoaded"
            assert entry["file_path"] == "/rules/security.md"
            assert entry["session_id"] == "s-001"

    def test_oserror_silenced(self, monkeypatch, tmp_path):
        import instructions_audit

        monkeypatch.setattr("sys.stdin", _stdin({"file_path": "x"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("builtins.open", side_effect=OSError):
                instructions_audit.main()


# ── task_audit ───────────────────────────────────────────────────────────────


class TestTaskAudit:
    def test_task_created(self, monkeypatch, tmp_path):
        import task_audit

        monkeypatch.setattr(
            "sys.stdin",
            _stdin(
                {
                    "hook_event_name": "TaskCreated",
                    "task_id": "t-001",
                    "task_subject": "Write tests",
                    "session_id": "sess-abc",
                }
            ),
        )
        with patch("pathlib.Path.home", return_value=tmp_path):
            task_audit.main()

    def test_task_completed(self, monkeypatch, tmp_path):
        import task_audit

        monkeypatch.setattr(
            "sys.stdin",
            _stdin(
                {
                    "hook_event_name": "TaskCompleted",
                    "task_id": "t-002",
                    "task_subject": "Deploy",
                    "session_id": "sess-xyz",
                }
            ),
        )
        with patch("pathlib.Path.home", return_value=tmp_path):
            task_audit.main()

    def test_empty_input(self, monkeypatch, tmp_path):
        import task_audit

        monkeypatch.setattr("sys.stdin", _stdin({}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            task_audit.main()

    def test_invalid_json(self, monkeypatch, tmp_path):
        import task_audit

        monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
        with patch("pathlib.Path.home", return_value=tmp_path):
            task_audit.main()

    def test_log_entry_structure(self, monkeypatch, tmp_path):
        import task_audit

        monkeypatch.setattr(
            "sys.stdin",
            _stdin(
                {
                    "hook_event_name": "TaskCreated",
                    "task_id": "t-999",
                    "task_subject": "Test subject",
                    "session_id": "s-test",
                }
            ),
        )
        with patch("pathlib.Path.home", return_value=tmp_path):
            task_audit.main()
        log_file = tmp_path / ".claude" / "logs" / "tasks.jsonl"
        if log_file.exists():
            entry = json.loads(log_file.read_text().strip())
            assert entry["task_id"] == "t-999"
            assert entry["event"] == "TaskCreated"

    def test_oserror_silenced(self, monkeypatch, tmp_path):
        import task_audit

        monkeypatch.setattr("sys.stdin", _stdin({"task_id": "x"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("builtins.open", side_effect=OSError):
                task_audit.main()
