"""
PostToolUse hook: detect stub patterns in Python files written/edited by Claude.

WHY "post-hoc warning", not "block" (corrected 2026-08-29, independent
review): this fires on PostToolUse, AFTER the Edit/Write has already landed
on disk. It cannot prevent or undo the write -- exit code 2 is the
strongest available signal (surfaces stderr to Claude, see
hooks/lib/runtime.py's hook_main docstring), not a preventive block. An
earlier version of this docstring said "block", which overclaimed what a
PostToolUse hook can do -- matches the exact class of overclaim independently
found and fixed in validation_theater_guard.py's docstring the same day.

Exit codes:
    0 — no stubs found (or non-Python file, or a parse/read error -- fails
        transparent, never escalates on its own failure)
    2 — stub patterns found; reports them to Claude via stderr as a post-hoc
        warning. The write already happened and is not undone.
"""

import json
import re
import sys
from pathlib import Path

from utils import hook_main

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
    """Read PostToolUse event from stdin and warn (post-hoc, via stderr/exit
    code) if stubs are detected -- cannot block or undo the write, see
    module docstring."""
    try:
        raw = sys.stdin.read()
        event = json.loads(raw)
    except Exception:
        # WHY: never escalate on parse errors — hook must be transparent on failure
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
    # WHY hook_main wrap (bottleneck #2, /boyko-project-radar autonomy-
    # subsystem scan, 2026-08-29): bare main() left an uncaught exception as
    # an unhandled crash rather than this hook's own registry.yaml-declared
    # fail_mode: open. fail_closed=False (default) is correct: PostToolUse
    # warn-only, never a permission decision.
    hook_main(main, fail_closed=False)
