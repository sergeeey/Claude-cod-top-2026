#!/usr/bin/env python3
"""PostToolUse(Edit) hook: detect tests weakened to force a pass.

WHY: The single most common form of validation theater in coding loops is
silently weakening a test so it passes — deleting an assert, replacing it with
`assert True`, commenting it out, or adding @pytest.mark.skip. The reviewer
prompt asks "tests not weakened?" but nothing enforces it. This catches the
edit at write-time.

Closes gap #2 of the self-fix hardening plan (research-methodology stack).
Soft nudge via additionalContext (never blocks) — symmetric to reject_gate_guard.

Fires on: Edit to a test file (test_*.py, *_test.py, or under a tests/ dir).
Compares old_string vs new_string and flags:
  1. assert count dropped         (removed assertions)
  2. new skip/xfail introduced    (test disabled)
  3. tautological assert added    (assert True / assert 1 == 1)
  4. assertion commented out      (# assert ...)
"""

import json
import os
import re
import sys
from pathlib import Path

_ASSERT_RE = re.compile(r"^\s*assert\b", re.MULTILINE)
_SKIP_RE = re.compile(
    r"@(?:pytest\.mark\.|unittest\.)?(?:skip|xfail)\b|pytest\.skip\s*\(",
    re.IGNORECASE,
)
_TAUTOLOGY_RE = re.compile(
    r"^\s*assert\s+(True|1|1\s*==\s*1|2\s*==\s*2)\s*(#.*)?$",
    re.MULTILINE,
)
_COMMENTED_ASSERT_RE = re.compile(r"^\s*#\s*assert\b", re.MULTILINE)


def _is_test_file(file_path: str) -> bool:
    """Return True if the path is a Python test file."""
    p = Path(file_path)
    if p.suffix != ".py":
        return False
    if p.name.startswith("test_") or p.stem.endswith("_test"):
        return True
    return "tests" in set(p.parts)


def _count(rx: re.Pattern, text: str) -> int:
    return len(rx.findall(text))


def _weakening_signals(old: str, new: str) -> list[str]:
    """Return human-readable weakening signals introduced by old -> new."""
    signals = []

    old_asserts = _count(_ASSERT_RE, old)
    new_asserts = _count(_ASSERT_RE, new)
    if new_asserts < old_asserts:
        removed = old_asserts - new_asserts
        signals.append(f"assertions dropped {old_asserts} → {new_asserts} (removed {removed})")

    if _count(_SKIP_RE, new) > _count(_SKIP_RE, old):
        signals.append("test disabled via skip/xfail")

    if _count(_TAUTOLOGY_RE, new) > _count(_TAUTOLOGY_RE, old):
        signals.append("tautological assertion added (assert True / 1==1)")

    if _count(_COMMENTED_ASSERT_RE, new) > _count(_COMMENTED_ASSERT_RE, old):
        signals.append("assertion commented out (# assert ...)")

    return signals


def main() -> None:
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    # WHY: weakening is an Edit operation — a brand-new Write test file is not
    # "weakening", it's authoring. Only Edit carries old_string to compare.
    if data.get("tool_name", "") != "Edit":
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path or not _is_test_file(file_path):
        sys.exit(0)

    old = tool_input.get("old_string", "")
    new = tool_input.get("new_string", "")
    if not old:
        sys.exit(0)

    signals = _weakening_signals(old, new)
    if not signals:
        sys.exit(0)

    msg = (
        "[test-integrity] ⚠️  This edit may WEAKEN a test to force a pass:\n"
        + "\n".join(f"  ✗ {s}" for s in signals)
        + "\n\n→ A test is a behavioral spec. If the code is wrong, fix the CODE, not the test. "
        "Only weaken a test if the behavior it checks was intentionally removed — and say why."
    )

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": msg,
                }
            }
        )
    )


if __name__ == "__main__":
    main()
