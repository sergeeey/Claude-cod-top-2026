#!/usr/bin/env python3
"""Guard: warn at commit when source changed after the last test run.

WHY: The anti-cheating rule "never claim tests pass without running them" needs
state — you can't detect it from a single tool call. This hook tracks two
timestamps per project and warns at git commit if source .py was edited AFTER
the last pytest run (i.e. the change was never actually tested).

Closes gap #3 of the self-fix hardening plan. Soft nudge (never blocks).

Registered on THREE events (one file, mode-dispatched):
  PostToolUse(Bash)        — if `pytest` ran → stamp last_test
  PostToolUse(Edit|Write)  — if source .py changed → stamp last_edit
  PreToolUse(Bash)         — if `git commit` → warn when last_edit > last_test

State: <cwd>/.claude/state/commit_test_gate.json
"""

import json
import os
import re
import sys
import time
from pathlib import Path

from hook_state import HookState

_PYTEST_RE = re.compile(r"\bpytest\b")
_COLLECT_ONLY_RE = re.compile(r"--co\b|--collect-only\b")
_COMMIT_RE = re.compile(r"\bgit\s+commit\b")


def _is_pytest(cmd: str) -> bool:
    """A real test run — pytest invoked, not a collect-only dry run."""
    return bool(_PYTEST_RE.search(cmd)) and not _COLLECT_ONLY_RE.search(cmd)


def _is_commit(cmd: str) -> bool:
    return bool(_COMMIT_RE.search(cmd))


def _is_source_py(file_path: str) -> bool:
    """Python source file that should be covered by tests (not a test itself)."""
    p = Path(file_path)
    if p.suffix != ".py":
        return False
    if p.name.startswith("test_") or p.stem.endswith("_test"):
        return False
    return "tests" not in set(p.parts)


def _should_warn(state: HookState) -> bool:
    """True if source was edited after the last test run (or never tested)."""
    last_edit = float(str(state.get("last_edit", 0)))
    last_test = float(str(state.get("last_test", 0)))
    return last_edit > last_test


def main() -> None:
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    # WHY: PostToolUse carries tool_response; PreToolUse does not. Use it to
    # distinguish the "stamp" events (post) from the "check" event (pre).
    is_post = "tool_response" in data
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    now = time.time()

    if tool == "Bash":
        cmd = tool_input.get("command", "")
        if is_post and _is_pytest(cmd):
            state = HookState("commit_test_gate")
            state["last_test"] = now
            state.save()
            sys.exit(0)
        if not is_post and _is_commit(cmd):
            state = HookState("commit_test_gate")
            if _should_warn(state):
                msg = (
                    "[commit-test-gate] ⚠️  Source .py changed since the last pytest run — "
                    "this commit may contain untested changes.\n"
                    "→ Run the tests and show the output before committing. "
                    "'Tests pass' without a real run is not evidence."
                )
                print(
                    json.dumps(
                        {
                            "hookSpecificOutput": {
                                "hookEventName": "PreToolUse",
                                "additionalContext": msg,
                            }
                        }
                    )
                )
            sys.exit(0)
        sys.exit(0)

    if is_post and tool in ("Edit", "Write"):
        if _is_source_py(tool_input.get("file_path", "")):
            state = HookState("commit_test_gate")
            state["last_edit"] = now
            state.save()
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
