#!/usr/bin/env python3
"""PostToolUse hook for Bash: detect risky operations and suggest checkpoint.

WHY: Before major changes (refactoring, migration, deletion) a context
"save point" is needed. If something goes wrong — the checkpoint allows
restoring the understanding of the project state.

Mechanism: hook receives JSON via stdin (like all Claude Code hooks),
checks the command against risky patterns, verifies checkpoint freshness.

FIX 2026-03-08: There was a bug — it read os.environ instead of stdin JSON.
Result: the hook never fired. Fixed.
"""

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
    "rm -rf",
    "drop table",
    "DROP TABLE",
    "migrate",
]


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
    is_risky = any(pattern in command for pattern in RISKY_PATTERNS)
    if not is_risky:
        return

    checkpoints_dir = find_checkpoints_dir()
    if checkpoints_dir is None:
        return

    age = latest_checkpoint_age(checkpoints_dir)

    if age is None or age > 60:
        freshness = "no checkpoints found" if age is None else f"latest is {age:.0f} min old"
        emit_hook_result(
            "PostToolUse",
            f"[checkpoint-guard] Risky operation detected: {command[:80]}... "
            f"Checkpoint status: {freshness}. "
            "SUGGESTION: Create a checkpoint before proceeding — "
            "save state to .claude/checkpoints/<date>_<description>.md "
            "(branch, key files, current task, rollback steps).",
        )


if __name__ == "__main__":
    main()
