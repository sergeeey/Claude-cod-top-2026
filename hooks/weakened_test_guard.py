#!/usr/bin/env python3
"""PreToolUse(Edit|MultiEdit|Write) hook: block tests weakened to force a pass.

WHY: The single most common form of validation theater in coding loops is
silently weakening a test so it passes -- deleting an assert, replacing it with
`assert True`, commenting it out, or adding @pytest.mark.skip. The reviewer
prompt asks "tests not weakened?" but nothing enforces it. This blocks the
edit before it lands.

Closes gap #2 of the self-fix hardening plan (research-methodology stack).

UPGRADED (2026-07-17, coherence audit): was a PostToolUse-only soft nudge
(additionalContext, never blocked) -- a weakening edit could still land. The
same audit found hooks/settings.json's permission-deny glob patterns for test
files (*.test.py, *_test.py, *tests.py) never matched this repo's own
`test_*.py` convention, so nothing else stopped it either. Now a hard
PreToolUse block via emit_permission_decision(deny). All three tool shapes
carry everything needed to compare BEFORE the tool executes -- Edit's
old_string/new_string, MultiEdit's edits list, and Write's full content are
all present in tool_input at PreToolUse time -- so no PostToolUse leg or
stash file is needed anymore.

Fires on:
  PreToolUse(Edit)      to a test file -- compares old_string vs new_string.
  PreToolUse(MultiEdit)  to a test file -- compares each edit's old/new pair.
  PreToolUse(Write)      to an EXISTING test file -- reads current on-disk
    content as "old", compares against tool_input["content"] as "new". A
    brand-new file (nothing on disk yet) is authoring, not weakening --
    always allowed.
  PostToolUse invocations of this same hook (registered via the "Edit|Write"
    matcher substring match) are a no-op: the decision was already made
    before the tool ran.

Flags (any one blocks):
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

from utils import emit_permission_decision

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


def _emit_block(signals: list[str]) -> None:
    msg = (
        "[test-integrity] BLOCKED: this edit would WEAKEN a test to force a pass:\n"
        + "\n".join(f"  ✗ {s}" for s in signals)
        + "\n\n→ A test is a behavioral spec. If the code is wrong, fix the CODE, not the test. "
        "Only weaken a test if the behavior it checks was intentionally removed — say why, "
        "then re-apply with the user's explicit go-ahead."
    )
    emit_permission_decision(decision="deny", reason=msg)


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

    # Only PreToolUse can carry a permissionDecision the client will honor --
    # this hook is also invoked at PostToolUse (same "Edit|Write" matcher
    # entry fires for both events), but by then the decision already landed.
    if "tool_response" in data:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if tool_name == "Edit":
        if not file_path or not _is_test_file(file_path):
            sys.exit(0)
        old = tool_input.get("old_string", "")
        new = tool_input.get("new_string", "")
        if not old:
            sys.exit(0)
        signals = _weakening_signals(old, new)
        if signals:
            _emit_block(signals)
        sys.exit(0)

    # WHY handle MultiEdit too (cross-model audit, same vulnerability class
    # as Write below): the "Edit|Write" matcher is an unanchored regex --
    # "Edit" matches as a SUBSTRING of "MultiEdit" -- so this hook is already
    # invoked for MultiEdit calls; it carries a batch `edits` list, not a
    # single old_string/new_string pair.
    if tool_name == "MultiEdit":
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
            _emit_block(all_signals)
        sys.exit(0)

    # WHY Write needs handling too (HIGH, cross-model audit): replacing a
    # whole EXISTING test file via `Write` (not `Edit`) previously skipped
    # weakening detection entirely. At PreToolUse the file on disk is still
    # the OLD version and tool_input["content"] is already the proposed NEW
    # version -- both sides of the comparison are available before the tool
    # runs, so this can decide (and block) in a single pass.
    if tool_name == "Write":
        if not file_path or not _is_test_file(file_path):
            sys.exit(0)
        old = _read_existing_content(file_path)
        if old is None:
            # brand-new file: authoring, not weakening -- nothing to compare
            sys.exit(0)
        new = tool_input.get("content", "")
        signals = _weakening_signals(old, new)
        if signals:
            _emit_block(signals)
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
