#!/usr/bin/env python3
"""PostToolUse hook for Bash: detect risky operations and suggest checkpoint.

ПОЧЕМУ: Перед крупными изменениями (рефакторинг, миграция, удаление)
нужна "точка сохранения" контекста. Если что-то пойдёт не так —
можно восстановить понимание состояния проекта из checkpoint.

Механизм: hook получает JSON через stdin (как все Claude Code hooks),
проверяет command на рисковые паттерны, проверяет свежесть checkpoints.

FIX 2026-03-08: Был баг — читал os.environ вместо stdin JSON.
Результат: hook никогда не срабатывал. Исправлено.
"""
import json
import sys
import time
from pathlib import Path

# ПОЧЕМУ: эти команды потенциально меняют состояние проекта так,
# что восстановление контекста без checkpoint будет сложным
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
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".claude" / "checkpoints"
        if candidate.exists():
            return candidate
        claude_dir = parent / ".claude"
        if claude_dir.exists():
            return candidate
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
    # ПОЧЕМУ: Claude Code передаёт данные через stdin JSON, не через env vars.
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_input = data.get("tool_input", data)
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
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"[checkpoint-guard] Risky operation detected: {command[:80]}... "
                    f"Checkpoint status: {freshness}. "
                    "SUGGESTION: Create a checkpoint before proceeding — "
                    "save state to .claude/checkpoints/<date>_<description>.md "
                    "(branch, key files, current task, rollback steps)."
                ),
            }
        }
        print(json.dumps(result))


if __name__ == "__main__":
    main()
