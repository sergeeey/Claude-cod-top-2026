#!/usr/bin/env python3
"""PostToolUse: auto-format Python and JS/TS files after Edit/Write.

WHY: ruff format instead of black — faster (10-100x), compatible output,
one tool for lint+format. CLAUDE.md v10.0 requires ruff.

FIX 2026-03-08: black → ruff format. Also fixed stdin parsing —
tool_input can be nested.
"""

import os
import subprocess

from utils import get_tool_input, parse_stdin


def main():
    data = parse_stdin()
    if not data:
        return

    # WHY: we support both formats — nested tool_input and flat
    tool_input = get_tool_input(data)
    path = tool_input.get("file_path", "")

    if not path or not os.path.exists(path):
        return

    ext = os.path.splitext(path)[1].lower()

    if ext == ".py":
        # WHY: ruff format — 10-100x faster than black, drop-in replacement
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
