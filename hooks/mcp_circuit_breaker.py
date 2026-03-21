"""
MCP Circuit Breaker — PreToolUse hook (claude-code-config).

Implements the Circuit Breaker pattern for MCP servers: on repeated failures
the server is temporarily blocked and Claude receives a fallback suggestion.

States:
  CLOSED    — normal operation
  OPEN      — blocked after N failures (server is not called)
  HALF_OPEN — test pass-through after recovery timeout
"""

import json
import time
from pathlib import Path

from utils import get_mcp_server_name, load_json_state, parse_stdin_raw, save_json_state

# --- Configuration -----------------------------------------------------------

FAILURE_THRESHOLD = 3
RECOVERY_TIMEOUT = 60  # seconds
STATE_FILE = Path.home() / ".claude" / "cache" / "mcp_circuit_state.json"

# WHY: fallback strings are stored here, not in external config —
# the hook must work without dependencies in any MCP state
FALLBACKS: dict[str, str] = {
    "context7": "Use WebSearch or WebFetch for documentation",
    "playwright": "Use WebFetch for static content",
    "basic-memory": "Use Read/Write for file-based memory",
    "ollama": "Skip local inference, use cloud model",
}
DEFAULT_FALLBACK = "Try alternative approach"


# --- Circuit Breaker Logic -------------------------------------------------


def get_circuit_status(entry: dict) -> str:
    """Determines the current circuit state for a specific server."""
    failures = entry.get("failures", 0)
    opened_at = entry.get("opened_at")

    if failures < FAILURE_THRESHOLD:
        return "CLOSED"

    if opened_at and (time.time() - opened_at) >= RECOVERY_TIMEOUT:
        # WHY: HALF_OPEN allows one request through to check
        # server recovery without fully resetting the counter
        return "HALF_OPEN"

    return "OPEN"


def record_open(state: dict, server: str) -> dict:
    """Transitions the server circuit to OPEN state, recording block time."""
    entry = state.get(server, {})
    entry["failures"] = entry.get("failures", 0) + 1
    if entry["failures"] >= FAILURE_THRESHOLD and "opened_at" not in entry:
        entry["opened_at"] = time.time()
    state[server] = entry
    return state


# --- Entry point ------------------------------------------------------------


def main() -> None:
    """Handles PreToolUse event from Claude Code."""
    event = parse_stdin_raw()
    if not event:
        # Cannot parse input — pass through without blocking
        print("{}")
        return

    tool_name: str = event.get("tool_name", "")
    server = get_mcp_server_name(tool_name)

    if server is None:
        # Not an MCP tool — circuit breaker does not apply
        print("{}")
        return

    state = load_json_state(STATE_FILE)
    entry = state.get(server, {})
    status = get_circuit_status(entry)

    if status == "OPEN":
        fallback = FALLBACKS.get(server, DEFAULT_FALLBACK)
        result = {
            "decision": "block",
            "reason": f"Circuit OPEN for '{server}' ({entry.get('failures', 0)} failures). "
            f"Fallback: {fallback}",
        }
        print(json.dumps(result))
        return

    if status == "HALF_OPEN":
        # WHY: reset opened_at to give one chance — if it fails
        # again, PreToolUse will re-record opened_at on the next call
        entry.pop("opened_at", None)
        state[server] = entry
        save_json_state(STATE_FILE, state)

    # CLOSED or HALF_OPEN — allow the call
    print("{}")


if __name__ == "__main__":
    main()
