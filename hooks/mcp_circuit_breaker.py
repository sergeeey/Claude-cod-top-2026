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

from lib.runtime import get_mcp_server_name, parse_stdin_raw
from lib.state import CB_FAILURE_THRESHOLD as FAILURE_THRESHOLD
from lib.state import CB_RECOVERY_TIMEOUT as RECOVERY_TIMEOUT
from lib.state import CB_STATE_FILE as STATE_FILE
from lib.state import file_lock, load_json_state, save_json_state

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

# WHY: how many replaced probe ids are remembered per server (see the superseded list in the grant).
SUPERSEDED_KEEP = 8


# --- Circuit Breaker Logic -------------------------------------------------


def probe_is_stale(entry: dict) -> bool:
    """True when a HALF_OPEN probe was granted long enough ago that its PostToolUse is lost.

    WHY (found 2026-11-26): the probe is granted by popping `opened_at` and setting
    `probe_in_flight`. Only mcp_circuit_breaker_post.py clears that flag. If the probe call is
    interrupted or its post hook never runs, the flag stays set and the server is blocked forever,
    because OPEN without `opened_at` never reaches HALF_OPEN. A probe older than RECOVERY_TIMEOUT
    is treated as lost. State written before `probe_started_at` existed has no timestamp, so it is
    treated as lost too and heals on its next call.
    """
    started = entry.get("probe_started_at")
    if not isinstance(started, (int, float)):
        return True
    return (time.time() - started) >= RECOVERY_TIMEOUT


def get_circuit_status(entry: dict) -> str:
    """Determines the current circuit state for a specific server."""
    failures = entry.get("failures", 0)
    opened_at = entry.get("opened_at")

    if failures < FAILURE_THRESHOLD:
        return "CLOSED"

    if entry.get("probe_in_flight"):
        # A fresh probe keeps the other calls out; a lost one must not.
        return "HALF_OPEN" if probe_is_stale(entry) else "OPEN"

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

            if entry.get("probe_in_flight") and not probe_is_stale(entry):
                fallback = FALLBACKS.get(server, DEFAULT_FALLBACK)
                result = {
                    "decision": "block",
                    "reason": f"MCP circuit OPEN for '{server}': probe already in flight. "
                    f"Fallback: {fallback}",
                }
                print(json.dumps(result))
                return

            entry.pop("opened_at", None)
            # WHY (Codex P2 on PR #578): when this probe replaces a stale one, the stale probe's id
            # is remembered. Once the replacement resolves, probe_id is cleared, and without this
            # list a late success of the old call would reset the counter and close the circuit.
            if entry.get("probe_in_flight") and entry.get("probe_id"):
                superseded = list(entry.get("superseded", []))
                superseded.append(entry["probe_id"])
                entry["superseded"] = superseded[-SUPERSEDED_KEEP:]
            # WHY: failures is NOT reset here — PostToolUse resets to 0 on success.
            # Resetting here would allow a second probe even if this one fails,
            # because get_circuit_status would see failures < threshold → CLOSED.
            entry["probe_in_flight"] = True
            # WHY: the start time lets a later call tell a live probe from a lost one
            # (see probe_is_stale).
            entry["probe_started_at"] = time.time()
            # WHY: the post hook uses this to recognise this probe's own result and to ignore
            # late results of earlier calls (see mcp_circuit_breaker_post.py).
            entry["probe_id"] = str(event.get("tool_use_id", "") or "") if event else ""
            state[server] = entry
            save_json_state(STATE_FILE, state)

    # CLOSED or HALF_OPEN — allow the call
    print("{}")


if __name__ == "__main__":
    main()
