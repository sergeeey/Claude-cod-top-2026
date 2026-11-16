#!/usr/bin/env python3
"""PreToolUse hook for Bash: detect risky operations and suggest checkpoint.

WHY: Before major changes (refactoring, migration, deletion) a context
"save point" is needed. If something goes wrong — the checkpoint allows
restoring the understanding of the project state.

Mechanism: hook receives JSON via stdin (like all Claude Code hooks),
checks the command against risky patterns, verifies checkpoint freshness.

FIX 2026-03-08: There was a bug — it read os.environ instead of stdin JSON.
Result: the hook never fired. Fixed.

FIX (HIGH, cross-model audit, hooks-02): this hook fired on PostToolUse, so
a command like `rm -rf ...` had ALREADY RUN by the time the checkpoint
suggestion appeared -- the exact scenario a checkpoint is supposed to
protect against. Moved to PreToolUse. Still a soft, non-blocking SUGGESTION
(emit_hook_result additionalContext), not a permission decision -- it does
not ask/deny, it just now appears before the risk instead of after it.
"""

import json
import os
import re
import tempfile
import time
from pathlib import Path

from lib.discovery import find_file_upward
from lib.git_commands import force_push_reason, git_invocations, invocations, runs_unparsed_shell
from lib.runtime import emit_hook_result, get_tool_input, parse_stdin

# WHY (2026-11-01, real): the checks below used to be plain substrings of the
# command text, so `git merge-base` (contains "git merge"), a `grep "rm -rf"`,
# and a heredoc note that mentioned a force push all raised "risky operation",
# on nearly every command of a session. Risk is now judged on real invocations
# (lib.git_commands); the substring list is kept only as the fallback for
# commands handed to an interpreter that cannot be parsed (`... | bash`).

# WHY: these commands potentially change project state in a way that
# restoring context without a checkpoint would be difficult
RISKY_PATTERNS = [
    "git rebase",
    "git merge",
    "git reset",
    "git checkout main",
    "git checkout master",
    # WHY switch (MEDIUM, cross-model audit): `git switch` is the modern
    # (git 2.23+) equivalent of `git checkout <branch>` and was unmatched.
    "git switch main",
    "git switch master",
    "git branch -D",
    "git push --force",
    "git push -f",
    "rm -rf",
    "drop table",
    "DROP TABLE",
    "migrate",
]

# WHY a dedicated check, not more literal strings in RISKY_PATTERNS (MEDIUM,
# cross-model audit): PowerShell's `Remove-Item -Recurse -Force` is the
# Windows equivalent of `rm -rf` and was completely unmatched -- but its
# flags can appear in either order (`-Recurse -Force` or `-Force -Recurse`),
# abbreviated (`-r`/`-f`), or with `ri` as the Remove-Item alias, so a fixed
# literal phrase would only ever catch one specific spelling.
_REMOVE_ITEM_CMD_RE = re.compile(r"\b(?:remove-item|ri)\b", re.IGNORECASE)
_RECURSE_FLAG_RE = re.compile(r"-r(?:ecurse)?\b", re.IGNORECASE)
_FORCE_FLAG_RE = re.compile(r"-f(?:orce)?\b", re.IGNORECASE)


def _is_risky_powershell_delete(command: str) -> bool:
    return bool(
        _REMOVE_ITEM_CMD_RE.search(command)
        and _RECURSE_FLAG_RE.search(command)
        and _FORCE_FLAG_RE.search(command)
    )


_DROP_TABLE_RE = re.compile(r"\bdrop\s+table\b", re.IGNORECASE)
_PROTECTED_BRANCHES = frozenset({"main", "master"})
_HARD_RESET_FLAGS = frozenset({"--hard", "--merge", "--keep"})


def _is_rm_rf(args: list[str]) -> bool:
    recursive = forced = False
    for arg in args:
        if arg == "--recursive":
            recursive = True
        elif arg == "--force":
            forced = True
        elif arg.startswith("-") and not arg.startswith("--"):
            recursive = recursive or "r" in arg[1:] or "R" in arg[1:]
            forced = forced or "f" in arg[1:]
    return recursive and forced


def _is_risky_git(command: str) -> bool:
    for sub, args in git_invocations(command):
        if sub in ("rebase", "merge"):  # `merge-base` is its own subcommand
            return True
        if sub == "reset" and any(a in _HARD_RESET_FLAGS for a in args):
            return True
        if sub in ("checkout", "switch") and any(a in _PROTECTED_BRANCHES for a in args):
            return True
        if sub == "branch" and "-D" in args:
            return True
        if sub == "push" and force_push_reason(args):
            return True
    return False


def is_risky_command(command: str) -> bool:
    """True when `command` really runs a state-destroying operation.

    Text that only mentions such an operation (quoted, in a heredoc body, as a
    grep pattern) is not risky. Commands piped into an interpreter that cannot
    be parsed fall back to the old substring list, so they are no less guarded.
    """
    if _is_risky_git(command) or _is_risky_powershell_delete(command):
        return True
    if _DROP_TABLE_RE.search(command):  # SQL usually arrives as text for psql/mysql
        return True
    for program, args in invocations(command):
        if program == "rm" and _is_rm_rf(args):
            return True
        if program == "migrate" or "migrate" in args:
            return True
    if runs_unparsed_shell(command):
        return any(pattern in command for pattern in RISKY_PATTERNS)
    return False


THROTTLE_ENV = "CHECKPOINT_GUARD_THROTTLE_MIN"
DEFAULT_THROTTLE_MIN = 30.0


def _throttled(key: str) -> bool:
    """True if a warning for `key` was already shown inside the throttle window.

    WHY: with a stale checkpoint the same suggestion repeated on every risky
    command. Once per window is enough; `CHECKPOINT_GUARD_THROTTLE_MIN=0`
    turns the throttle off. A failure to read or write the state never blocks a
    warning.
    """
    try:
        minutes = float(os.environ.get(THROTTLE_ENV, DEFAULT_THROTTLE_MIN))
    except ValueError:
        minutes = DEFAULT_THROTTLE_MIN
    if minutes <= 0:
        return False
    path = Path(tempfile.gettempdir()) / "claude_checkpoint_guard_throttle.json"
    now = time.time()
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    last = state.get(key)
    if isinstance(last, (int, float)) and now - last < minutes * 60:
        return True
    state = {k: v for k, v in state.items() if isinstance(v, (int, float)) and now - v < 86400}
    state[key] = now
    try:
        path.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass
    return False


def find_checkpoints_dir() -> Path | None:
    """Find .claude/checkpoints/ walking up from CWD."""
    # WHY: check for existing checkpoints dir first, then fall back to .claude dir
    result = find_file_upward(str(Path(".claude") / "checkpoints"))
    if result is not None:
        return result
    # If .claude exists but no checkpoints dir, return the expected path
    claude_dir = find_file_upward(".claude")
    if claude_dir is not None and claude_dir.is_dir():
        return claude_dir / "checkpoints"
    return None


def latest_checkpoint_age(checkpoints_dir: Path) -> float | None:
    """Return age in minutes of the newest checkpoint, or None if no checkpoints."""
    if not checkpoints_dir.exists():
        return None

    md_files = list(checkpoints_dir.glob("*.md"))
    if not md_files:
        return None

    newest = max(f.stat().st_mtime for f in md_files)
    return (time.time() - newest) / 60


def main():
    data = parse_stdin()
    if not data:
        return

    tool_input = get_tool_input(data)
    command = tool_input.get("command", "")

    if not is_risky_command(command):
        return

    checkpoints_dir = find_checkpoints_dir()
    # WHY the throttle is consulted only when a warning would actually be shown:
    # a fresh checkpoint must not start a quiet period that hides a later, real one.
    would_warn = checkpoints_dir is None or (
        (age := latest_checkpoint_age(checkpoints_dir)) is None or age > 60
    )
    if not would_warn:
        return
    if _throttled(str(checkpoints_dir) if checkpoints_dir is not None else "no-checkpoints-dir"):
        return
    if checkpoints_dir is None:
        # WHY warn anyway, not silently return (LOW, cross-model audit): a
        # risky command with no .claude directory anywhere upward previously
        # produced ZERO warning -- the exact case where a checkpoint would
        # be most useful (no established save-point mechanism at all yet).
        emit_hook_result(
            "PreToolUse",
            f"[checkpoint-guard] Risky operation detected: {command[:80]}... "
            "No .claude/checkpoints directory found in this project. "
            "SUGGESTION: consider saving your current understanding of the "
            "project state before proceeding (branch, key files, current "
            "task, rollback plan) — there is no existing checkpoint to fall back to.",
        )
        return

    age = latest_checkpoint_age(checkpoints_dir)

    if age is None or age > 60:
        freshness = "no checkpoints found" if age is None else f"latest is {age:.0f} min old"
        emit_hook_result(
            "PreToolUse",
            f"[checkpoint-guard] Risky operation detected: {command[:80]}... "
            f"Checkpoint status: {freshness}. "
            "SUGGESTION: Create a checkpoint before proceeding — "
            "save state to .claude/checkpoints/<date>_<description>.md "
            "(branch, key files, current task, rollback steps).",
        )


if __name__ == "__main__":
    main()
