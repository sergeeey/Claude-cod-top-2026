#!/usr/bin/env python3
"""PostToolUse: auto-format Python and JS/TS files after Edit/Write.

ПОЧЕМУ: ruff format вместо black — быстрее (10-100x), совместимый вывод,
один инструмент для lint+format. CLAUDE.md v10.0 требует ruff.

FIX 2026-03-08: black → ruff format. Также исправлен парсинг stdin —
tool_input может быть вложенным.
"""

import os
import subprocess

from utils import get_tool_input, parse_stdin


def main():
    data = parse_stdin()
    if not data:
        return

    # ПОЧЕМУ: поддерживаем оба формата — вложенный tool_input и плоский
    tool_input = get_tool_input(data)
    path = tool_input.get("file_path", "")

    if not path or not os.path.exists(path):
        return

    ext = os.path.splitext(path)[1].lower()

    if ext == ".py":
        # ПОЧЕМУ: ruff format — 10-100x быстрее black, drop-in replacement
        subprocess.run(
            ["ruff", "format", "--line-length", "100", "--quiet", path],
            capture_output=True,
        )
    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        subprocess.run(
            ["prettier", "--write", "--log-level", "silent", path],
            capture_output=True,
        )


if __name__ == "__main__":
    main()
