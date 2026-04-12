#!/usr/bin/env python3
"""PreToolUse hook: validate Python/JS syntax before Write/Edit.

WHY: Claude generates code → writes to disk → runs → SyntaxError → rewrites.
This cycle wastes tokens and breaks flow. Catching syntax errors BEFORE disk
write eliminates it entirely. Python ast.parse() takes ~0.3ms on 500 lines.

Coverage:
  .py  → stdlib ast.parse() (zero dependencies)
  .js  → node --check (skipped if node not in PATH)
  .ts  → skipped (requires tsc, too heavy for a hook)
"""

import ast
import subprocess
import sys
from pathlib import Path

from utils import get_tool_input, hook_main, parse_stdin


def _validate_python(content: str) -> str | None:
    """Return error description or None if syntax is valid."""
    try:
        ast.parse(content)
        return None
    except SyntaxError as e:
        loc = f"line {e.lineno}" if e.lineno else "unknown line"
        return f"{loc}: {e.msg}"


def _validate_js(content: str) -> str | None:
    """Validate JS via `node --input-type=module`. Returns error or None.

    WHY: node --check requires a file, but we only have content as a string.
    --input-type=module + stdin is the zero-temp-file approach.
    Fails silently if node is not installed (fail-open).
    """
    try:
        result = subprocess.run(
            ["node", "--input-type=module"],
            input=content,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 and result.stderr:
            # WHY: node stderr has full path noise — strip to first error line
            first_error = result.stderr.strip().splitlines()[0]
            return first_error[:200]
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # WHY: node not available or too slow → fail-open, do not block write
        return None


def main() -> None:
    data = parse_stdin()
    tool_name: str = data.get("tool_name", "")

    # WHY: only Write and Edit produce new content. MultiEdit is an alias
    # for batch edits — each new_string fragment goes through Edit anyway.
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = get_tool_input(data)
    file_path: str = tool_input.get("file_path", "")

    # Write sends new_content; Edit sends new_string
    content: str = tool_input.get("new_content") or tool_input.get("new_string", "")

    if not content or not file_path:
        sys.exit(0)

    suffix = Path(file_path).suffix.lower()
    error: str | None = None

    if suffix == ".py":
        error = _validate_python(content)
    elif suffix in (".js", ".mjs", ".cjs"):
        error = _validate_js(content)
    # .ts/.tsx: skip — tsc is too heavy for inline hook

    if error:
        import json

        reason = (
            f"SyntaxError in {Path(file_path).name}: {error}. Fix the syntax error before writing."
        )
        print(json.dumps({"decision": "block", "reason": reason}))
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    hook_main(main)
