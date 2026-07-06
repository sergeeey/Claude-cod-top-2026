#!/usr/bin/env python3
"""PostToolUse(Edit) hook: detect tests weakened to force a pass.

WHY: The single most common form of validation theater in coding loops is
silently weakening a test so it passes — deleting an assert, replacing it with
`assert True`, commenting it out, or adding @pytest.mark.skip. The reviewer
prompt asks "tests not weakened?" but nothing enforces it. This catches the
edit at write-time.

Closes gap #2 of the self-fix hardening plan (research-methodology stack).
Soft nudge via additionalContext (never blocks) — symmetric to reject_gate_guard.

Fires on:
  PostToolUse(Edit) to a test file — compares old_string vs new_string.
  PreToolUse(Write) to an EXISTING test file — stashes its current on-disk
    content (cross-model audit fix: a whole-file `Write` replacement to an
    existing test file previously skipped weakening detection entirely,
    since the guard only ever handled `Edit`'s old_string/new_string pair).
  PostToolUse(Write) to a test file — retrieves the stashed content and
    compares it against the just-written content, same as the Edit path.
State: <cwd>/.claude/state/weakened_test_guard.json (pending Write stashes).

Flags:
  1. assert count dropped         (removed assertions, unittest OR bare assert)
  2. new skip/xfail introduced    (test disabled, incl. @pytest.mark.skipif)
  3. tautological assert added    (assert True / assert 1 == 1)
  4. assertion commented out      (# assert ...)
"""

import json
import os
import re
import sys
from pathlib import Path

from hook_state import HookState

_ASSERT_RE = re.compile(r"^\s*assert\b", re.MULTILINE)
# WHY unittest methods (MEDIUM, cross-model audit): the old check only
# counted bare `assert` statements, so replacing `self.assertEqual(a, b)`
# with nothing (or a no-op) went undetected in unittest.TestCase-style tests.
_UNITTEST_ASSERT_RE = re.compile(
    r"^\s*self\.assert\w+\(",
    re.MULTILINE,
)
# WHY skipif (MEDIUM, cross-model audit): `@pytest.mark.skipif(...)` disables
# a test just as effectively as `@pytest.mark.skip`, but wasn't matched.
_SKIP_RE = re.compile(
    r"@(?:pytest\.mark\.|unittest\.)?(?:skip(?:if)?|xfail)\b|pytest\.skip\s*\(",
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


def _total_assert_count(text: str) -> int:
    """Bare `assert` statements PLUS unittest.TestCase-style `self.assertX(...)`
    calls -- counting only bare asserts missed a test weakened by deleting
    `self.assertEqual(a, b)` in a unittest-style suite."""
    return _count(_ASSERT_RE, text) + _count(_UNITTEST_ASSERT_RE, text)


def _weakening_signals(old: str, new: str) -> list[str]:
    """Return human-readable weakening signals introduced by old -> new."""
    signals = []

    old_asserts = _total_assert_count(old)
    new_asserts = _total_assert_count(new)
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


def _emit_warning(signals: list[str]) -> None:
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


def _read_existing_content(file_path: str) -> str | None:
    """Current on-disk content of file_path, or None if it doesn't exist yet
    (a brand-new file is authoring, not weakening -- nothing to compare)."""
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except OSError:
        return None


def main() -> None:
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    is_post = "tool_response" in data
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if tool_name == "Edit":
        # WHY gate on is_post: this hook is registered under BOTH
        # PreToolUse(Edit|Write) and PostToolUse(Edit|Write) -- PreToolUse is
        # needed for the Write-stash leg below, but Edit's old_string/
        # new_string are identical in both phases. Without this guard, a
        # single Edit call would run this exact check twice and could print
        # the same warning twice.
        if not is_post:
            sys.exit(0)
        if not file_path or not _is_test_file(file_path):
            sys.exit(0)
        old = tool_input.get("old_string", "")
        new = tool_input.get("new_string", "")
        if not old:
            sys.exit(0)
        signals = _weakening_signals(old, new)
        if signals:
            _emit_warning(signals)
        sys.exit(0)

    # WHY handle MultiEdit too (cross-model audit, same vulnerability class
    # as the Write fix below): the "Edit|Write" matcher is an unanchored
    # regex -- "Edit" matches as a SUBSTRING of "MultiEdit" -- so this hook
    # was ALREADY being invoked for MultiEdit calls, just silently falling
    # through to the final sys.exit(0) with zero detection, since MultiEdit
    # carries a batch `edits` list, not a single old_string/new_string pair.
    if tool_name == "MultiEdit":
        if not is_post:
            sys.exit(0)
        if not file_path or not _is_test_file(file_path):
            sys.exit(0)
        all_signals: list[str] = []
        for edit in tool_input.get("edits", []):
            old = edit.get("old_string", "")
            new = edit.get("new_string", "")
            if not old:
                continue
            for signal in _weakening_signals(old, new):
                if signal not in all_signals:
                    all_signals.append(signal)
        if all_signals:
            _emit_warning(all_signals)
        sys.exit(0)

    # WHY handle Write too (HIGH, cross-model audit): replacing a whole
    # EXISTING test file via `Write` previously skipped weakening detection
    # entirely, since the guard only ever compared Edit's old_string/
    # new_string pair. A PreToolUse(Write) leg stashes the file's current
    # on-disk content BEFORE it's overwritten; the PostToolUse(Write) leg
    # retrieves that stash and compares it against what was just written --
    # the same detection logic as the Edit path, applied to a full-file diff.
    if tool_name == "Write":
        if not file_path or not _is_test_file(file_path):
            sys.exit(0)

        state = HookState("weakened_test_guard")
        pending = state.get("pending", {}) or {}

        if not is_post:
            old_content = _read_existing_content(file_path)
            if old_content is not None:
                pending[file_path] = old_content
                state["pending"] = pending
                state.save()
            sys.exit(0)

        old = pending.pop(file_path, None)
        if old is not None:
            state["pending"] = pending
            state.save()
        if old is None:
            # WHY not None -> stop, not "no signal": no stashed content means
            # either the file was brand-new (authoring, not weakening) or the
            # PreToolUse leg never ran for this file -- either way there is
            # no "before" to compare against.
            sys.exit(0)

        new = tool_input.get("content", "")
        signals = _weakening_signals(old, new)
        if signals:
            _emit_warning(signals)
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
