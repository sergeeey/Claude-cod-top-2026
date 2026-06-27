"""Tests for observability hooks: model_usage_tracker, hook_observability, smart_model_router.

WHY: These three hooks were unregistered (hook_observability, smart_model_router) or
broken (model_usage_tracker read ghost fields not present in PostToolUse payload).
Fixed in session 2026-06-21. Tests added to prevent regression.
"""

import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── helpers ───────────────────────────────────────────────────────────────────

HOOKS_DIR = Path(__file__).parent.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

VALID_POST_TOOL = {
    "session_id": "abc123def456",
    "tool_name": "Read",
    "tool_input": {"file_path": "/some/file.py"},
    "tool_response": {"content": "x" * 200},
}


def _stdin(data: dict) -> io.StringIO:
    return io.StringIO(json.dumps(data))


# ── model_usage_tracker ───────────────────────────────────────────────────────


class TestModelUsageTracker:
    """model_usage_tracker: append tool-usage metrics to model_usage.jsonl."""

    def test_happy_path_writes_entry(self, monkeypatch, tmp_path):
        """Valid PostToolUse payload → entry written to log file."""
        import model_usage_tracker

        monkeypatch.setattr("sys.stdin", _stdin(VALID_POST_TOOL))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("model_usage_tracker.LOG_FILE", tmp_path / "model_usage.jsonl"):
                model_usage_tracker.main()

        log_file = tmp_path / "model_usage.jsonl"
        assert log_file.exists(), "log file not created"
        entry = json.loads(log_file.read_text().strip())
        assert entry["tool"] == "Read"
        assert entry["sid"] == "abc123de"  # truncated to 8 chars
        assert "ts" in entry
        assert "resp_bytes" in entry
        assert "inp_bytes" in entry
        assert "est_out_tok" in entry
        assert "est_in_tok" in entry

    def test_token_proxy_calculation(self, monkeypatch, tmp_path):
        """est_out_tok = resp_bytes // 4, est_in_tok = inp_bytes // 4."""
        import model_usage_tracker

        payload = {
            "session_id": "s1",
            "tool_name": "Write",
            "tool_input": {"content": "A" * 40},  # 40 bytes → est_in_tok = 10
            "tool_response": {"bytes_written": 100, "data": "X" * 96},  # ~100 bytes
        }
        monkeypatch.setattr("sys.stdin", _stdin(payload))
        with patch("model_usage_tracker.LOG_FILE", tmp_path / "model_usage.jsonl"):
            model_usage_tracker.main()

        entry = json.loads((tmp_path / "model_usage.jsonl").read_text().strip())
        assert entry["est_out_tok"] == entry["resp_bytes"] // 4
        assert entry["est_in_tok"] == entry["inp_bytes"] // 4

    def test_empty_stdin_no_crash(self, monkeypatch, tmp_path):
        """Empty stdin → exit 0, no file written."""
        import model_usage_tracker

        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        log = tmp_path / "model_usage.jsonl"
        with patch("model_usage_tracker.LOG_FILE", log):
            with pytest.raises(SystemExit) as exc_info:
                model_usage_tracker.main()
        assert exc_info.value.code == 0
        assert not log.exists()

    def test_malformed_json_no_crash(self, monkeypatch, tmp_path):
        """Malformed JSON → exit 0, no file written."""
        import model_usage_tracker

        monkeypatch.setattr("sys.stdin", io.StringIO("not { json }"))
        log = tmp_path / "model_usage.jsonl"
        with patch("model_usage_tracker.LOG_FILE", log):
            with pytest.raises(SystemExit) as exc_info:
                model_usage_tracker.main()
        assert exc_info.value.code == 0
        assert not log.exists()

    def test_recursion_guard_skips_write(self, monkeypatch, tmp_path):
        """CLAUDE_INVOKED_BY set → exit 0 immediately, no log written."""
        import model_usage_tracker

        monkeypatch.setenv("CLAUDE_INVOKED_BY", "subagent")
        monkeypatch.setattr("sys.stdin", _stdin(VALID_POST_TOOL))
        log = tmp_path / "model_usage.jsonl"
        with patch("model_usage_tracker.LOG_FILE", log):
            with pytest.raises(SystemExit) as exc_info:
                model_usage_tracker.main()
        assert exc_info.value.code == 0
        assert not log.exists(), "must not write when CLAUDE_INVOKED_BY is set"

    def test_oserror_on_write_no_crash(self, monkeypatch, tmp_path):
        """OSError during log write → silently ignored (fail-open)."""
        import model_usage_tracker

        monkeypatch.setattr("sys.stdin", _stdin(VALID_POST_TOOL))
        with patch("model_usage_tracker.LOG_FILE", tmp_path / "model_usage.jsonl"):
            with patch("builtins.open", side_effect=OSError("disk full")):
                model_usage_tracker.main()  # must not raise

    def test_missing_fields_use_defaults(self, monkeypatch, tmp_path):
        """Payload with missing optional fields → uses defaults, doesn't crash."""
        import model_usage_tracker

        monkeypatch.setattr("sys.stdin", _stdin({}))
        with patch("model_usage_tracker.LOG_FILE", tmp_path / "model_usage.jsonl"):
            model_usage_tracker.main()

        entry = json.loads((tmp_path / "model_usage.jsonl").read_text().strip())
        assert entry["tool"] == "unknown"
        assert entry["sid"] == ""

    def test_session_id_truncated_to_8_chars(self, monkeypatch, tmp_path):
        """session_id is stored as first 8 chars only."""
        import model_usage_tracker

        payload = {**VALID_POST_TOOL, "session_id": "1234567890abcdef"}
        monkeypatch.setattr("sys.stdin", _stdin(payload))
        with patch("model_usage_tracker.LOG_FILE", tmp_path / "model_usage.jsonl"):
            model_usage_tracker.main()

        entry = json.loads((tmp_path / "model_usage.jsonl").read_text().strip())
        assert entry["sid"] == "12345678"
        assert len(entry["sid"]) == 8

    def test_multiple_calls_append_not_overwrite(self, monkeypatch, tmp_path):
        """Each call appends a new line — does not truncate existing log."""
        import model_usage_tracker

        log = tmp_path / "model_usage.jsonl"
        for tool in ("Read", "Write", "Bash"):
            payload = {**VALID_POST_TOOL, "tool_name": tool}
            monkeypatch.setattr("sys.stdin", _stdin(payload))
            with patch("model_usage_tracker.LOG_FILE", log):
                model_usage_tracker.main()

        lines = log.read_text().strip().splitlines()
        assert len(lines) == 3
        tools = [json.loads(line)["tool"] for line in lines]
        assert tools == ["Read", "Write", "Bash"]


# ── hook_observability ────────────────────────────────────────────────────────


class TestHookObservability:
    """hook_observability: lightweight event-level telemetry logger."""

    def test_happy_path_writes_entry(self, monkeypatch, tmp_path):
        """Valid PostToolUse payload → entry written with ts/event/tool."""
        import hook_observability

        payload = {**VALID_POST_TOOL, "hook_event_name": "PostToolUse"}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        log = tmp_path / "hook_events.jsonl"
        with patch("hook_observability.LOG_FILE", log):
            with pytest.raises(SystemExit) as exc_info:
                hook_observability.main()
        assert exc_info.value.code == 0
        assert log.exists(), "log file not created"
        entry = json.loads(log.read_text().strip())
        assert entry["event"] == "PostToolUse"
        assert entry["tool"] == "Read"
        assert "ts" in entry

    def test_ts_is_iso_format(self, monkeypatch, tmp_path):
        """Timestamp is ISO 8601 string (not unix float)."""
        import hook_observability

        payload = {**VALID_POST_TOOL, "hook_event_name": "PostToolUse"}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        log = tmp_path / "hook_events.jsonl"
        with patch("hook_observability.LOG_FILE", log):
            with pytest.raises(SystemExit):
                hook_observability.main()

        entry = json.loads(log.read_text().strip())
        ts = entry["ts"]
        assert isinstance(ts, str), f"ts must be string, got {type(ts)}"
        assert "T" in ts, "ts must be ISO format"

    def test_empty_stdin_no_crash(self, monkeypatch, tmp_path):
        """Empty stdin → exit 0, no file written."""
        import hook_observability

        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        log = tmp_path / "hook_events.jsonl"
        with patch("hook_observability.LOG_FILE", log):
            with pytest.raises(SystemExit) as exc_info:
                hook_observability.main()
        assert exc_info.value.code == 0
        assert not log.exists()

    def test_malformed_json_no_crash(self, monkeypatch, tmp_path):
        """Malformed JSON → exit 0, no crash."""
        import hook_observability

        monkeypatch.setattr("sys.stdin", io.StringIO("{{not_json}}"))
        log = tmp_path / "hook_events.jsonl"
        with patch("hook_observability.LOG_FILE", log):
            with pytest.raises(SystemExit) as exc_info:
                hook_observability.main()
        assert exc_info.value.code == 0

    def test_oserror_on_write_no_crash(self, monkeypatch, tmp_path):
        """OSError during write → silently ignored (fail-open)."""
        import hook_observability

        payload = {**VALID_POST_TOOL, "hook_event_name": "PostToolUse"}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        log = tmp_path / "hook_events.jsonl"
        with patch("hook_observability.LOG_FILE", log):
            with patch("builtins.open", side_effect=OSError("disk full")):
                with pytest.raises(SystemExit) as exc_info:
                    hook_observability.main()
        assert exc_info.value.code == 0

    def test_unknown_event_falls_back(self, monkeypatch, tmp_path):
        """Payload without hook_event_name → event field = 'unknown'."""
        import hook_observability

        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(VALID_POST_TOOL)))
        log = tmp_path / "hook_events.jsonl"
        with patch("hook_observability.LOG_FILE", log):
            with pytest.raises(SystemExit):
                hook_observability.main()

        entry = json.loads(log.read_text().strip())
        assert entry["event"] == "unknown"

    def test_multiple_entries_appended(self, monkeypatch, tmp_path):
        """Multiple calls append separate lines."""
        import hook_observability

        log = tmp_path / "hook_events.jsonl"
        for event in ("PreToolUse", "PostToolUse"):
            payload = {**VALID_POST_TOOL, "hook_event_name": event}
            monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
            with patch("hook_observability.LOG_FILE", log):
                with pytest.raises(SystemExit):
                    hook_observability.main()

        lines = log.read_text().strip().splitlines()
        assert len(lines) == 2
        events = [json.loads(line)["event"] for line in lines]
        assert events == ["PreToolUse", "PostToolUse"]


# ── smart_model_router ────────────────────────────────────────────────────────


class TestSmartModelRouter:
    """smart_model_router: recommend model switch when usage >80%."""

    def test_no_tool_exits_silently(self, monkeypatch):
        """If model-status.py tool doesn't exist → exit 0, no output."""
        import smart_model_router

        with patch("smart_model_router.TOOL") as mock_tool:
            mock_tool.exists.return_value = False
            with pytest.raises(SystemExit) as exc_info:
                smart_model_router.main()
        assert exc_info.value.code == 0

    def test_recursion_guard(self, monkeypatch):
        """CLAUDE_INVOKED_BY set → exit 0 immediately."""
        import smart_model_router

        monkeypatch.setenv("CLAUDE_INVOKED_BY", "subagent")
        with pytest.raises(SystemExit) as exc_info:
            smart_model_router.main()
        assert exc_info.value.code == 0

    def test_subprocess_error_exits_silently(self, monkeypatch):
        """subprocess.SubprocessError → exit 0, no crash."""
        import smart_model_router

        with patch("smart_model_router.TOOL") as mock_tool:
            mock_tool.exists.return_value = True
            with patch("subprocess.run", side_effect=subprocess.SubprocessError("timeout")):
                with pytest.raises(SystemExit) as exc_info:
                    smart_model_router.main()
        assert exc_info.value.code == 0

    def test_tool_non_zero_exit_silent(self, monkeypatch):
        """model-status.py returns non-zero → exit 0, no output."""
        import smart_model_router

        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("smart_model_router.TOOL") as mock_tool:
            mock_tool.exists.return_value = True
            with patch("subprocess.run", return_value=mock_result):
                with pytest.raises(SystemExit) as exc_info:
                    smart_model_router.main()
        assert exc_info.value.code == 0

    def test_low_usage_no_output(self, monkeypatch, capsys):
        """All models <80% usage → no JSON printed, exit 0."""
        import smart_model_router

        usage_data = {
            "claude-sonnet": {"weekly_pct": 40.0},
            "claude-opus": {"weekly_pct": 25.0},
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(usage_data)

        with patch("smart_model_router.TOOL") as mock_tool:
            mock_tool.exists.return_value = True
            with patch("subprocess.run", return_value=mock_result):
                with pytest.raises(SystemExit) as exc_info:
                    smart_model_router.main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.out == "", "must produce no output when usage is low"

    def test_high_usage_emits_json(self, monkeypatch, capsys):
        """Model at ≥80% usage → JSON with additionalContext printed."""
        import smart_model_router

        usage_data = {"claude-sonnet": {"weekly_pct": 95.0}}
        mock_usage = MagicMock(returncode=0, stdout=json.dumps(usage_data))
        mock_suggest = MagicMock(returncode=0, stdout="claude-haiku-2 # fast")

        with patch("smart_model_router.TOOL") as mock_tool:
            mock_tool.exists.return_value = True
            with patch("subprocess.run", side_effect=[mock_usage, mock_suggest]):
                smart_model_router.main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "hookSpecificOutput" in output
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "95%" in ctx or "95" in ctx
        assert "model-router" in ctx

    def test_invalid_json_from_tool_exits_silently(self, monkeypatch):
        """model-status.py returns non-JSON → exit 0."""
        import smart_model_router

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json"

        with patch("smart_model_router.TOOL") as mock_tool:
            mock_tool.exists.return_value = True
            with patch("subprocess.run", return_value=mock_result):
                with pytest.raises(SystemExit) as exc_info:
                    smart_model_router.main()
        assert exc_info.value.code == 0
