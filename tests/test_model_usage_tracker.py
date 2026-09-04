"""Tests for model_usage_tracker.py's Agent-specific exact-token fix.

GitHub issue #227: `tool_response` for an `Agent`-type PostToolUse event
already carries `resolvedModel`/`totalTokens`/`totalDurationMs`/
`totalToolUseCount` -- exact numbers, not proxies. This file verifies the
hook now prefers those fields when present, while still computing the
byte-proxy fields for every entry (existing consumers keep working).
"""

from __future__ import annotations

import io
import json


def _run(monkeypatch, tmp_path, data: dict) -> dict:
    import model_usage_tracker

    log_path = tmp_path / "model_usage.jsonl"
    monkeypatch.setattr(model_usage_tracker, "LOG_FILE", log_path)
    monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
    model_usage_tracker.main()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    return json.loads(lines[-1])


class TestAgentExactTokens:
    def test_agent_call_with_real_fields_logs_them_exactly(self, monkeypatch, tmp_path):
        entry = _run(
            monkeypatch,
            tmp_path,
            {
                "tool_name": "Agent",
                "session_id": "abc12345",
                "tool_input": {"prompt": "find X"},
                "tool_response": {
                    "resolvedModel": "claude-haiku-4-5-20251001",
                    "totalTokens": 41957,
                    "totalDurationMs": 4741,
                    "totalToolUseCount": 0,
                    "usage": {"input_tokens": 10, "output_tokens": 157},
                },
            },
        )
        assert entry["resolved_model"] == "claude-haiku-4-5-20251001"
        assert entry["total_tokens_exact"] == 41957
        assert entry["total_duration_ms"] == 4741
        assert entry["total_tool_use_count"] == 0
        assert entry["token_source"] == "exact"

    def test_agent_call_still_computes_proxy_fields_for_compat(self, monkeypatch, tmp_path):
        """otel_exporter.py reads est_out_tok/est_in_tok unconditionally -- must not disappear."""
        entry = _run(
            monkeypatch,
            tmp_path,
            {
                "tool_name": "Agent",
                "session_id": "abc12345",
                "tool_input": {"prompt": "x"},
                "tool_response": {
                    "resolvedModel": "claude-haiku-4-5-20251001",
                    "totalTokens": 100,
                    "totalDurationMs": 1000,
                    "totalToolUseCount": 1,
                },
            },
        )
        assert "resp_bytes" in entry
        assert "inp_bytes" in entry
        assert "est_out_tok" in entry
        assert "est_in_tok" in entry

    def test_agent_call_without_resolved_model_falls_back_to_proxy(self, monkeypatch, tmp_path):
        """Not every Agent response is guaranteed to carry the exact fields -- degrade gracefully."""
        entry = _run(
            monkeypatch,
            tmp_path,
            {
                "tool_name": "Agent",
                "session_id": "abc12345",
                "tool_input": {"prompt": "x"},
                "tool_response": {"status": "completed"},
            },
        )
        assert "token_source" not in entry
        assert "resolved_model" not in entry
        assert "est_out_tok" in entry

    def test_non_agent_tool_never_gets_exact_fields(self, monkeypatch, tmp_path):
        """The exact-field path is Agent-specific; Bash/Read/etc. keep using the proxy only."""
        entry = _run(
            monkeypatch,
            tmp_path,
            {
                "tool_name": "Bash",
                "session_id": "abc12345",
                "tool_input": {"command": "ls"},
                "tool_response": {
                    "resolvedModel": "should-be-ignored",
                    "totalTokens": 999,
                },
            },
        )
        assert "token_source" not in entry
        assert "resolved_model" not in entry

    def test_agent_call_with_zero_total_tokens_still_treated_as_exact(self, monkeypatch, tmp_path):
        """totalTokens=0 is a legitimate value, not missing data -- must not be treated as falsy-absent."""
        entry = _run(
            monkeypatch,
            tmp_path,
            {
                "tool_name": "Agent",
                "session_id": "abc12345",
                "tool_input": {"prompt": "x"},
                "tool_response": {
                    "resolvedModel": "claude-haiku-4-5-20251001",
                    "totalTokens": 0,
                    "totalDurationMs": 5,
                    "totalToolUseCount": 0,
                },
            },
        )
        assert entry["token_source"] == "exact"
        assert entry["total_tokens_exact"] == 0
