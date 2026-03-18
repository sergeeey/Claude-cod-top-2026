"""Unit tests for hooks/mcp_circuit_breaker_post.py."""

from __future__ import annotations

import io
import json
import sys

import mcp_circuit_breaker_post


def _run_main_with_stdin(payload: dict) -> None:
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        mcp_circuit_breaker_post.main()
    finally:
        sys.stdin = old_stdin


class TestCircuitBreakerPost:
    def test_non_mcp_skipped(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(mcp_circuit_breaker_post, "STATE_FILE", state_file)

        _run_main_with_stdin({"tool_name": "Read", "tool_result": "ok"})
        assert not state_file.exists()

    def test_handles_missing_state_file_creates_on_write(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(mcp_circuit_breaker_post, "STATE_FILE", state_file)

        _run_main_with_stdin({"tool_name": "mcp__context7__search", "tool_result": "ok"})
        assert state_file.exists()
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state["context7"]["failures"] == 0

    def test_failure_increments_counter(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(mcp_circuit_breaker_post, "STATE_FILE", state_file)

        _run_main_with_stdin({"tool_name": "mcp__ctx__call", "tool_result": "connection refused"})
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state["ctx"]["failures"] == 1

        _run_main_with_stdin({"tool_name": "mcp__ctx__call", "tool_result": "timed out"})
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state["ctx"]["failures"] == 2

    def test_failure_at_threshold_opens(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(mcp_circuit_breaker_post, "STATE_FILE", state_file)

        for _ in range(mcp_circuit_breaker_post.FAILURE_THRESHOLD):
            _run_main_with_stdin({"tool_name": "mcp__ctx__call", "tool_result": "error: failed to connect"})

        state = json.loads(state_file.read_text(encoding="utf-8"))
        entry = state["ctx"]
        assert entry["failures"] >= mcp_circuit_breaker_post.FAILURE_THRESHOLD
        assert "opened_at" in entry

    def test_success_resets_failures_and_clears_open(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(mcp_circuit_breaker_post, "STATE_FILE", state_file)

        # Create an "open" state
        state_file.write_text(json.dumps({"ctx": {"failures": 3, "opened_at": 123.0}}), encoding="utf-8")

        _run_main_with_stdin({"tool_name": "mcp__ctx__call", "tool_result": "OK"})

        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state["ctx"] == {"failures": 0}

