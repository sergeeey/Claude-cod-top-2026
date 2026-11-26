"""A HALF_OPEN probe whose PostToolUse never arrives must not lock the MCP server out forever.

WHY this file exists (found 2026-11-26, self-healing review of hooks/mcp_circuit_breaker*.py):
the PreToolUse hook moves a server from HALF_OPEN to a probe by popping `opened_at` and setting
`probe_in_flight`. Only mcp_circuit_breaker_post.py clears that flag. If the probe call is
interrupted or the post hook never runs, the state stays `failures >= threshold`, no `opened_at`,
`probe_in_flight` set. get_circuit_status() then reports OPEN forever, so every later call to that
server is blocked and nothing in the hooks ever reaches HALF_OPEN again.

These tests drive the real PreToolUse/PostToolUse entry points against a real state file.
"""

from __future__ import annotations

import io
import json
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hooks"))

import mcp_circuit_breaker  # noqa: E402
import mcp_circuit_breaker_post  # noqa: E402
from mcp_circuit_breaker import FAILURE_THRESHOLD, RECOVERY_TIMEOUT  # noqa: E402

TOOL = "mcp__context7__search"
SERVER = "context7"


def _setup(monkeypatch, tmp_path: Path, state: dict, module) -> Path:
    state_file = tmp_path / "mcp_circuit_state.json"
    state_file.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(module, "STATE_FILE", state_file)
    monkeypatch.setattr(module, "_LOCK_FILE", tmp_path / "mcp_circuit_state.lock")
    return state_file


def _pre(monkeypatch, tmp_path: Path, state: dict) -> tuple[dict, dict]:
    """Run PreToolUse once. Returns (hook output, state file after the call)."""
    state_file = _setup(monkeypatch, tmp_path, state, mcp_circuit_breaker)
    buf = io.StringIO()
    with patch("mcp_circuit_breaker.parse_stdin_raw", return_value={"tool_name": TOOL}):
        with redirect_stdout(buf):
            mcp_circuit_breaker.main()
    return json.loads(buf.getvalue() or "{}"), json.loads(state_file.read_text(encoding="utf-8"))


def _post(monkeypatch, tmp_path: Path, state: dict, result: str) -> dict:
    state_file = _setup(monkeypatch, tmp_path, state, mcp_circuit_breaker_post)
    event = {"tool_name": TOOL, "tool_result": result}
    with patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event):
        mcp_circuit_breaker_post.main()
    return json.loads(state_file.read_text(encoding="utf-8"))


def _stale_state(age: float) -> dict:
    return {
        SERVER: {
            "failures": FAILURE_THRESHOLD,
            "probe_in_flight": True,
            "probe_started_at": time.time() - age,
        }
    }


class TestStaleProbeRecovery:
    def test_stale_probe_lets_a_new_probe_through(self, monkeypatch, tmp_path):
        """Positive control on the defect: before the fix this returns a block with reason OPEN."""
        out, _ = _pre(monkeypatch, tmp_path, _stale_state(age=RECOVERY_TIMEOUT * 2))
        assert out.get("decision") != "block", out

    def test_fresh_probe_still_blocks_concurrent_calls(self, monkeypatch, tmp_path):
        """A probe that is genuinely in flight must keep the other calls out."""
        out, _ = _pre(monkeypatch, tmp_path, _stale_state(age=1.0))
        assert out.get("decision") == "block", out

    def test_legacy_probe_without_timestamp_is_treated_as_stale(self, monkeypatch, tmp_path):
        """State written before this fix has no probe_started_at; it must not stay locked."""
        state = {SERVER: {"failures": FAILURE_THRESHOLD, "probe_in_flight": True}}
        out, _ = _pre(monkeypatch, tmp_path, state)
        assert out.get("decision") != "block", out

    def test_granted_probe_records_its_start_time(self, monkeypatch, tmp_path):
        state = {
            SERVER: {"failures": FAILURE_THRESHOLD, "opened_at": time.time() - RECOVERY_TIMEOUT - 1}
        }
        before = time.time()
        out, after = _pre(monkeypatch, tmp_path, state)
        assert out.get("decision") != "block", out
        assert after[SERVER]["probe_in_flight"] is True
        assert before <= after[SERVER]["probe_started_at"] <= time.time()

    def test_lost_probe_cannot_lock_forever_end_to_end(self, monkeypatch, tmp_path):
        """Open -> HALF_OPEN probe granted -> post never runs -> later call is still allowed."""
        state = {
            SERVER: {"failures": FAILURE_THRESHOLD, "opened_at": time.time() - RECOVERY_TIMEOUT - 1}
        }
        out, after = _pre(monkeypatch, tmp_path, state)
        assert out.get("decision") != "block", out
        # Simulate the lost PostToolUse: rewind the probe start past the recovery window.
        after[SERVER]["probe_started_at"] = time.time() - RECOVERY_TIMEOUT - 1
        out2, _ = _pre(monkeypatch, tmp_path, after)
        assert out2.get("decision") != "block", out2


class TestPostClearsProbeTimestamp:
    def test_failed_probe_clears_flags_and_reopens(self, monkeypatch, tmp_path):
        state = _stale_state(age=1.0)
        after = _post(monkeypatch, tmp_path, state, "request timed out after 30s")
        assert "probe_in_flight" not in after[SERVER]
        assert "probe_started_at" not in after[SERVER]
        assert "opened_at" in after[SERVER]

    def test_successful_probe_resets_entry(self, monkeypatch, tmp_path):
        after = _post(monkeypatch, tmp_path, _stale_state(age=1.0), '{"ok": true}')
        assert after[SERVER] == {"failures": 0}
