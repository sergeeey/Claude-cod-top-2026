#!/usr/bin/env python3
"""PostToolUse hook for Bash: auto-log commits to activeContext.md.

ПОЧЕМУ: memory_guard только НАПОМИНАЕТ обновить контекст. Этот hook ДЕЛАЕТ —
автоматически дописывает commit log в activeContext.md. Двойная страховка:
1. Автолог (факт коммита зафиксирован)
2. Напоминание Claude дополнить контекст вручную (автолог — это минимум)

Отличие от memory_guard: memory_guard проверяет свежесть файла.
post_commit_memory ведёт структурированный лог коммитов.
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_git(args: list[str], timeout: int = 10) -> str:
    """Run git command and return stdout."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def find_active_context() -> Path | None:
    """Find activeContext.md walking up from CWD."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".claude" / "memory" / "activeContext.md"
        if candidate.exists():
            return candidate
    return None


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_input = data.get("tool_input", data)
    command = tool_input.get("command", "")

    if "git commit" not in command:
        return

    # ПОЧЕМУ: проверяем tool_response на успешность — не логировать неудачные коммиты.
    # Поддерживаем оба имени поля (tool_response из документации, tool_result как fallback)
    tool_response = data.get("tool_response", data.get("tool_result", {}))
    if isinstance(tool_response, dict):
        response_text = str(tool_response.get("stdout", tool_response.get("output", "")))
    elif isinstance(tool_response, str):
        response_text = tool_response
    else:
        response_text = str(tool_response)

    # Неудачный коммит — пропускаем
    if "nothing to commit" in response_text or "error" in response_text.lower():
        return

    # Получаем данные последнего коммита
    commit_hash = run_git(["log", "-1", "--format=%h"])
    commit_msg = run_git(["log", "-1", "--format=%s"])

    if not commit_hash:
        return

    # Находим activeContext.md
    active_ctx = find_active_context()
    if active_ctx is None:
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    "[post-commit-memory] Commit logged but no activeContext.md found. "
                    "Consider creating .claude/memory/activeContext.md for project state tracking."
                ),
            }
        }
        print(json.dumps(result))
        return

    # ПОЧЕМУ: дописываем в конец файла, не перезаписываем.
    # Секция "Auto-commit log" — структурированный лог, легко парсить.
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    log_entry = f"- [{now}] `{commit_hash}`: {commit_msg}\n"

    content = active_ctx.read_text(encoding="utf-8")

    # Ищем существующую секцию или создаём новую
    section_header = "## Auto-commit log"
    if section_header in content:
        # Дописываем после заголовка секции (перед следующей секцией или в конец)
        lines = content.split("\n")
        insert_idx = None
        for i, line in enumerate(lines):
            if line.strip() == section_header:
                insert_idx = i + 1
                break
        if insert_idx is not None:
            lines.insert(insert_idx, log_entry.rstrip())
            content = "\n".join(lines)
    else:
        # Создаём секцию в конце файла
        content = content.rstrip() + f"\n\n{section_header}\n{log_entry}"

    active_ctx.write_text(content, encoding="utf-8")

    # Напоминание Claude дополнить контекст вручную
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"[post-commit-memory] Auto-logged commit {commit_hash} to activeContext.md. "
                "Please also update the context manually with WHAT was done and WHY — "
                "the auto-log only captures the commit message."
            ),
        }
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
