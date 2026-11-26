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
        after = _post_payload(
            monkeypatch,
            tmp_path,
            state,
            {"tool_name": TOOL, "hook_event_name": "PostToolUseFailure", "error": "timed out"},
        )
        assert "probe_in_flight" not in after[SERVER]
        assert "probe_started_at" not in after[SERVER]
        assert "opened_at" in after[SERVER]

    def test_successful_probe_resets_entry(self, monkeypatch, tmp_path):
        after = _post(monkeypatch, tmp_path, _stale_state(age=1.0), '{"ok": true}')
        assert after[SERVER] == {"failures": 0}


# --- Added 2026-11-26 (owner review of 06e8175 and of the first follow-up) ----------------------
#
# Claude Code's hooks reference: PostToolUse fires only when a tool call succeeds; a failed call,
# including an MCP error result, fires PostToolUseFailure with an `error` string. The earlier
# candidate scanned tool_response of successful calls for error patterns, which could open the
# circuit on a healthy server, and its "error" test used a payload that PostToolUse never carries.
# A probe now records the tool_use_id that granted it, so a late result of an earlier call cannot
# change the newer probe.

RESPONSE_ERROR = {"content": [{"type": "text", "text": "upstream failed"}], "isError": True}
RESPONSE_OK = {"content": [{"type": "text", "text": "ok"}], "isError": False}


def _post_payload(monkeypatch, tmp_path: Path, state: dict, payload: dict) -> dict:
    state_file = _setup(monkeypatch, tmp_path, state, mcp_circuit_breaker_post)
    with patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=payload):
        mcp_circuit_breaker_post.main()
    return json.loads(state_file.read_text(encoding="utf-8"))


def _pre_with_id(monkeypatch, tmp_path: Path, state: dict, tool_use_id: str) -> tuple[dict, dict]:
    state_file = _setup(monkeypatch, tmp_path, state, mcp_circuit_breaker)
    buf = io.StringIO()
    event = {"tool_name": TOOL, "tool_use_id": tool_use_id}
    with patch("mcp_circuit_breaker.parse_stdin_raw", return_value=event):
        with redirect_stdout(buf):
            mcp_circuit_breaker.main()
    return json.loads(buf.getvalue() or "{}"), json.loads(state_file.read_text(encoding="utf-8"))


class TestEventDecidesOutcome:
    def test_failure_event_opens_the_circuit(self, monkeypatch, tmp_path):
        """Positive control on the defect: with the key the other hooks use, three failures open it."""
        state: dict = {}
        for _ in range(FAILURE_THRESHOLD):
            state = _post_payload(
                monkeypatch,
                tmp_path,
                state,
                {
                    "tool_name": TOOL,
                    "hook_event_name": "PostToolUseFailure",
                    "error": "upstream failed",
                },
            )
        assert state[SERVER].get("opened_at") is not None, state

    def test_success_in_tool_response_resets(self, monkeypatch, tmp_path):
        state = _post_payload(
            monkeypatch,
            tmp_path,
            {SERVER: {"failures": 2}},
            {"tool_name": TOOL, "tool_response": RESPONSE_OK},
        )
        assert state[SERVER] == {"failures": 0}

    def test_healthy_response_quoting_a_timeout_does_not_count(self, monkeypatch, tmp_path):
        """A successful response is a success whatever its text says (regression guard for the
        pattern-scan the earlier candidate used; see mcp_circuit_breaker_post.py)."""
        state: dict = {}
        for _ in range(FAILURE_THRESHOLD + 1):
            state = _post_payload(
                monkeypatch,
                tmp_path,
                state,
                {"tool_name": TOOL, "tool_response": "docs: request timed out after 30s"},
            )
        assert "opened_at" not in state[SERVER], state
        assert state[SERVER] == {"failures": 0}

    def test_interrupted_call_is_not_counted(self, monkeypatch, tmp_path):
        """A user abort is not a server failure."""
        after = _post_payload(
            monkeypatch,
            tmp_path,
            {SERVER: {"failures": 1}},
            {
                "tool_name": TOOL,
                "hook_event_name": "PostToolUseFailure",
                "error": "interrupted",
                "is_interrupt": True,
            },
        )
        assert after[SERVER] == {"failures": 1}


class TestLateResultOfOldProbe:
    def _probing_state(self, probe_id: str) -> dict:
        return {
            SERVER: {
                "failures": FAILURE_THRESHOLD,
                "probe_in_flight": True,
                "probe_started_at": time.time(),
                "probe_id": probe_id,
            }
        }

    def test_late_error_from_old_call_does_not_disturb_new_probe(self, monkeypatch, tmp_path):
        after = _post_payload(
            monkeypatch,
            tmp_path,
            self._probing_state("new-probe"),
            {
                "tool_name": TOOL,
                "tool_use_id": "old-call",
                "hook_event_name": "PostToolUseFailure",
                "error": "upstream failed",
            },
        )
        assert after[SERVER]["probe_in_flight"] is True
        assert after[SERVER]["probe_id"] == "new-probe"
        assert "opened_at" not in after[SERVER]

    def test_late_success_from_old_call_does_not_close_the_circuit(self, monkeypatch, tmp_path):
        after = _post_payload(
            monkeypatch,
            tmp_path,
            self._probing_state("new-probe"),
            {"tool_name": TOOL, "tool_use_id": "old-call", "tool_response": RESPONSE_OK},
        )
        assert after[SERVER]["probe_in_flight"] is True
        assert after[SERVER]["failures"] == FAILURE_THRESHOLD

    def test_probe_own_error_still_resolves_it(self, monkeypatch, tmp_path):
        after = _post_payload(
            monkeypatch,
            tmp_path,
            self._probing_state("new-probe"),
            {
                "tool_name": TOOL,
                "tool_use_id": "new-probe",
                "hook_event_name": "PostToolUseFailure",
                "error": "upstream failed",
            },
        )
        assert "probe_in_flight" not in after[SERVER]
        assert after[SERVER].get("opened_at") is not None

    def test_grant_records_the_probe_id(self, monkeypatch, tmp_path):
        state = {
            SERVER: {"failures": FAILURE_THRESHOLD, "opened_at": time.time() - RECOVERY_TIMEOUT - 1}
        }
        out, after = _pre_with_id(monkeypatch, tmp_path, state, "probe-7")
        assert out.get("decision") != "block", out
        assert after[SERVER]["probe_id"] == "probe-7"

    def test_post_without_id_keeps_legacy_behaviour(self, monkeypatch, tmp_path):
        """Without tool_use_id nothing can be matched, so the probe is resolved as before."""
        after = _post_payload(
            monkeypatch,
            tmp_path,
            self._probing_state("new-probe"),
            {
                "tool_name": TOOL,
                "hook_event_name": "PostToolUseFailure",
                "error": "upstream failed",
            },
        )
        assert "probe_in_flight" not in after[SERVER]


class TestRecoveryWindowAndRepeatedFailure:
    def test_recovery_window_is_measured_from_the_last_opening(self, monkeypatch, tmp_path):
        """Just opened: still blocked. Opened a full window ago: a probe is granted."""
        blocked, _ = _pre(
            monkeypatch,
            tmp_path,
            {SERVER: {"failures": FAILURE_THRESHOLD, "opened_at": time.time()}},
        )
        assert blocked.get("decision") == "block", blocked
        allowed, _ = _pre(
            monkeypatch,
            tmp_path,
            {SERVER: {"failures": FAILURE_THRESHOLD, "opened_at": time.time() - RECOVERY_TIMEOUT}},
        )
        assert allowed.get("decision") != "block", allowed

    def test_failed_probe_reopens_and_the_next_window_starts_fresh(self, monkeypatch, tmp_path):
        state = {
            SERVER: {"failures": FAILURE_THRESHOLD, "opened_at": time.time() - RECOVERY_TIMEOUT - 1}
        }
        _, granted = _pre_with_id(monkeypatch, tmp_path, state, "probe-1")
        reopened = _post_payload(
            monkeypatch,
            tmp_path,
            granted,
            {
                "tool_name": TOOL,
                "tool_use_id": "probe-1",
                "hook_event_name": "PostToolUseFailure",
                "error": "upstream failed",
            },
        )
        assert reopened[SERVER]["failures"] == FAILURE_THRESHOLD + 1
        assert abs(reopened[SERVER]["opened_at"] - time.time()) < 5
        blocked, _ = _pre(monkeypatch, tmp_path, reopened)
        assert blocked.get("decision") == "block", blocked

    def test_overlong_but_alive_probe_is_superseded_and_its_late_result_ignored(
        self, monkeypatch, tmp_path
    ):
        """Probe A outlives the window; probe B is granted. A's late error must not touch B."""
        stale_a = {
            SERVER: {
                "failures": FAILURE_THRESHOLD,
                "probe_in_flight": True,
                "probe_started_at": time.time() - RECOVERY_TIMEOUT - 5,
                "probe_id": "probe-A",
            }
        }
        _, with_b = _pre_with_id(monkeypatch, tmp_path, stale_a, "probe-B")
        assert with_b[SERVER]["probe_id"] == "probe-B"
        after_late_a = _post_payload(
            monkeypatch,
            tmp_path,
            with_b,
            {
                "tool_name": TOOL,
                "tool_use_id": "probe-A",
                "hook_event_name": "PostToolUseFailure",
                "error": "upstream failed",
            },
        )
        assert after_late_a[SERVER]["probe_id"] == "probe-B"
        assert "opened_at" not in after_late_a[SERVER]
        closed = _post_payload(
            monkeypatch,
            tmp_path,
            after_late_a,
            {"tool_name": TOOL, "tool_use_id": "probe-B", "tool_response": RESPONSE_OK},
        )
        assert closed[SERVER]["failures"] == 0
        assert "probe_in_flight" not in closed[SERVER]


class TestInterruptedProbe:
    def _aborted(self, monkeypatch, tmp_path, started_ago: float) -> dict:
        state = {
            SERVER: {
                "failures": FAILURE_THRESHOLD,
                "probe_in_flight": True,
                "probe_started_at": time.time() - started_ago,
                "probe_id": "probe-X",
            }
        }
        return _post_payload(
            monkeypatch,
            tmp_path,
            state,
            {
                "tool_name": TOOL,
                "hook_event_name": "PostToolUseFailure",
                "error": "interrupted",
                "is_interrupt": True,
                "tool_use_id": "probe-X",
            },
        )

    def test_aborted_probe_is_released_without_counting(self, monkeypatch, tmp_path):
        after = self._aborted(monkeypatch, tmp_path, started_ago=1.0)
        assert "probe_in_flight" not in after[SERVER]
        assert "probe_id" not in after[SERVER]
        assert after[SERVER]["failures"] == FAILURE_THRESHOLD

    def test_next_call_gets_the_probe_at_once(self, monkeypatch, tmp_path):
        """Released means the next call is a probe now, not after another window."""
        after = self._aborted(monkeypatch, tmp_path, started_ago=1.0)
        allowed, granted = _pre(monkeypatch, tmp_path, after)
        assert allowed.get("decision") != "block", allowed
        assert granted[SERVER]["probe_in_flight"] is True

    def test_release_is_never_later_than_the_stale_path(self, monkeypatch, tmp_path):
        """The stale path would grant a probe at probe_started_at + RECOVERY_TIMEOUT.
        An abort must not make the server wait longer than that (review 2026-11-26)."""
        started_ago = 50.0
        after = self._aborted(monkeypatch, tmp_path, started_ago=started_ago)
        stale_deadline = time.time() - started_ago + RECOVERY_TIMEOUT
        window_end = after[SERVER]["opened_at"] + RECOVERY_TIMEOUT
        assert window_end <= stale_deadline + 1, (window_end, stale_deadline)


class TestSupersededProbeAfterReplacementFails:
    """Codex P2 on PR #578: probe A is superseded by probe B; B fails and clears the in-flight
    probe; A's late success must not reset the counter and close the circuit."""

    def test_late_success_of_superseded_probe_does_not_close_the_circuit(
        self, monkeypatch, tmp_path
    ):
        stale_a = {
            SERVER: {
                "failures": FAILURE_THRESHOLD,
                "probe_in_flight": True,
                "probe_started_at": time.time() - RECOVERY_TIMEOUT - 5,
                "probe_id": "probe-A",
            }
        }
        _, with_b = _pre_with_id(monkeypatch, tmp_path, stale_a, "probe-B")
        failed_b = _post_payload(
            monkeypatch,
            tmp_path,
            with_b,
            {
                "tool_name": TOOL,
                "hook_event_name": "PostToolUseFailure",
                "error": "upstream failed",
                "tool_use_id": "probe-B",
            },
        )
        assert "probe_in_flight" not in failed_b[SERVER]
        assert failed_b[SERVER]["failures"] == FAILURE_THRESHOLD + 1
        opened = failed_b[SERVER]["opened_at"]
        after_a = _post_payload(
            monkeypatch,
            tmp_path,
            failed_b,
            {"tool_name": TOOL, "tool_use_id": "probe-A", "tool_response": RESPONSE_OK},
        )
        assert after_a[SERVER]["failures"] == FAILURE_THRESHOLD + 1, after_a
        assert after_a[SERVER]["opened_at"] == opened
        blocked, _ = _pre(monkeypatch, tmp_path, after_a)
        assert blocked.get("decision") == "block", blocked

    def test_late_failure_of_superseded_probe_is_ignored_too(self, monkeypatch, tmp_path):
        stale_a = {
            SERVER: {
                "failures": FAILURE_THRESHOLD,
                "probe_in_flight": True,
                "probe_started_at": time.time() - RECOVERY_TIMEOUT - 5,
                "probe_id": "probe-A",
            }
        }
        _, with_b = _pre_with_id(monkeypatch, tmp_path, stale_a, "probe-B")
        after_b_ok = _post_payload(
            monkeypatch,
            tmp_path,
            with_b,
            {"tool_name": TOOL, "tool_use_id": "probe-B", "tool_response": RESPONSE_OK},
        )
        assert after_b_ok[SERVER]["failures"] == 0
        after_a_fail = _post_payload(
            monkeypatch,
            tmp_path,
            after_b_ok,
            {
                "tool_name": TOOL,
                "hook_event_name": "PostToolUseFailure",
                "error": "upstream failed",
                "tool_use_id": "probe-A",
            },
        )
        assert after_a_fail[SERVER]["failures"] == 0, after_a_fail
