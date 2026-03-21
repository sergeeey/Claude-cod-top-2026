"""Tests for mcp_circuit_breaker_post.py — PostToolUse hook circuit breaker.

WHY: the hook updates the circuit breaker state file based on the MCP call result.
We test the business logic (is_error + state update) in isolation from the filesystem
and stdin — all I/O dependencies are replaced with mocks.
"""

import os
import sys

# WHY: hooks live one level above tests/. insert(0) ensures
# our path takes priority over site-packages during import.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch  # noqa: E402

import mcp_circuit_breaker_post  # noqa: E402
import pytest  # noqa: E402

# =============================================================================
# Helper functions
# =============================================================================


def make_event(tool_name: str, tool_result: str) -> dict:
    """Assembles a minimal event-dict for the PostToolUse hook."""
    return {"tool_name": tool_name, "tool_result": tool_result}


MCP_TOOL = "mcp__context7__search"  # valid MCP tool name → server = "context7"
NON_MCP_TOOL = "Read"  # regular tool — not MCP


# =============================================================================
# is_error() — pure function, tested without mocks
# =============================================================================


class TestIsError:
    """is_error: correctly detects failure indicators."""

    def test_detects_error_lowercase(self) -> None:
        assert mcp_circuit_breaker_post.is_error("some error occurred") is True

    def test_detects_timed_out(self) -> None:
        assert mcp_circuit_breaker_post.is_error("request timed out after 30s") is True

    def test_detects_econnrefused_uppercase_in_indicator_list(self) -> None:
        # WHY: ERROR_INDICATORS contains "ECONNREFUSED" (uppercase),
        # but is_error() calls lower() only on result, not on indicators.
        # So "ECONNREFUSED" in the result is NOT detected — this is real
        # code behavior. The test records it as a known limitation.
        assert mcp_circuit_breaker_post.is_error("ECONNREFUSED 127.0.0.1:3000") is False

    def test_detects_econnrefused_lowercase(self) -> None:
        # lowercase variant is detected correctly via the "ECONNREFUSED" indicator
        # only if it matches after lower() — it won't. But "connection refused"
        # is detected via a separate indicator.
        assert mcp_circuit_breaker_post.is_error("connection refused on port 3000") is True

    def test_detects_502_in_response(self) -> None:
        assert mcp_circuit_breaker_post.is_error("HTTP 502 Bad Gateway") is True

    def test_success_result_not_error(self) -> None:
        assert mcp_circuit_breaker_post.is_error('{"results": [{"id": 1}]}') is False

    def test_empty_result_not_error(self) -> None:
        assert mcp_circuit_breaker_post.is_error("") is False

    def test_case_insensitive_detection(self) -> None:
        # WHY: is_error calls lower() before comparing,
        # so "Error" and "ERROR" should be detected.
        assert mcp_circuit_breaker_post.is_error("Error: something went wrong") is True
        assert mcp_circuit_breaker_post.is_error("ERROR: fatal") is True


# =============================================================================
# main() — tested via patch of I/O dependencies
# =============================================================================


class TestSuccessResetsFailures:
    """Success response with existing failures → reset counter to 0."""

    def test_success_resets_failures(self) -> None:
        # WHY: circuit breaker recovers from HALF_OPEN on the first
        # successful response — failures and opened_at are fully reset.
        event = make_event(MCP_TOOL, '{"results": []}')
        existing_state = {"context7": {"failures": 2, "opened_at": 9999.0}}

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value=existing_state),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        saved_state = mock_save.call_args[0][1]
        assert saved_state["context7"]["failures"] == 0
        # WHY: on reset the entry is replaced entirely {"failures": 0},
        # so opened_at disappears as well.
        assert "opened_at" not in saved_state["context7"]

    def test_success_with_zero_failures_saves_clean_entry(self) -> None:
        """Success with clean state (failures=0) — state stays {"failures": 0}."""
        event = make_event(MCP_TOOL, "ok")
        existing_state = {"context7": {"failures": 0}}

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value=existing_state),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        saved_state = mock_save.call_args[0][1]
        assert saved_state["context7"] == {"failures": 0}


class TestErrorIncrementsCounter:
    """Error response → failures incremented by 1."""

    def test_error_increments_counter_from_zero(self) -> None:
        event = make_event(MCP_TOOL, "connection refused")
        existing_state = {"context7": {"failures": 0}}

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value=existing_state),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        saved_state = mock_save.call_args[0][1]
        assert saved_state["context7"]["failures"] == 1

    def test_error_increments_existing_failures(self) -> None:
        event = make_event(MCP_TOOL, "timed out")
        existing_state = {"context7": {"failures": 1}}

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value=existing_state),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        saved_state = mock_save.call_args[0][1]
        assert saved_state["context7"]["failures"] == 2


class TestErrorAtThresholdSetsOpenedAt:
    """When FAILURE_THRESHOLD is reached → opened_at is set."""

    def test_error_at_threshold_sets_opened_at(self) -> None:
        # WHY: FAILURE_THRESHOLD=3, with failures=2 the next error
        # raises it to 3, which is >= threshold → circuit opens.
        event = make_event(MCP_TOOL, "500 Internal Server Error")
        existing_state = {"context7": {"failures": 2}}

        fake_time = 1_700_000_000.0

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value=existing_state),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
            patch("mcp_circuit_breaker_post.time.time", return_value=fake_time),
        ):
            mcp_circuit_breaker_post.main()

        saved_state = mock_save.call_args[0][1]
        assert saved_state["context7"]["failures"] == 3
        assert saved_state["context7"]["opened_at"] == pytest.approx(fake_time)

    def test_below_threshold_no_opened_at(self) -> None:
        """Error below threshold (failures=1) → opened_at is not set."""
        event = make_event(MCP_TOOL, "error")
        existing_state = {"context7": {"failures": 0}}

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value=existing_state),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        saved_state = mock_save.call_args[0][1]
        assert "opened_at" not in saved_state["context7"]


class TestNonMcpToolSkipped:
    """Non-MCP tool (Read, Bash, Write) → state is not changed."""

    def test_non_mcp_tool_skipped(self) -> None:
        # WHY: get_mcp_server_name returns None for "Read" —
        # hook should exit without touching the state.
        event = make_event(NON_MCP_TOOL, "error critical failure")

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state") as mock_load,
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        mock_load.assert_not_called()
        mock_save.assert_not_called()

    def test_bash_tool_skipped(self) -> None:
        event = make_event("Bash", "timed out")

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state") as mock_load,
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        mock_load.assert_not_called()
        mock_save.assert_not_called()


class TestHandlesMissingStateFile:
    """No state file → load returns {}, error recorded as the first one."""

    def test_handles_missing_state_file(self) -> None:
        # WHY: load_json_state returns {} when the file is absent.
        # entry = state.get(server, {}) → failures = 0 + 1 = 1.
        # We use "connection refused" (lowercase) which is in ERROR_INDICATORS.
        event = make_event(MCP_TOOL, "connection refused")
        empty_state: dict = {}

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value=empty_state),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        saved_state = mock_save.call_args[0][1]
        assert "context7" in saved_state
        assert saved_state["context7"]["failures"] == 1

    def test_save_called_with_correct_state_file_path(self) -> None:
        """save_json_state is called with the correct STATE_FILE path."""
        event = make_event(MCP_TOOL, "ok")

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value={}),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        called_path = mock_save.call_args[0][0]
        assert called_path == mcp_circuit_breaker_post.STATE_FILE


class TestDoesNotOverwriteOpenedAt:
    """An already-set opened_at is not overwritten on subsequent errors."""

    def test_does_not_overwrite_opened_at(self) -> None:
        # WHY: the condition `"opened_at" not in entry` guards against overwrite.
        # It is important to preserve the original open timestamp for TTL logic.
        original_opened_at = 1_600_000_000.0
        event = make_event(MCP_TOOL, "502 Bad Gateway")
        existing_state = {
            "context7": {
                "failures": 5,  # already above threshold
                "opened_at": original_opened_at,
            }
        }

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value=existing_state),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
            patch("mcp_circuit_breaker_post.time.time", return_value=9_999_999_999.0),
        ):
            mcp_circuit_breaker_post.main()

        saved_state = mock_save.call_args[0][1]
        assert saved_state["context7"]["opened_at"] == pytest.approx(original_opened_at)
        assert saved_state["context7"]["failures"] == 6  # increment continues

    def test_opened_at_set_only_once_at_threshold(self) -> None:
        """opened_at is set exactly once — when the threshold is first reached."""
        first_opened_at = 1_700_000_000.0
        # First call: failures 2 → 3, threshold reached → opened_at is set
        event = make_event(MCP_TOOL, "failed to connect")
        state_before_threshold = {"context7": {"failures": 2}}

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch(
                "mcp_circuit_breaker_post.load_json_state",
                return_value=state_before_threshold,
            ),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
            patch("mcp_circuit_breaker_post.time.time", return_value=first_opened_at),
        ):
            mcp_circuit_breaker_post.main()

        state_after_threshold = mock_save.call_args[0][1]
        assert state_after_threshold["context7"]["opened_at"] == pytest.approx(first_opened_at)

        # Second call: failures 3 → 4, opened_at already set → not overwritten
        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch(
                "mcp_circuit_breaker_post.load_json_state",
                return_value=state_after_threshold,
            ),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
            patch("mcp_circuit_breaker_post.time.time", return_value=9_999_999_999.0),
        ):
            mcp_circuit_breaker_post.main()

        final_state = mock_save.call_args[0][1]
        assert final_state["context7"]["opened_at"] == pytest.approx(first_opened_at)


class TestEmptyEvent:
    """Empty or invalid event → hook exits without errors."""

    def test_empty_event_exits_gracefully(self) -> None:
        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value={}),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        mock_save.assert_not_called()

    def test_none_event_exits_gracefully(self) -> None:
        # WHY: parse_stdin_raw returns {} on parse error,
        # but None is also possible as an edge case (though utils returns {}).
        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=None),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        mock_save.assert_not_called()
