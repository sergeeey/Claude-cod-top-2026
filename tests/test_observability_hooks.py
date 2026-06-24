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

VALID_TOKEN_PAYLOAD = {
    "tokens": 500,
}


def _stdin(data: dict) -> io.StringIO:
    return io.StringIO(json.dumps(data))


# ── model_usage_tracker ───────────────────────────────────────────────────────


class TestModelUsageTracker:
    """model_usage_tracker: weekly per-model token counter persisted to JSON."""

    def test_happy_path_writes_usage_file(self, monkeypatch, tmp_path):
        """Payload with tokens > 0 → USAGE_FILE written with weekly counter."""
        import model_usage_tracker

        monkeypatch.setattr("sys.stdin", _stdin(VALID_TOKEN_PAYLOAD))
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        with patch("model_usage_tracker.USAGE_FILE", tmp_path / "model_usage.json"):
            model_usage_tracker.main()

        usage_file = tmp_path / "model_usage.json"
        assert usage_file.exists(), "USAGE_FILE not created"
        data = json.loads(usage_file.read_text())
        assert "weekly" in data
        assert data["weekly"]["claude-sonnet-4-6"] == 500

    def test_usage_under_usage_key(self, monkeypatch, tmp_path):
        """Payload with usage.total_tokens → tokens counted correctly."""
        import model_usage_tracker

        payload = {"usage": {"total_tokens": 1000}}
        monkeypatch.setattr("sys.stdin", _stdin(payload))
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku")
        with patch("model_usage_tracker.USAGE_FILE", tmp_path / "model_usage.json"):
            model_usage_tracker.main()

        data = json.loads((tmp_path / "model_usage.json").read_text())
        assert data["weekly"]["claude-haiku"] == 1000

    def test_empty_stdin_no_crash(self, monkeypatch, tmp_path):
        """Empty stdin → exit 0, no file written."""
        import model_usage_tracker

        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        usage_file = tmp_path / "model_usage.json"
        with patch("model_usage_tracker.USAGE_FILE", usage_file):
            with pytest.raises(SystemExit) as exc_info:
                model_usage_tracker.main()
        assert exc_info.value.code == 0
        assert not usage_file.exists()

    def test_malformed_json_no_crash(self, monkeypatch, tmp_path):
        """Malformed JSON → exit 0, no file written."""
        import model_usage_tracker

        monkeypatch.setattr("sys.stdin", io.StringIO("not { json }"))
        usage_file = tmp_path / "model_usage.json"
        with patch("model_usage_tracker.USAGE_FILE", usage_file):
            with pytest.raises(SystemExit) as exc_info:
                model_usage_tracker.main()
        assert exc_info.value.code == 0
        assert not usage_file.exists()

    def test_zero_tokens_exits_silently(self, monkeypatch, tmp_path):
        """Payload with tokens=0 → exit 0, no file written (nothing to count)."""
        import model_usage_tracker

        monkeypatch.setattr("sys.stdin", _stdin({"tokens": 0}))
        usage_file = tmp_path / "model_usage.json"
        with patch("model_usage_tracker.USAGE_FILE", usage_file):
            with pytest.raises(SystemExit) as exc_info:
                model_usage_tracker.main()
        assert exc_info.value.code == 0
        assert not usage_file.exists()

    def test_recursion_guard_skips_write(self, monkeypatch, tmp_path):
        """CLAUDE_INVOKED_BY set → exit 0 immediately, no file written."""
        import model_usage_tracker

        monkeypatch.setenv("CLAUDE_INVOKED_BY", "subagent")
        monkeypatch.setattr("sys.stdin", _stdin(VALID_TOKEN_PAYLOAD))
        usage_file = tmp_path / "model_usage.json"
        with patch("model_usage_tracker.USAGE_FILE", usage_file):
            with pytest.raises(SystemExit) as exc_info:
                model_usage_tracker.main()
        assert exc_info.value.code == 0
        assert not usage_file.exists(), "must not write when CLAUDE_INVOKED_BY is set"

    def test_oserror_on_write_no_crash(self, monkeypatch, tmp_path):
        """OSError during write → silently ignored (fail-open)."""
        import model_usage_tracker

        monkeypatch.setattr("sys.stdin", _stdin(VALID_TOKEN_PAYLOAD))
        usage_file = tmp_path / "model_usage.json"
        with patch("model_usage_tracker.USAGE_FILE", usage_file):
            with patch("os.replace", side_effect=OSError("disk full")):
                model_usage_tracker.main()  # must not raise

    def test_multiple_calls_accumulate(self, monkeypatch, tmp_path):
        """Multiple calls accumulate token counts, not overwrite."""
        import model_usage_tracker

        usage_file = tmp_path / "model_usage.json"
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet")
        for tokens in (100, 200, 300):
            monkeypatch.setattr("sys.stdin", _stdin({"tokens": tokens}))
            with patch("model_usage_tracker.USAGE_FILE", usage_file):
                model_usage_tracker.main()

        data = json.loads(usage_file.read_text())
        assert data["weekly"]["claude-sonnet"] == 600  # 100 + 200 + 300

    def test_default_model_fallback(self, monkeypatch, tmp_path):
        """ANTHROPIC_MODEL not set → uses default model name."""
        import model_usage_tracker

        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
        monkeypatch.setattr("sys.stdin", _stdin(VALID_TOKEN_PAYLOAD))
        with patch("model_usage_tracker.USAGE_FILE", tmp_path / "model_usage.json"):
            model_usage_tracker.main()

        data = json.loads((tmp_path / "model_usage.json").read_text())
        assert len(data["weekly"]) == 1
        model_key = next(iter(data["weekly"]))
        assert "claude" in model_key  # default contains "claude"


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
