#!/usr/bin/env python3
"""PostToolUse(Edit|Write) hook: nudge to escalate from local-fix tunnel vision.

WHY: an agent stuck re-editing ONE file is the "нервное окончание" failure mode
— treating a symptom of a larger structure as an isolated local bug. Repeated
local patching that doesn't stick usually means the cause is elsewhere
(симптом ≠ причина). This is the detection/forcing half of the MACROSCOPE goal:
the analysis half is the `macro-locality` skill + `hd-mavp-router` Locality
Triage (Шаг -1); a skill can't reliably fire itself, so the "when to escalate"
signal belongs in a hook (deterministic, event-driven), not in skill prose.

Detection: per-session count of edits to the same file_path. At the threshold,
emit ONE soft nudge for that file (never repeated — nagging erodes trust, per
skeptic-triggers.md § Calibration), pointing at the macro-locality diagnosis.

Honest limitation: raw re-edit count is a [WEAK] proxy. A legitimately
churn-heavy file (a big refactor) will cross the threshold without any hidden
macrostructure — hence a soft, dismissible, once-per-file nudge, never a block.
THRESHOLD is a heuristic chosen for precision over recall, not a calibrated
constant (no outcomes ledger exists to tune it — same honesty as
skeptic-triggers.md's 2.5× constant).

Does NOT block: PostToolUse fires after the edit already happened; this only
injects additionalContext. State: <cwd>/.claude/state/locality_escalation_guard.json
"""

from __future__ import annotations

import os
import sys

from hook_state import HookState
from utils import emit_hook_result, log_hook_trigger, parse_stdin

HOOK_NAME = "locality_escalation_guard"

# WHY [WEAK]: 4, not 3 — three edits to one file is ordinary iterative work and
# would nag constantly (false positive). Four begins to look like churn without
# progress. Tunable; no ground-truth ledger backs the exact value.
THRESHOLD = 4

# WHY both: Edit re-touches, Write re-writes; repeated Write to one path is the
# same "can't get this file right" signal as repeated Edit.
_TRACKED_TOOLS = frozenset({"Edit", "Write"})


def process_edit(session_state: dict, path: str, threshold: int) -> tuple[dict, bool]:
    """Pure core (no I/O — unit-testable): fold one edit into per-session state.

    Returns (updated_state, should_nudge). should_nudge is True exactly once per
    file — on the edit that first reaches `threshold`. A file already nudged, or
    below threshold, returns False.
    """
    # WHY defensive isinstance coercion, not a bare .get(): state files in this
    # repo DO get corrupted/hand-edited (observed: a legacy bare-int eo_loop.json
    # + leaked "sess1" test fixture fail-closing iteration_guard). For an advisory
    # nudge the right response to a malformed prior value is fail-open — treat it
    # as fresh — never crash the hook on the edit that triggered it.
    counts_raw = session_state.get("counts", {})
    counts = dict(counts_raw) if isinstance(counts_raw, dict) else {}
    nudged_raw = session_state.get("nudged", [])
    nudged = list(nudged_raw) if isinstance(nudged_raw, list) else []
    prev = counts.get(path, 0)
    # WHY `not isinstance(prev, bool)`: bool is a subclass of int in Python, so a
    # hand-corrupted JSON `true` would pass a bare isinstance(prev, int) and become
    # 2 instead of resetting — violating this function's own "malformed → fresh"
    # intent. JSON true/false round-trip to Python bool, so reject them explicitly.
    prev_int = prev if isinstance(prev, int) and not isinstance(prev, bool) else 0
    counts[path] = prev_int + 1
    should_nudge = counts[path] >= threshold and path not in nudged
    if should_nudge:
        nudged.append(path)
    return {"counts": counts, "nudged": nudged}, should_nudge


def _nudge_message(path: str, count: int) -> str:
    return (
        f"[locality-escalation] ✎ {path} edited {count}× this session.\n"
        "Repeated local fixing to one file often means the cause is elsewhere "
        "(симптом ≠ причина). Before the next patch, ask: is this a local bug, "
        "or a symptom of a larger structure you're not seeing?\n"
        "→ Run Locality Triage (hd-mavp-router Шаг -1) or invoke the "
        "`macro-locality` skill to decide: part-of-macrosystem / local-cause / "
        "needs-data / ill-posed.\n"
        "Heuristic threshold [WEAK] — dismiss if this file is legitimately "
        "churn-heavy (a planned refactor is not a hidden macrostructure)."
    )


def main() -> None:
    # WHY: recursion guard — a subagent's own edits must not trip the counter.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    data = parse_stdin()
    if not data:
        sys.exit(0)

    if data.get("tool_name", "") not in _TRACKED_TOOLS:
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    path = tool_input.get("file_path", "")
    if not path:
        sys.exit(0)

    session = data.get("session_id", "default")
    state = HookState(HOOK_NAME)

    raw = state.get(session, {})
    # WHY: tolerate any malformed/hand-edited prior value — state is advisory,
    # a bad entry must never break the edit that triggered this hook.
    session_state = raw if isinstance(raw, dict) else {}

    new_state, should_nudge = process_edit(session_state, path, THRESHOLD)
    state[session] = new_state
    state.save()

    if not should_nudge:
        sys.exit(0)

    count = new_state["counts"][path]
    log_hook_trigger(
        hook_name=HOOK_NAME,
        trigger_type="repeated_local_edit",
        action="warning",
        sample=path,
        session_id=session,
    )
    emit_hook_result("PostToolUse", _nudge_message(path, count))


if __name__ == "__main__":
    main()
