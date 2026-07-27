#!/usr/bin/env python3
"""PostToolUse hook: capture Edit/Write observations to session log.

WHY: auto_capture.py only captures git commits and test failures.
claude-mem showed that capturing every file modification builds a richer
intra-session picture — so session_save.py has more to work with.

Architecture: appends a single line per operation to a daily session log
in ~/.claude/memory/raw/session-YYYY-MM-DD.md. The session log is
processed by session_save.py at Stop.
"""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from utils import file_lock, hook_main, parse_stdin

# WHY: recursion guard — hooks run inside Agent SDK sub-invocations too
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

RAW_DIR = Path.home() / ".claude" / "memory" / "_auto" / "raw"
MAX_SESSION_LOG_BYTES = 50_000  # WHY: cap at 50KB — larger = noise, not signal


def _get_session_log() -> Path:
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    return RAW_DIR / f"session-{date}.md"


def _ensure_header(log_path: Path) -> None:
    """Create session log with header if it doesn't exist."""
    if log_path.exists():
        return
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    log_path.write_text(
        f"# Session Observations — {date}\n\n"
        f"#raw #session-log #auto-capture\n\n"
        f"**Date:** {date}  \n\n"
        f"---\n\n",
        encoding="utf-8",
    )


def _append_observation(tool_name: str, tool_input: dict, tool_response: dict) -> bool:
    """Append one observation line to today's session log."""
    log_path = _get_session_log()

    # WHY: size guard — if log is already large, stop appending noise
    if log_path.exists() and log_path.stat().st_size > MAX_SESSION_LOG_BYTES:
        return False

    # Extract what's interesting per tool
    if tool_name == "Edit":
        file_path = tool_input.get("file_path", "?")
        old_len = len(tool_input.get("old_string", ""))
        new_len = len(tool_input.get("new_string", ""))
        delta = new_len - old_len
        sign = "+" if delta >= 0 else ""
        observation = f"Edit `{file_path}` ({sign}{delta} chars)"
    elif tool_name == "Write":
        file_path = tool_input.get("file_path", "?")
        content_len = len(tool_input.get("content", ""))
        observation = f"Write `{file_path}` ({content_len} chars)"
    else:
        return False

    # Only log successful operations (exit_code 0 or no exit_code)
    exit_code = tool_response.get("exit_code", 0)
    if isinstance(exit_code, int) and exit_code != 0:
        return False

    ts = datetime.now(UTC).strftime("%H:%M")
    # WHY lock (MEDIUM, cross-model audit): on the FIRST observation of a
    # day, two concurrent hook invocations could both see log_path.exists()
    # == False in _ensure_header() and both call write_text() -- the second
    # header write truncates whatever the first process had already
    # appended. Locking the whole ensure-header+append sequence closes this.
    # WHY timeout=15.0 + acquired-check (real bug, found by a cross-file
    # concurrency test): file_lock()'s default 2.0s timeout yields False
    # rather than raising -- a bare `with file_lock(...):` still enters the
    # block unprotected. Raising here is caught by hook_main()'s outer
    # exception handler (prints to stderr, non-zero exit) rather than
    # silently corrupting the session log.
    lock_path = log_path.with_suffix(".lock")
    with file_lock(lock_path, timeout=15.0) as acquired:
        if not acquired:
            raise TimeoutError(f"Could not acquire observation log lock: {lock_path}")
        _ensure_header(log_path)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"- `{ts}` {observation}\n")

    return True


def main() -> None:
    data = parse_stdin()
    if not data:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    tool_response = data.get("tool_response", {})
    _append_observation(tool_name, tool_input, tool_response)


if __name__ == "__main__":
    hook_main(main)
