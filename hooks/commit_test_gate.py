#!/usr/bin/env python3
"""Guard: warn at commit, and block Stop, when source changed after the last
test run.

WHY: The anti-cheating rule "never claim tests pass without running them" needs
state — you can't detect it from a single tool call. This hook tracks two
timestamps per project and warns at git commit if source .py was edited AFTER
the last pytest run (i.e. the change was never actually tested).

Closes gap #3 of the self-fix hardening plan. Commit warning is a soft nudge
(never blocks); the Stop check is a REAL block (exit code 2), see below.

Registered on FOUR events (one file, mode-dispatched):
  PostToolUse(Bash)        — if `pytest` ran → stamp last_test
  PostToolUse(Edit|Write)  — if source .py changed → stamp last_edit
  PreToolUse(Bash)         — if `git commit` → warn when last_edit > last_test
  Stop                     — block the turn from ending when last_edit > last_test

WHY the Stop check blocks but the commit check only warns (2026-08-28,
survivorship-bias review of "tests passed" claims -- see
experiments/20260824-elai-hooks-skeptic-pilot/ and
experiments/20260824-permission-policy-skeptic-pilot/ for the pattern this
generalizes: every bug in those two pilots was independently reproduced with
a real command, never accepted on an agent's/session's own say-so): the
commit gate has an escape hatch (the user can commit anyway after reading the
warning), but "claimed done without ever running the tests" is exactly the
failure mode this file exists to prevent, and a warning is easy to skim past
at the moment a turn ends. `Stop` is registered UNWRAPPED (not through
async_wrapper.py, unlike this same event's other hooks in settings.json) --
per hooks/CLAUDE.md's own warning, async_wrapper backgrounds the process, so
its exit code would never reach Claude Code synchronously and the block
would silently do nothing.

WHY a bounded retry cap (_MAX_CONSECUTIVE_STOP_BLOCKS), not an unconditional
block: this repo's own docs (fetched from code.claude.com/docs/en/hooks,
2026-08-28) confirm exit-code-2 on Stop "continues the conversation" but
document no built-in loop-prevention field (no `stop_hook_active` equivalent
was found in the fetched schema) -- an unconditional block risks an infinite
loop if a change genuinely doesn't need re-testing (e.g. `_is_source_py`'s
own definition is a heuristic, not a proof). Capped at 2 consecutive blocks
per this repo's existing "Stuck Detection" convention (CLAUDE.md's 4-tier
recovery, max depth 3 attempts per tier) -- fail OPEN (let the stop proceed)
after the cap, never fail closed into an unbreakable loop. The PreToolUse
commit-time warning remains as an independent, unrelated backstop.

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


def _is_stop_event(data: dict) -> bool:
    """WHY both cases: hook_observability.py already established the
    defensive pattern of checking both snake_case (documented) and
    camelCase (seen in practice) forms of this field."""
    return data.get("hook_event_name") == "Stop" or data.get("hookEventName") == "Stop"


# WHY 2, not higher: gives Claude one real chance to see the block and run
# tests, plus one more in case the first attempt's test run itself failed or
# was interrupted -- then fails open rather than risk an unbounded loop. See
# module docstring for why no confirmed platform-level loop-prevention field
# exists to lean on instead.
_MAX_CONSECUTIVE_STOP_BLOCKS = 2


def _handle_stop(data: dict) -> None:  # noqa: ARG001 -- data reserved for future use
    """Block the turn from ending if source .py changed since the last
    passing pytest run this session. Exits 2 (blocks, per
    code.claude.com/docs/en/hooks' documented exit-code-2 behavior for Stop)
    with the reason on stderr, or 0 (allows) otherwise."""
    state = HookState("commit_test_gate")
    if not _should_warn(state):
        if state.get("stop_blocks"):
            state["stop_blocks"] = 0
            state.save()
        sys.exit(0)

    blocks = int(str(state.get("stop_blocks", 0))) + 1
    if blocks > _MAX_CONSECUTIVE_STOP_BLOCKS:
        # WHY reset, not stamp last_test: failing open here is honest about
        # NOT having verified the tests -- it must never look like a real
        # test run happened. The independent commit-time warning below still
        # fires if this session's changes are later committed untested.
        state["stop_blocks"] = 0
        state.save()
        sys.exit(0)

    state["stop_blocks"] = blocks
    state.save()
    print(
        "[commit-test-gate] Source .py changed since the last passing pytest run "
        "this session -- run the tests before finishing this turn. "
        "'Tests pass' without a real run is not evidence "
        f"(attempt {blocks}/{_MAX_CONSECUTIVE_STOP_BLOCKS}, then this will not block again).",
        file=sys.stderr,
    )
    sys.exit(2)


def main() -> None:
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    if _is_stop_event(data):
        # WHY not hooks/lib/runtime.py's hook_main(fail_closed=True) (Gate
        # 12a's own recipe, 2026-08-28): that function's fail-closed path is
        # hardcoded to emit_permission_decision(decision="deny", ...) -- the
        # PreToolUse JSON protocol. For a Stop event that JSON is meaningless
        # (Stop blocks via exit code 2 + stderr, per this module's docstring),
        # and hook_main() would still os._exit(0) afterward -- an unhandled
        # crash would silently become an ALLOW, exactly the failure mode
        # Gate 12a exists to prevent, just via the wrong mechanism for this
        # event type. Fails closed natively instead: exit 2 + stderr, the
        # one thing Stop actually understands. No timeout wrapper (unlike
        # hook_main's threaded guard) because _handle_stop only does local
        # JSON-state-file I/O -- no network/subprocess call exists here that
        # could plausibly hang.
        try:
            _handle_stop(data)
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001 -- must fail closed on ANY crash, not just expected ones
            print(
                f"[commit-test-gate] Stop handler crashed ({e}) -- failing closed.",
                file=sys.stderr,
            )
            sys.exit(2)
        return

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
