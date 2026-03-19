"""Unit tests for hooks/mcp_circuit_breaker.py — Circuit Breaker pattern."""

import time

from mcp_circuit_breaker import (
    DEFAULT_FALLBACK,
    FAILURE_THRESHOLD,
    FALLBACKS,
    RECOVERY_TIMEOUT,
    get_circuit_status,
    record_open,
)
from utils import get_mcp_server_name, load_json_state, save_json_state

# === get_mcp_server_name (moved to utils) ===


class TestGetServerName:
    def test_valid_mcp_tool(self):
        assert get_mcp_server_name("mcp__context7__search") == "context7"

    def test_valid_mcp_tool_with_underscores(self):
        assert get_mcp_server_name("mcp__basic-memory__write") == "basic-memory"

    def test_non_mcp_tool(self):
        assert get_mcp_server_name("Read") is None
        assert get_mcp_server_name("Bash") is None

    def test_malformed_mcp(self):
        assert get_mcp_server_name("mcp__only") is None

    def test_empty_string(self):
        assert get_mcp_server_name("") is None


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


# === record_open ===


class TestRecordOpen:
    def test_increments_failures(self):
        state = {"ctx": {"failures": 1}}
        state = record_open(state, "ctx")
        assert state["ctx"]["failures"] == 2

    def test_new_server_starts_at_one(self):
        state = {}
        state = record_open(state, "new_server")
        assert state["new_server"]["failures"] == 1

    def test_sets_opened_at_at_threshold(self):
        state = {"ctx": {"failures": FAILURE_THRESHOLD - 1}}
        state = record_open(state, "ctx")
        assert "opened_at" in state["ctx"]

    def test_does_not_overwrite_existing_opened_at(self):
        original_time = 1000.0
        state = {"ctx": {"failures": FAILURE_THRESHOLD, "opened_at": original_time}}
        state = record_open(state, "ctx")
        assert state["ctx"]["opened_at"] == original_time


# === State persistence (via utils) ===


class TestStatePersistence:
    def test_save_and_load(self, tmp_path):
        state_file = tmp_path / "state.json"
        state = {"server1": {"failures": 2}}
        save_json_state(state_file, state)
        loaded = load_json_state(state_file)
        assert loaded == state

    def test_load_missing_file(self, tmp_path):
        state_file = tmp_path / "nonexistent.json"
        assert load_json_state(state_file) == {}

    def test_load_corrupt_json(self, tmp_path):
        state_file = tmp_path / "bad.json"
        state_file.write_text("not json at all")
        assert load_json_state(state_file) == {}


# === Fallbacks ===


class TestFallbacks:
    def test_known_servers_have_fallbacks(self):
        for server in ["context7", "playwright", "basic-memory", "ollama"]:
            assert server in FALLBACKS

    def test_default_fallback_exists(self):
        assert DEFAULT_FALLBACK
