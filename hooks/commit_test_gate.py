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
import shlex
import sys
import time
from pathlib import Path

from hook_state import HookState

_COLLECT_ONLY_RE = re.compile(r"--co\b|--collect-only\b")
_COMMIT_RE = re.compile(r"\bgit\s+commit\b")

# WHY (cross-model audit, hooks-02 MEDIUM): the old check was a bare
# `\bpytest\b` substring search over the WHOLE command string, so
# `echo pytest` or a heredoc whose body merely mentions the word "pytest"
# (e.g. a report template) counted as a real test run and suppressed the
# "tests didn't pass" warning. Detection now requires "pytest" to be the
# actual COMMAND of a statement (directly, via a path like .venv/bin/pytest,
# or via `python -m pytest`) -- not merely present as text anywhere.
_HEREDOC_START_RE = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")
_CHAIN_SPLIT_RE = re.compile(r"&&|\|\||[;&|]")
_PYTHON_EXE_RE = re.compile(r"^python3?(\.\d+)?$")


def _split_statements(cmd: str) -> list[str]:
    """Split into shell statements at ;, &, |, and newline -- EXCEPT inside a
    heredoc body, which is opaque data, not further statements. Without this,
    a heredoc body LINE that happens to start with the bare word "pytest"
    would be mis-tokenized as a real pytest invocation, while a genuine
    multi-line script with no explicit `&&` between lines (bash runs each
    line in sequence regardless) needs the newline split to detect a real
    run on a later line."""
    statements: list[str] = []
    buf: list[str] = []
    heredoc_terminator: str | None = None
    for line in cmd.split("\n"):
        if heredoc_terminator is not None:
            buf.append(line)
            if line.strip() == heredoc_terminator:
                statements.append("\n".join(buf))
                buf = []
                heredoc_terminator = None
            continue
        heredoc_match = _HEREDOC_START_RE.search(line)
        if heredoc_match:
            heredoc_terminator = heredoc_match.group(1)
            buf = [line]
            continue
        statements.extend(s for s in _CHAIN_SPLIT_RE.split(line) if s.strip())
    if buf:  # unterminated heredoc at EOF -- flush what we have rather than drop it
        statements.append("\n".join(buf))
    return statements


def _statement_tokens(statement: str) -> list[str]:
    try:
        return shlex.split(statement, posix=True)
    except ValueError:
        return statement.split()


def _is_pytest(cmd: str) -> bool:
    """A real test run — pytest invoked as the actual command of a statement,
    not merely mentioned as text (echo/printf/heredoc body). Excludes
    collect-only dry runs."""
    for statement in _split_statements(cmd):
        if _COLLECT_ONLY_RE.search(statement):
            continue
        tokens = _statement_tokens(statement)
        if not tokens:
            continue
        first = tokens[0]
        if first == "pytest" or first.endswith(("/pytest", "\\pytest", "/pytest.exe")):
            return True
        if (
            len(tokens) >= 3
            and _PYTHON_EXE_RE.fullmatch(first)
            and tokens[1] == "-m"
            and tokens[2] == "pytest"
        ):
            return True
    return False


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


def _exit_code(tool_response: dict) -> int:
    """Same convention used across this repo's hooks (auto_capture.py,
    learning_tracker.py): exit_code, falling back to returncode, defaulting
    to 0 (success) when the harness doesn't populate either field."""
    return tool_response.get("exit_code", tool_response.get("returncode", 0)) or 0


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
        # WHY exit-code gate (HIGH, cross-model audit): a FAILED pytest run
        # previously still stamped last_test, so a later commit avoided the
        # "tests didn't pass" warning even though tests genuinely failed --
        # the whole point of this hook is defeated by its own success path.
        if is_post and _is_pytest(cmd) and _exit_code(data.get("tool_response", {})) == 0:
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

    # WHY include MultiEdit (MEDIUM, cross-model audit): source edits made
    # through a MultiEdit PostToolUse event previously weren't stamped at
    # all, since only Edit/Write were handled -- MultiEdit carries the same
    # single-target `file_path` field as Edit/Write, just with multiple
    # old/new_string pairs applied atomically.
    if is_post and tool in ("Edit", "Write", "MultiEdit"):
        if _is_source_py(tool_input.get("file_path", "")):
            state = HookState("commit_test_gate")
            state["last_edit"] = now
            state.save()
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
