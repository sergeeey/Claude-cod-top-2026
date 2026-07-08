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

import re
import time
from pathlib import Path

from utils import emit_hook_result, find_file_upward, get_tool_input, parse_stdin

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

    # Check if command matches risky patterns
    is_risky = any(pattern in command for pattern in RISKY_PATTERNS) or _is_risky_powershell_delete(
        command
    )
    if not is_risky:
        return

    checkpoints_dir = find_checkpoints_dir()
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
