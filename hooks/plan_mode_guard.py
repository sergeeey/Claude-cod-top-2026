#!/usr/bin/env python3
"""PostToolUse hook for Edit|Write: remind about Plan-First Protocol.

ПОЧЕМУ: CLAUDE.md v10.0 требует EnterPlanMode при 3+ файлах, но агент может
забыть к середине сессии. Hook считает уникальные файлы и напоминает
принудительно — это работает на уровне системы, а не "памяти".

Механизм: temp-файл /tmp/claude_plan_guard_<session>.txt хранит пути
отредактированных файлов. При >=3 уникальных — напоминание.

v2: если в .claude/plans/ есть активный plan file для текущей сессии,
предупреждение подавляется — план уже существует.
"""
import json
import sys
import tempfile
from pathlib import Path


def get_tracker_path(session_id: str) -> Path:
    """Get path for session-specific file tracker."""
    # ПОЧЕМУ: используем session_id, а не PID — PID может переиспользоваться,
    # session_id уникален для каждой сессии Claude Code
    safe_id = session_id.replace("/", "_").replace("\\", "_")[:32]
    return Path(tempfile.gettempdir()) / f"claude_plan_guard_{safe_id}.txt"


def has_active_plan() -> bool:
    """Check if any plan file exists in .claude/plans/ directory.

    ПОЧЕМУ: если план уже существует (одобрен или в процессе), предупреждение
    о 3+ файлах без плана — ложноположительное. Проверяем наличие .md файлов
    в plans/ как маркер того что план был создан.
    """
    plans_dir = Path.home() / ".claude" / "plans"
    if not plans_dir.exists():
        return False
    # Любой .md файл, модифицированный за последние 24 часа = активный план
    import time
    now = time.time()
    for f in plans_dir.glob("*.md"):
        if now - f.stat().st_mtime < 86400:  # 24 hours
            return True
    return False


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    # ПОЧЕМУ: поддерживаем оба формата — вложенный tool_input и плоский (legacy).
    # post_format.py читает file_path с root, но документация говорит о вложенности.
    tool_input = data.get("tool_input", data)
    file_path = tool_input.get("file_path", "")

    if not file_path:
        return

    # Session tracking
    session_id = data.get("session_id", "unknown")
    tracker = get_tracker_path(session_id)

    # Read existing paths
    existing_paths: set[str] = set()
    if tracker.exists():
        existing_paths = set(tracker.read_text(encoding="utf-8").strip().split("\n"))
        existing_paths.discard("")

    # Add new path (normalize)
    normalized = str(Path(file_path).resolve())
    existing_paths.add(normalized)

    # Write back
    tracker.write_text("\n".join(existing_paths) + "\n", encoding="utf-8")

    count = len(existing_paths)

    # ПОЧЕМУ: если план существует — не предупреждать, агент работает по плану.
    if has_active_plan():
        return

    # ПОЧЕМУ: 3 — порог из CLAUDE.md v10.0 Plan-First Protocol.
    # 5 — более настойчивое, потому что агент явно игнорирует первое напоминание.
    if count == 3:
        # Мягкое напоминание — JSON stdout чтобы Claude увидел
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    "[plan-mode-guard] 3 unique files edited in this session. "
                    "CLAUDE.md v10.0 Plan-First Protocol: tasks touching 3+ files "
                    "should use EnterPlanMode first. Consider the 4-phase workflow: "
                    "Explore -> Design (brainstorming skill) -> Plan -> Code. "
                    "If you haven't planned — pause and create a plan."
                ),
            }
        }
        print(json.dumps(result))
    elif count >= 5:
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"[plan-mode-guard] WARNING: {count} unique files edited without "
                    "a plan! This violates Plan-First Protocol (CLAUDE.md v10.0). "
                    "STOP and create a plan via EnterPlanMode (Explore -> Design "
                    "-> Plan -> Code), or confirm with user that no plan is needed."
                ),
            }
        }
        print(json.dumps(result))


if __name__ == "__main__":
    main()
