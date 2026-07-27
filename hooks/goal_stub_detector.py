"""
PostToolUse hook: detect stub patterns in Python files written/edited by Claude.

Exit codes:
    0 — allow (no stubs or non-Python or error)
    2 — block (stub patterns found)
"""

import json
import re
import sys
from pathlib import Path

# WHY: compile once at module level — hook runs per-tool-use, keep it fast
STUB_PATTERNS = re.compile(
    r"(TODO|FIXME|raise\s+NotImplementedError|pass\s*#\s*stub)",
    re.IGNORECASE,
)


def is_excluded(file_path: Path) -> bool:
    """Return True if the file should be skipped (tests dir or test_ prefix)."""
    parts = file_path.parts
    # WHY: check every path segment so nested tests/ dirs are also excluded
    if any(part == "tests" for part in parts):
        return True
    if file_path.name.startswith("test_"):
        return True
    return False


def main() -> None:
    """Read PostToolUse event from stdin and block if stubs are detected."""
    try:
        raw = sys.stdin.read()
        event = json.loads(raw)
    except Exception:
        # WHY: never block on parse errors — hook must be transparent on failure
        sys.exit(0)

    tool_name = event.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    raw_path = tool_input.get("file_path", "")
    if not raw_path:
        sys.exit(0)

    file_path = Path(raw_path)

    if file_path.suffix != ".py":
        sys.exit(0)

    if is_excluded(file_path):
        sys.exit(0)

    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        # WHY: file may not exist yet or be unreadable — don't block on I/O errors
        sys.exit(0)

    findings: list[str] = []
    for line_num, line in enumerate(lines, start=1):
        if STUB_PATTERNS.search(line):
            findings.append(f"STUB_DETECTED: {file_path}:{line_num}: {line.strip()}")

    if findings:
        for msg in findings:
            print(msg, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
