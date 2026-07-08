"""Concurrency regression test for the MCP circuit breaker race condition.

WHY this file exists: mcp_circuit_breaker_post.py's read-modify-write of the
shared state file (load_json_state -> mutate -> save_json_state) previously
ran with no locking. Two concurrent failing calls to the same server could
both read the same "before" failures count and the last writer would win,
silently losing an increment and delaying (or missing) when the circuit
should open. This test drives real threads through the real (file_lock-guarded)
code path against a real state file -- not mocked I/O -- so it can actually
observe the race being closed, not just assert the lock exists.
"""

import sys
import threading
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

import mcp_circuit_breaker_post  # noqa: E402
from utils import load_json_state  # noqa: E402


class TestConcurrentFailuresDoNotLoseIncrements:
    def test_twenty_concurrent_failures_all_counted(self, tmp_path, monkeypatch):
        state_file = tmp_path / "circuit_state.json"
        monkeypatch.setattr(mcp_circuit_breaker_post, "STATE_FILE", state_file)
        monkeypatch.setattr(mcp_circuit_breaker_post, "_LOCK_FILE", state_file.with_suffix(".lock"))

        event = {"tool_name": "mcp__context7__search", "tool_result": "connection refused"}

        def run_once():
            with patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event):
                mcp_circuit_breaker_post.main()

        threads = [threading.Thread(target=run_once) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final_state = load_json_state(state_file)
        # WHY exactly 20, not "at least 1": without the lock, concurrent
        # threads racing on the same read-modify-write would very likely
        # undercount here -- this is the actual failure mode the fix closes.
        assert final_state["context7"]["failures"] == 20

    def test_concurrent_failures_across_two_servers_do_not_cross_contaminate(
        self, tmp_path, monkeypatch
    ):
        state_file = tmp_path / "circuit_state.json"
        monkeypatch.setattr(mcp_circuit_breaker_post, "STATE_FILE", state_file)
        monkeypatch.setattr(mcp_circuit_breaker_post, "_LOCK_FILE", state_file.with_suffix(".lock"))

        event_a = {"tool_name": "mcp__context7__search", "tool_result": "timed out"}
        event_b = {"tool_name": "mcp__playwright__click", "tool_result": "timed out"}

        def run(event):
            with patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event):
                mcp_circuit_breaker_post.main()

        threads = [
            threading.Thread(target=run, args=(event_a if i % 2 == 0 else event_b,))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final_state = load_json_state(state_file)
        assert final_state["context7"]["failures"] == 10
        assert final_state["playwright"]["failures"] == 10
