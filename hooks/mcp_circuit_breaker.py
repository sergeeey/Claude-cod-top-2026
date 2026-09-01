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
import sys
import time

from utils import (
    CB_FAILURE_THRESHOLD as FAILURE_THRESHOLD,
)
from utils import (
    CB_RECOVERY_TIMEOUT as RECOVERY_TIMEOUT,
)
from utils import (
    CB_STATE_FILE as STATE_FILE,
)
from utils import (
    file_lock,
    get_mcp_server_name,
    load_json_state,
    parse_stdin_raw,
    save_json_state,
)

# WHY a dedicated .lock path, not STATE_FILE itself: the lock is a sentinel
# file (created/deleted per file_lock()'s O_CREAT|O_EXCL protocol), separate
# from the actual JSON state content.
_LOCK_FILE = STATE_FILE.with_suffix(".lock")

# --- Configuration -----------------------------------------------------------

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
    """Record a failure for *server* and open the circuit if threshold is reached.

    WHY: This function exists as a pure, testable utility for unit tests
    (tests/test_circuit_breaker.py). The production path in mcp_circuit_breaker_post.py
    inlines this logic to avoid a shared-state import dependency between pre/post hooks.
    Do NOT remove — tests depend on it.
    """
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
        # WHY: probe_in_flight prevents concurrent HALF_OPEN probes. The
        # check-then-set below must happen under a lock, not just as a flag
        # -- without the lock, two simultaneous PreToolUse calls can both
        # load_json_state() BEFORE either writes, both see probe_in_flight
        # absent, and both set it and let their calls through, defeating the
        # single-probe intent despite the flag existing.
        # WHY `as acquired` + explicit check (fixed 2026-09-01, sibling fix
        # to mcp_circuit_breaker_post.py -- same bare `with file_lock(...):`
        # bug, same shared _LOCK_FILE): a timed-out lock must not silently
        # let this PreToolUse hook proceed as if it held it. `timeout=15.0`
        # matches every other file_lock() call site in this repo.
        with file_lock(_LOCK_FILE, timeout=15.0) as acquired:
            if not acquired:
                # Fail-open, not fail-crash: this hook is ungated by
                # hook_main (see bottom of file), so raising here would be
                # an unhandled-exception crash. Allowing the call through
                # under sustained contention risks a duplicate HALF_OPEN
                # probe -- a lesser failure than blocking every tool call
                # whenever the lock is briefly contended.
                print(
                    f"[circuit-breaker] {server}: lock timeout, allowing call through",
                    file=sys.stderr,
                )
                print("{}")
                return
            # WHY re-read here, not reuse the outer `state`/`entry`: another
            # process may have updated the file between our first
            # load_json_state() above and acquiring this lock.
            state = load_json_state(STATE_FILE)
            entry = state.get(server, {})

            if entry.get("probe_in_flight"):
                fallback = FALLBACKS.get(server, DEFAULT_FALLBACK)
                result = {
                    "decision": "block",
                    "reason": f"MCP circuit OPEN for '{server}': probe already in flight. "
                    f"Fallback: {fallback}",
                }
                print(json.dumps(result))
                return

            entry.pop("opened_at", None)
            # WHY: failures is NOT reset here — PostToolUse resets to 0 on success.
            # Resetting here would allow a second probe even if this one fails,
            # because get_circuit_status would see failures < threshold → CLOSED.
            entry["probe_in_flight"] = True
            state[server] = entry
            save_json_state(STATE_FILE, state)

    # CLOSED or HALF_OPEN — allow the call
    print("{}")


if __name__ == "__main__":
    main()
