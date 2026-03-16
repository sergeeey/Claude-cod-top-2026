"""Unit tests for hooks/mcp_circuit_breaker.py — Circuit Breaker pattern."""

import time

from mcp_circuit_breaker import (
    DEFAULT_FALLBACK,
    FAILURE_THRESHOLD,
    FALLBACKS,
    RECOVERY_TIMEOUT,
    get_circuit_status,
    get_server_name,
    load_state,
    reset_circuit,
    save_state,
)

# === get_server_name ===


class TestGetServerName:
    def test_valid_mcp_tool(self):
        assert get_server_name("mcp__context7__search") == "context7"

    def test_valid_mcp_tool_with_underscores(self):
        assert get_server_name("mcp__basic-memory__write") == "basic-memory"

    def test_non_mcp_tool(self):
        assert get_server_name("Read") is None
        assert get_server_name("Bash") is None

    def test_malformed_mcp(self):
        assert get_server_name("mcp__only") is None

    def test_empty_string(self):
        assert get_server_name("") is None


# === get_circuit_status ===


class TestGetCircuitStatus:
    def test_closed_no_failures(self):
        assert get_circuit_status({}) == "CLOSED"

    def test_closed_under_threshold(self):
        assert get_circuit_status({"failures": FAILURE_THRESHOLD - 1}) == "CLOSED"

    def test_open_at_threshold(self):
        entry = {"failures": FAILURE_THRESHOLD, "opened_at": time.time()}
        assert get_circuit_status(entry) == "OPEN"

    def test_open_above_threshold(self):
        entry = {"failures": FAILURE_THRESHOLD + 5, "opened_at": time.time()}
        assert get_circuit_status(entry) == "OPEN"

    def test_half_open_after_timeout(self):
        entry = {
            "failures": FAILURE_THRESHOLD,
            "opened_at": time.time() - RECOVERY_TIMEOUT - 1,
        }
        assert get_circuit_status(entry) == "HALF_OPEN"

    def test_open_without_opened_at(self):
        """Edge: failures >= threshold but no opened_at → OPEN (no timeout to check)."""
        entry = {"failures": FAILURE_THRESHOLD}
        assert get_circuit_status(entry) == "OPEN"


# === reset_circuit (replaces old record_open) ===


class TestResetCircuit:
    def test_resets_failures_to_zero(self):
        state = {"ctx": {"failures": FAILURE_THRESHOLD, "opened_at": 1000.0}}
        state = reset_circuit(state, "ctx")
        assert state["ctx"]["failures"] == 0

    def test_removes_opened_at(self):
        state = {"ctx": {"failures": FAILURE_THRESHOLD, "opened_at": 1000.0}}
        state = reset_circuit(state, "ctx")
        assert "opened_at" not in state["ctx"]

    def test_reset_unknown_server(self):
        state = {}
        state = reset_circuit(state, "new_server")
        assert state["new_server"] == {"failures": 0}

    def test_half_open_success_closes_circuit(self):
        """Integration: HALF_OPEN + reset → next status is CLOSED.

        WHY: This is the critical fix — previously only opened_at was removed
        but failures stayed >= threshold, causing infinite OPEN→HALF_OPEN→OPEN.
        """
        state = {
            "ctx": {
                "failures": FAILURE_THRESHOLD,
                "opened_at": time.time() - RECOVERY_TIMEOUT - 1,
            }
        }
        # Verify it's HALF_OPEN
        assert get_circuit_status(state["ctx"]) == "HALF_OPEN"
        # Reset (what PreToolUse now does)
        state = reset_circuit(state, "ctx")
        # Verify it's CLOSED
        assert get_circuit_status(state["ctx"]) == "CLOSED"


# === State persistence ===


class TestStatePersistence:
    def test_save_and_load(self, tmp_state_file, monkeypatch):
        import mcp_circuit_breaker

        monkeypatch.setattr(mcp_circuit_breaker, "STATE_FILE", tmp_state_file)

        state = {"server1": {"failures": 2}}
        save_state(state)
        loaded = load_state()
        assert loaded == state

    def test_load_missing_file(self, tmp_state_file, monkeypatch):
        import mcp_circuit_breaker

        monkeypatch.setattr(mcp_circuit_breaker, "STATE_FILE", tmp_state_file)

        assert load_state() == {}

    def test_load_corrupt_json(self, tmp_state_file, monkeypatch):
        import mcp_circuit_breaker

        monkeypatch.setattr(mcp_circuit_breaker, "STATE_FILE", tmp_state_file)
        tmp_state_file.write_text("not json at all")

        assert load_state() == {}


# === Fallbacks ===


class TestFallbacks:
    def test_known_servers_have_fallbacks(self):
        for server in ["context7", "playwright", "basic-memory", "ollama"]:
            assert server in FALLBACKS

    def test_default_fallback_exists(self):
        assert DEFAULT_FALLBACK
