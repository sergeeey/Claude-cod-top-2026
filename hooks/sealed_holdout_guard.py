#!/usr/bin/env python3
"""PreToolUse(Edit|MultiEdit|Write) hook: block a sealed_holdout.yaml "re-seal"
or a structurally invalid consumption.

WHY: experiments/_template/sealed_holdout.yaml's own hard rule is "once opened
(consumed: true), it is CONSUMED -- no longer a valid holdout for any further
optimization of this same branch." Nothing enforced that before this hook --
an author (or an agent under time pressure) could bump `opened_at` to a new,
later timestamp while keeping `sealed_at`/`holdout_ref` the same, making a
CONSUMED holdout look freshly opened again for a second round of tuning against
it -- exactly the Goodhart risk this file exists to prevent in the first place.

Mirrors hooks/weakened_test_guard.py's own shape: a PreToolUse hard block via
emit_permission_decision(deny), comparing OLD (on-disk or reconstructed) vs NEW
content for the three tool shapes (Edit/MultiEdit/Write), stdlib-only (no
PyYAML dependency -- hooks run without package installs, same reasoning as
hooks/independence_scorer.py's own minimal regex-based extractor).

Flags (any one blocks):
  1. Re-seal attempt: OLD had consumed=true, NEW changes opened_at to a
     DIFFERENT value while sealed_at/holdout_ref stay the same.
  2. Structurally invalid consumption: NEW sets consumed=true but opened_at
     is null/missing.
"""

import json
import os
import re
import sys
from pathlib import Path

from lib.runtime import emit_permission_decision, get_tool_input, hook_main

_FLAT_KEY_RE = re.compile(r"^(\w+):\s*(.*)$", re.MULTILINE)
# WHY (skeptic-found, 2026-09-12): YAML 1.1 (what yaml.safe_load, used by
# scripts/check_experiment_graph.py, actually implements) resolves "yes"/"on"
# to True too. Without matching that here, `consumed: yes` is treated as
# consumed by the offline CI check but NOT by this hook's own _is_true --
# the re-seal guard below would then never arm for a holdout an author
# legitimately marked consumed with a YAML 1.1 boolean spelling.
_TRUE_STRINGS = frozenset({"true", "yes", "on"})


def _is_sealed_holdout_file(file_path: str) -> bool:
    p = Path(file_path)
    return p.name == "sealed_holdout.yaml" and "experiments" in set(p.parts)


def _strip_inline_comment(raw: str) -> str:
    """Drop a trailing ' # comment' from a raw YAML scalar value.

    WHY (skeptic-found, 2026-09-12, verified via constructed input): without
    this, `consumed: true    # opened at VERIFY yesterday` extracts the WHOLE
    remainder of the line as the value, so `_is_true()` on
    `"true    # opened at VERIFY yesterday"` returns False -- silently
    defeating both the re-seal guard (old_consumed reads False) and
    promotion_gate_guard.py's invariant (a comment-suffixed delta fails
    float() and is treated as "not filled", silently passing the exact
    internal-up/held-out-down signature the gate exists to catch).

    Only splits on a '#' preceded by whitespace or at the very start of the
    value, matching YAML's own comment-recognition rule -- a bare `#` glued
    to non-whitespace is part of the scalar, not a comment start. This is a
    best-effort, not a full YAML scanner: a value that legitimately contains
    ' #' (none of this file's real fields do -- hash/path/timestamp/number
    shapes) would be truncated too. Documented limitation, not a silent gap.
    """
    return re.split(r"(?:^|\s)#", raw, maxsplit=1)[0].strip()


def _extract_flat_fields(content: str) -> dict[str, str | None]:
    """Minimal top-level key:value extractor -- avoids a PyYAML dependency,
    same reasoning as hooks/independence_scorer.py's _parse_yaml_paths.
    Only handles this file's own flat (non-nested, non-list) shape.

    Comment-stripping happens HERE, at the single point of extraction, so
    every consumer (this file's own _is_true, and promotion_gate_guard.py's
    _to_float, which imports this same function) gets a clean value --
    fixing the root cause once instead of patching each consumer separately.
    """
    fields: dict[str, str | None] = {}
    for m in _FLAT_KEY_RE.finditer(content):
        key = m.group(1)
        raw = _strip_inline_comment(m.group(2))
        if raw.lower() in ("null", "~", ""):
            fields[key] = None
        else:
            fields[key] = raw.strip("\"'")
    return fields


def _is_true(value: str | None) -> bool:
    return (value or "").strip().lower() in _TRUE_STRINGS


def _weakening_signals(old: str, new: str) -> list[str]:
    old_fields = _extract_flat_fields(old)
    new_fields = _extract_flat_fields(new)
    signals: list[str] = []

    old_consumed = _is_true(old_fields.get("consumed"))
    new_opened_at = new_fields.get("opened_at")
    old_opened_at = old_fields.get("opened_at")
    # WHY keyed on holdout_ref ALONE, not holdout_ref+sealed_at (sec-auditor-
    # found, 2026-09-12, live-verified before fixing): requiring BOTH fields
    # unchanged let an author bump `sealed_at` while keeping the SAME
    # `holdout_ref` and slip past this guard undetected -- reuse of the same
    # underlying holdout DATA is the actual violation; `sealed_at` is
    # author-editable metadata and must not be able to launder a re-seal by
    # itself.
    same_holdout = old_fields.get("holdout_ref") == new_fields.get("holdout_ref")

    if old_consumed and same_holdout and new_opened_at != old_opened_at:
        signals.append(
            "re-seal attempt: this holdout was already consumed (consumed=true) -- "
            f"opened_at cannot move from {old_opened_at!r} to {new_opened_at!r} while "
            "holdout_ref stays the same. A consumed holdout is no longer valid "
            "for any further optimization of this branch."
        )

    new_consumed = _is_true(new_fields.get("consumed"))
    if new_consumed and not new_opened_at:
        signals.append(
            "structurally invalid consumption: consumed=true but opened_at is not set -- "
            "a holdout can only be consumed by being opened"
        )

    return signals


def _emit_block(signals: list[str]) -> None:
    msg = (
        "[sealed-holdout-guard] BLOCKED: this edit would violate the sealed-holdout "
        "invariant:\n"
        + "\n".join(f"  ✗ {s}" for s in signals)
        + "\n\n→ A sealed holdout opens exactly once, at VERIFY stage. If this "
        "experiment genuinely needs a fresh holdout for a new round, create a NEW "
        "sealed_holdout.yaml (new holdout_ref) rather than reopening a consumed one."
    )
    emit_permission_decision(decision="deny", reason=msg)


def _read_existing_content(file_path: str) -> str | None:
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except OSError:
        return None


def main() -> None:
    # WHY (sec-auditor-found, 2026-09-12, verified live via a real piped
    # subprocess before fixing): a malformed payload (non-dict data, or a
    # non-dict tool_input) previously crashed INSIDE the relevance check
    # itself, before _is_sealed_holdout_file() ever ran -- meaning the crash
    # happened for ANY Edit/Write call, not just ones targeting
    # sealed_holdout.yaml. That was harmless only because hooks/lib/
    # runtime.py's own fail_closed path silently discarded the resulting
    # deny (fixed separately, PR #443) -- fixing THAT alone would have made
    # THIS hook start denying arbitrary unrelated Edit/Write calls on any
    # malformed payload. Both fixes are required together; this is the
    # second half. get_tool_input() already handles a non-dict tool_input
    # (falls back to `data` itself); the isinstance guard on file_path
    # covers the remaining case where tool_input is a dict but file_path is
    # some non-string value.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)
    if not isinstance(data, dict):
        sys.exit(0)

    # Only PreToolUse carries a permissionDecision the client will honor.
    if "tool_response" in data:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = get_tool_input(data)
    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path or not _is_sealed_holdout_file(file_path):
        sys.exit(0)  # irrelevant to this hook -- never deny an unrelated call

    if tool_name == "Edit":
        old = _read_existing_content(file_path)
        if old is None:
            sys.exit(0)  # brand-new file -- authoring, nothing to compare
        new_string = str(tool_input.get("new_string", ""))
        old_string = str(tool_input.get("old_string", ""))
        new = old.replace(old_string, new_string, 1) if old_string in old else old
        signals = _weakening_signals(old, new)
        if signals:
            _emit_block(signals)
        sys.exit(0)

    # WHY this branch is reachable despite the registered matcher being
    # "Edit|Write", not "Edit|MultiEdit|Write" (sec-auditor raised this as
    # [UNKNOWN], 2026-09-12): hooks/weakened_test_guard.py's own identical
    # situation documents the answer -- Claude Code's matcher is an
    # unanchored regex, and "Edit" matches as a SUBSTRING of "MultiEdit", so
    # this hook is already invoked for MultiEdit calls under the registered
    # matcher. Kept consistent with that established, repo-wide convention
    # rather than widening this one hook's registry entry alone.
    if tool_name == "MultiEdit":
        old = _read_existing_content(file_path)
        if old is None:
            sys.exit(0)
        current = old
        for edit in tool_input.get("edits", []):
            old_string = str(edit.get("old_string", ""))
            new_string = str(edit.get("new_string", ""))
            if old_string in current:
                current = current.replace(old_string, new_string, 1)
        signals = _weakening_signals(old, current)
        if signals:
            _emit_block(signals)
        sys.exit(0)

    if tool_name == "Write":
        old = _read_existing_content(file_path)
        new = str(tool_input.get("content", ""))
        if old is None:
            # Brand-new file: still check structural validity (flag 2 only --
            # there is no "old" to re-seal against).
            new_fields = _extract_flat_fields(new)
            if _is_true(new_fields.get("consumed")) and not new_fields.get("opened_at"):
                _emit_block(
                    [
                        "structurally invalid consumption: consumed=true but opened_at "
                        "is not set -- a holdout can only be consumed by being opened"
                    ]
                )
            sys.exit(0)
        signals = _weakening_signals(old, new)
        if signals:
            _emit_block(signals)
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    # WHY fail_closed=True: same reasoning as promotion_gate_guard.py -- this hook
    # exists specifically to deny a re-seal/invalid-consumption write; a crash or
    # hang mid-comparison must not silently let it through.
    hook_main(main, fail_closed=True)
