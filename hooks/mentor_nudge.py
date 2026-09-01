#!/usr/bin/env python3
"""UserPromptSubmit hook: periodic mentor-protocol reminder.

WHY: fires every INTERVAL-th prompt with the mentor-protocol TIP/lesson
format reminder. Previously alternated with a career-interview-question
mode (removed 2026-08-22, user request — noise on infra/audit tasks,
an unrelated tail appended to every response regardless of relevance).
Mentor-protocol now fires on every INTERVAL instead of every 2*INTERVAL.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from utils import emit_hook_result, hook_main, parse_stdin

if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

COUNTER_FILE = Path.home() / ".claude" / "cache" / "mentor_counter.txt"
INTERVAL = 3


def _read_counter() -> int:
    try:
        return int(COUNTER_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return 0


def _write_counter(n: int) -> None:
    try:
        COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
        COUNTER_FILE.write_text(str(n), encoding="utf-8")
    except OSError:
        pass


def main() -> None:
    data = parse_stdin()

    prompt = data.get("prompt", "") if isinstance(data, dict) else ""
    if len(prompt.strip()) < 10:
        return

    count = _read_counter() + 1
    _write_counter(count)

    if count % INTERVAL != 0:
        return

    message = (
        f"[mentor-protocol] Response #{count}. "
        "Format: 💡 TIP: [1-2 lines BEFORE your answer, tied to THIS specific task/file/line]. "
        "After your answer, wrap the insight in a callout box:\n"
        "> [!lesson] ⚡ Урок\n> [1-3 lines — trend/tool/cross-domain/quote, NOT obvious]\n"
        "Both required. BANNED: generic advice ('use type hints', 'write tests'). "
        "REQUIRED: concrete ('auth.py:47 Literal[...] prevents invalid status bug')."
    )

    emit_hook_result("UserPromptSubmit", message)


if __name__ == "__main__":
    hook_main(main)
