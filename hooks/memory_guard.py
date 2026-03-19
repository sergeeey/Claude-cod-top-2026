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

import time

from utils import (
    emit_hook_result,
    extract_tool_response,
    find_project_memory,
    get_tool_input,
    is_failed_commit,
    parse_stdin,
)


def main():
    data = parse_stdin()
    if not data:
        return

    tool_input = get_tool_input(data)
    command = tool_input.get("command", "")

    if "git commit" not in command:
        return

    response_text = extract_tool_response(data)
    if is_failed_commit(response_text):
        return

    # Find project memory
    active_ctx = find_project_memory()
    if active_ctx is None:
        emit_hook_result(
            "PostToolUse",
            "[memory-guard] git commit detected but no .claude/memory/activeContext.md found. "
            "Consider creating one to track project state.",
        )
        return

    # Check staleness: if activeContext was modified more than 5 min ago, it's stale
    mtime = active_ctx.stat().st_mtime
    age_minutes = (time.time() - mtime) / 60

    if age_minutes > 5:
        emit_hook_result(
            "PostToolUse",
            f"[memory-guard] git commit detected. activeContext.md is {age_minutes:.0f} min old. "
            "UPDATE REQUIRED: Update .claude/memory/activeContext.md with what was just committed. "
            "Also check: decisions.md (if architectural), patterns.md (if bug fix).",
        )


if __name__ == "__main__":
    main()
