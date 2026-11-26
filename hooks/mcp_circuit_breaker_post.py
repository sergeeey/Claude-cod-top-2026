#!/usr/bin/env python3
"""
MCP Circuit Breaker — PostToolUse hook (claude-code-config).

Records MCP call result: success → reset counter, error → increment.
Works in pair with mcp_circuit_breaker.py (PreToolUse).
"""

import json
import re
import sys
import time

from lib.runtime import get_mcp_server_name, parse_stdin_raw
from lib.state import CB_FAILURE_THRESHOLD as FAILURE_THRESHOLD
from lib.state import CB_STATE_FILE as STATE_FILE
from lib.state import file_lock, load_json_state, save_json_state

# WHY the same lock path as mcp_circuit_breaker.py (Pre hook): both processes
# read-modify-write the SAME state file, so they must contend for the SAME
# lock, not two independent ones.
_LOCK_FILE = STATE_FILE.with_suffix(".lock")

# WHY: substring "500" / "error" appear in normal API responses (docs, status tables,
# error-handling examples). We use structured JSON check first, then anchored regex
# patterns for connection errors only — never bare status codes or the word "error".
_CONNECTION_ERROR_RE = re.compile(
    r"\b(ECONNREFUSED|ETIMEDOUT|ENOTFOUND|connection refused|failed to connect|timed out)\b",
    re.IGNORECASE,
)
# WHY: require "HTTP" prefix to avoid matching bare "500" inside response content.
_HTTP_ERROR_RE = re.compile(r"\bHTTP\s+(5\d{2})\b", re.IGNORECASE)


def is_error(result: str) -> bool:
    """Detect MCP tool errors without false-positives on normal response content.

    WHY: bare substring "error" or "500" appear in legitimate responses
    (API docs, status tables, error handling examples). We require:
    1. Structured error field in parsed JSON, OR
    2. Connection-level error keywords as whole words, OR
    3. HTTP 5xx status codes preceded by "HTTP" keyword.
    """
    # 1. Try structured parse first — Claude Code hook result has "error" key on failure.
    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict):
            if parsed.get("error") or parsed.get("isError"):
                return True
            status = parsed.get("status_code") or parsed.get("statusCode")
            if status and int(status) >= 500:
                return True
            return False
    except (json.JSONDecodeError, ValueError, TypeError):
        pass  # not JSON — fall through to regex

    # 2. Connection-level errors as whole words (case-insensitive).
    if _CONNECTION_ERROR_RE.search(result):
        return True

    # 3. HTTP 5xx with "HTTP" prefix to avoid matching bare "500" in content.
    if _HTTP_ERROR_RE.search(result):
        return True

    return False


def main() -> None:
    event = parse_stdin_raw()
    if not event:
        return

    tool_name: str = event.get("tool_name", "")
    server = get_mcp_server_name(tool_name)
    if server is None:
        return

    # WHY the event name decides, not the text of the response (found 2026-11-26, Claude Code hooks
    # reference): PostToolUse fires only when a call SUCCEEDS; a failed call, including an MCP error
    # result, fires PostToolUseFailure with an `error` string. The earlier code scanned successful
    # responses for error patterns, so healthy answers that quoted "timed out" could open the
    # circuit.
    # is_interrupt is an abort by the user, not a server failure, so it is not counted.
    hook_event = event.get("hook_event_name", "PostToolUse")
    interrupted = hook_event == "PostToolUseFailure" and bool(event.get("is_interrupt"))
    error = hook_event == "PostToolUseFailure" and not interrupted
    # WHY the call's id (see the late-result check below): lets a result from an earlier call be
    # told apart from the result of the probe that is in flight now.
    tool_use_id = str(event.get("tool_use_id", "") or "")

    # WHY the whole read-modify-write under one lock: without it, two
    # concurrent failing calls to the same server both load_json_state()
    # before either writes, both increment their own local copy of
    # `failures` from the same starting number, and the last save_json_state()
    # wins -- silently losing one increment and delaying (or missing) the
    # point where the circuit should actually open.
    #
    # WHY `as acquired` + explicit check (fixed 2026-09-01, found via
    # test_circuit_breaker_lock_race.py failing on CI under 20-thread load):
    # a bare `with file_lock(_LOCK_FILE):` still ENTERS the block even when
    # the lock timed out (yields False) -- this was the one caller among 17
    # in this repo that skipped the check every other file_lock() caller
    # applies (see hooks/lib/state.py's own file_lock docstring). Under real
    # contention two threads both proceeded unlocked, raced on the same
    # PID-suffixed tmp file inside atomic_write_json, and one lost its
    # increment (assert 19 == 20). `timeout=15.0` matches every other
    # file_lock() call site in this repo -- the previous 2.0s default was an
    # unrelated outlier, not a deliberate choice for this hook.
    with file_lock(_LOCK_FILE, timeout=15.0) as acquired:
        if not acquired:
            # Fail-safe, not fail-crash: this is a PostToolUse hook, so
            # raising here would surface as an unhandled-exception crash
            # (hooks/CLAUDE.md "never raise unhandled exceptions"). Skipping
            # the update under sustained lock contention loses at most one
            # increment -- worse than the lock working, but far better than
            # crashing the hook outright.
            print(
                f"[circuit-breaker] {server}: lock timeout, skipping state update",
                file=sys.stderr,
            )
            return
        state = load_json_state(STATE_FILE)
        entry = state.get(server, {})

        # WHY (owner review 2026-11-26): a call granted BEFORE the circuit opened, or a probe that
        # was given up as lost, can report after a newer probe was granted. Its result says nothing
        # about the newer probe, so it must not clear the newer probe's flags or move failures.
        probe_id = entry.get("probe_id", "")
        if entry.get("probe_in_flight") and tool_use_id and probe_id and tool_use_id != probe_id:
            print(
                f"[circuit-breaker] {server}: late result of an earlier call ignored",
                file=sys.stderr,
            )
            return

        if interrupted:
            # WHY: a user abort is not a server failure, so failures do not move. But if the
            # aborted call was the probe, release it now instead of leaving the server blocked
            # until the probe goes stale.
            if entry.get("probe_in_flight") and tool_use_id and tool_use_id == probe_id:
                entry.pop("probe_in_flight", None)
                entry.pop("probe_started_at", None)
                entry.pop("probe_id", None)
                # WHY opened_at is set again: the grant removed it, and OPEN without opened_at never
                # reaches HALF_OPEN, which would block the server forever (the original defect).
                # Restarting the window gives the next probe a full recovery timeout.
                entry["opened_at"] = time.time()
                state[server] = entry
                save_json_state(STATE_FILE, state)
            return

        if error:
            # Increment failures, at threshold — record opened_at
            failures = entry.get("failures", 0) + 1
            entry["failures"] = failures
            # WHY: clear probe_in_flight before re-opening, so the next
            # PreToolUse sees a clean OPEN state (not a stale in-flight probe).
            entry.pop("probe_in_flight", None)
            entry.pop("probe_started_at", None)
            entry.pop("probe_id", None)
            if failures >= FAILURE_THRESHOLD and "opened_at" not in entry:
                entry["opened_at"] = time.time()
                print(
                    f"[circuit-breaker] {server}: OPEN after {failures} failures",
                    file=sys.stderr,
                )
        else:
            # Success — full reset (recovery from HALF_OPEN or normal CLOSED call)
            if entry.get("failures", 0) > 0:
                print(
                    f"[circuit-breaker] {server}: recovered, resetting",
                    file=sys.stderr,
                )
            # WHY: reset failures to 0 and clear both probe flags.
            # failures=0 ensures get_circuit_status returns CLOSED immediately.
            # probe_in_flight must be cleared or the next PreToolUse will block
            # even though the circuit is now healthy.
            entry = {"failures": 0}

        state[server] = entry
        save_json_state(STATE_FILE, state)


if __name__ == "__main__":
    main()
