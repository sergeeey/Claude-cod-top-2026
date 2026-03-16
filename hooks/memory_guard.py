#!/usr/bin/env python3
"""PostToolUse hook for Bash: detect git commit and remind to update memory.

ПОЧЕМУ: После каждого коммита память должна обновляться. Без этого hook
Claude "забывает" обновить activeContext.md, и при следующей сессии
контекст устаревший.

Механизм: hook получает JSON через stdin (как все Claude Code hooks),
проверяет command на "git commit", оценивает свежесть activeContext.md.

FIX 2026-03-08: Был баг — читал os.environ вместо stdin JSON.
Результат: hook никогда не срабатывал. Исправлено.
"""

import json
import sys
import time
from pathlib import Path


def find_project_memory() -> Path | None:
    """Find activeContext.md walking up from CWD."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".claude" / "memory" / "activeContext.md"
        if candidate.exists():
            return candidate
    return None


def main():
    # ПОЧЕМУ: Claude Code передаёт данные через stdin JSON, не через env vars.
    # Формат: {"tool_input": {"command": "..."}, "tool_response": {...}}
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_input = data.get("tool_input", data)
    command = tool_input.get("command", "")

    # Only trigger on git commit commands
    if "git commit" not in command:
        return

    # Check if commit was successful
    tool_response = data.get("tool_response", data.get("tool_result", {}))
    if isinstance(tool_response, dict):
        tool_output = str(tool_response.get("stdout", tool_response.get("output", "")))
    elif isinstance(tool_response, str):
        tool_output = tool_response
    else:
        tool_output = str(tool_response)

    if "nothing to commit" in tool_output or "error" in tool_output.lower():
        return

    # Find project memory
    active_ctx = find_project_memory()
    if active_ctx is None:
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    "[memory-guard] git commit detected but no "
                    ".claude/memory/activeContext.md found. "
                    "Consider creating one to track project state."
                ),
            }
        }
        print(json.dumps(result))
        return

    # Check staleness: if activeContext was modified more than 5 min ago, it's stale
    mtime = active_ctx.stat().st_mtime
    age_minutes = (time.time() - mtime) / 60

    if age_minutes > 5:
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"[memory-guard] git commit detected. "
                    f"activeContext.md is {age_minutes:.0f} min old. "
                    "UPDATE REQUIRED: Update activeContext.md "
                    "with what was just committed. "
                    "Also check: decisions.md (if architectural), "
                    "patterns.md (if bug fix)."
                ),
            }
        }
        print(json.dumps(result))


if __name__ == "__main__":
    main()
