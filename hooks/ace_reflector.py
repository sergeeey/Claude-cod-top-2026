#!/usr/bin/env python3
"""PreToolUse(Agent) + SubagentStop hook: ACE Reflector — incremental playbook learning.

Based on: ACE (Agentive Context Engineering), arXiv:2510.04618
WHY: pattern_extractor fires only on fix: commits. ACE Reflector fires on
every SubagentStop, capturing approach effectiveness across ALL task types.
Delta updates (not full rewrites) preserve accumulated knowledge across sessions.

ACE roles mapped to our system:
  Generator  → builder/explorer/tester agents
  Reflector  → this hook
  Curator    → playbook.md (sorted by net score: helpful - harmful)

WHY outcome detection was rewritten (2026-07-09, /boyko-specialist audit
against arXiv:2605.30621 "Harness Updating Is Not Harness Benefit"): the
original _extract_outcome() classified success/failure by keyword-matching
the AGENT'S OWN closing message ("completed"/"done" vs "error:"/"failed") --
pure self-reported narrative, never externally verified. An agent that says
"Fixed the bug! Completed." with a hidden logic error scored helpful+1; an
agent that honestly reports "error: file not found" scored harmful+1 even
though honest failure reporting is correct behavior. This is exactly the
Validation Theater pattern from audit-verification-gate.md, running
automatically inside the self-learning loop instead of a one-off session.

Fix: outcome is now read from commit_test_gate.py's ALREADY-EXTERNALLY-
VERIFIED state (<cwd>/.claude/state/commit_test_gate.json) -- its `last_test`
is only stamped after a REAL pytest run with exit_code==0, and `last_edit`
after a real source .py edit. This hook now only asks: did a verified test
pass, or an unverified source edit, happen AFTER this specific subagent's
turn started? Registered on TWO events (mode-dispatched by payload shape,
same discriminator iteration_guard.py already uses):
  PreToolUse(Agent)  -> stamp this session's turn-start timestamp
  SubagentStop       -> compare commit_test_gate's timestamps against it

Known limitations (both pre-existing properties of HookState/commit_test_gate
this hook now depends on, not introduced by this fix -- flagged by cross-model
review, 2026-07-09, not silently patched here since fixing either means
changing shared behavior for every hook that uses HookState):
1. Keyed by session_id, not per-invocation id (shared with iteration_guard.py's
   eo_loop counter). Two Agent calls running in parallel in the same session
   will overwrite each other's turn-start stamp -- the later start wins for
   both.
2. HookState resolves its path from Path.cwd() at construction time -- if the
   working directory changes between when commit_test_gate.py stamps
   last_edit/last_test and when this hook reads them, they resolve to
   DIFFERENT state files and the signal is silently lost (outcome -> None).
   commit_test_gate.py already has this same exposure between its own
   last_edit and last_test stamps; this hook inherits it, not adds it.
3. commit_test_gate.json's last_test/last_edit are GLOBAL per-cwd keys, not
   session-scoped (unlike this hook's own ace_reflector_turns.json, which
   IS keyed by session_id). If two Claude Code sessions run concurrently in
   the same working directory, a real test pass triggered by session B can
   get credited as "helpful" to session A's turn, since _determine_outcome
   only compares timestamps, not session identity (flagged by reviewer
   agent, 2026-07-09). Accepted as a known limitation, not fixed here:
   this is a soft, best-effort learning signal feeding playbook.md
   rankings, not a security or correctness gate -- and the fix would mean
   adding session-scoping to commit_test_gate.py's shared state schema,
   which other hooks also read/write. Low practical impact: most sessions
   don't share a cwd with another concurrently-running session.

FIXED (2026-07-17, coherence audit): a 4th issue, distinct from the 3 above --
not a signal-loss/race bug but a DESIGN BIAS in how "harmful" was scored.
_determine_outcome's "harmful" fires whenever a source edit happened with NO
verified test pass in the SAME turn. That penalizes this repo's own
build-squad pattern by construction: builder edits in its own worktree,
tester verifies SEPARATELY in a different worktree/turn. Every clean
builder-only turn scored "harmful" purely because verification hadn't
happened YET in that exact turn -- not because the edit was bad. playbook.md
showed this directly: "general: helpful 2, harmful 640" before this fix,
almost entirely this false signal rather than 640 real failures.

Fix: main() no longer records "harmful" immediately. An edit-only turn is
appended to a pending queue (ace_reflector_pending.json) instead. Every
subsequent hook firing sweeps that queue against the latest last_test: an
entry resolves to "helpful" the moment ANY later verified pass happens
(typically a separate tester turn), or falls back to the original immediate
"harmful" after PENDING_EXPIRY_SECONDS with still no verification -- a
genuinely abandoned edit, not a healthy split workflow. _determine_outcome
itself is UNCHANGED (still returns immediate 'helpful'/'harmful'/None) --
only main()'s interpretation of its 'harmful' result changed, from "record
now" to "defer and re-check later".
"""

import sys
import time
from pathlib import Path

from hook_state import HookState
from utils import file_lock, hook_main, parse_stdin

PLAYBOOK_PATH = Path.home() / ".claude" / "memory" / "_auto" / "playbook.md"
# WHY (F-09, security audit 2026-07-12): PLAYBOOK_PATH is a GLOBAL,
# machine-wide path -- concurrent Claude Code sessions can race on the
# unlocked load-mutate-save in main(), silently dropping one session's
# helpful/harmful counter increment. Reuses file_lock(), same primitive
# already used 6x elsewhere in this repo (expert_registry.py, etc.). Lock
# path is derived from PLAYBOOK_PATH at call time inside main(), not as a
# module-level constant -- existing tests monkeypatch PLAYBOOK_PATH to a
# tmp_path, and a constant computed at import time would miss that.
MIN_RESPONSE_LEN = 30
MAX_ENTRIES = 50  # WHY: prevent unbounded growth — keep only top-N by net score
PENDING_EXPIRY_SECONDS = 7200  # WHY 2h: long enough for a separate tester turn
# to follow builder's, short enough that a genuinely abandoned edit still
# resolves to "harmful" instead of sitting in pending forever.
MAX_PENDING = 200  # WHY: same unbounded-growth guard as MAX_ENTRIES, applied
# to the pending queue instead of the playbook itself.

_TURN_STATE_NAME = "ace_reflector_turns"
_COMMIT_TEST_GATE_STATE_NAME = "commit_test_gate"
_PENDING_STATE_NAME = "ace_reflector_pending"


# --- Approach classification --------------------------------------------------

_APPROACH_KEYWORDS: list[tuple[str, list[str]]] = [
    ("test-driven", ["pytest", "assert", "test_", "failing test"]),
    ("search-first", ["grep", "glob", "rg ", "find ", "search"]),
    ("explore-first", ["read", "explore", "understand", "context"]),
    ("direct-implementation", ["edit", "write", "create", "implement", "add "]),
    ("debug", ["traceback", "error", "fix", "diagnose", "root cause"]),
]


def _classify_approach(message: str) -> str:
    """Return the dominant approach keyword for this agent run.

    WHY: approach classification aggregates across tasks, not per-task —
    this reveals which workflows succeed most over time (ACE insight).
    """
    msg_lower = message.lower()
    for approach, keywords in _APPROACH_KEYWORDS:
        if any(k in msg_lower for k in keywords):
            return approach
    return "general"


# --- Outcome detection ---------------------------------------------------------


def _stamp_turn_start(session: str) -> None:
    """Record when this session's Agent call started, keyed by session_id."""
    state = HookState(_TURN_STATE_NAME)
    state[session] = time.time()
    state.save()


def _determine_outcome(session: str) -> str | None:
    """Return 'helpful', 'harmful', or None (no verification signal this turn).

    'helpful': a REAL pytest run with exit_code==0 happened after this turn
               started — verified externally by commit_test_gate.py, not by
               this hook or the agent's own words.
    'harmful': a source .py file was edited after this turn started, but no
               verified test pass followed — an unverified change, matching
               commit_test_gate.py's own definition of risk.
    None:      no source edit and no test run this turn — nothing to verify
               (e.g. a read-only/research agent) — stay silent rather than
               fabricate a verdict from message text.
    """
    turn_state = HookState(_TURN_STATE_NAME)
    raw_start = turn_state.get(session)
    if raw_start is None:
        return None
    try:
        turn_start = float(str(raw_start))
    except (TypeError, ValueError):
        return None

    ct_state = HookState(_COMMIT_TEST_GATE_STATE_NAME)
    try:
        last_test = float(str(ct_state.get("last_test", 0) or 0))
        last_edit = float(str(ct_state.get("last_edit", 0) or 0))
    except (TypeError, ValueError):
        return None

    if last_test > turn_start:
        return "helpful"
    if last_edit > turn_start:
        return "harmful"
    return None


def _get_turn_start(session: str) -> float | None:
    """Re-read this session's turn-start stamp (same read _determine_outcome
    does internally, exposed separately so a deferred pending entry can
    record its own turn_start without changing _determine_outcome's
    signature or its existing test coverage)."""
    turn_state = HookState(_TURN_STATE_NAME)
    raw_start = turn_state.get(session)
    if raw_start is None:
        return None
    try:
        return float(str(raw_start))
    except (TypeError, ValueError):
        return None


def _read_last_test() -> float | None:
    """Latest verified-test-pass timestamp from commit_test_gate.json, or
    None if the state is missing/corrupt. Used to sweep the pending queue,
    independent of whether THIS turn's own outcome is helpful/harmful/None."""
    ct_state = HookState(_COMMIT_TEST_GATE_STATE_NAME)
    try:
        return float(str(ct_state.get("last_test", 0) or 0))
    except (TypeError, ValueError):
        return None


# --- Deferred resolution (2026-07-17 fix) -------------------------------------


def _load_pending() -> list[dict]:
    state = HookState(_PENDING_STATE_NAME)
    raw = state.get("entries", [])
    return list(raw) if isinstance(raw, list) else []


def _save_pending(entries: list[dict]) -> None:
    state = HookState(_PENDING_STATE_NAME)
    # WHY trim here, not just at append time: expiry-driven shrinkage in
    # _resolve_pending already keeps steady-state size small, but this is
    # the last line of defense against unbounded growth if sweeping ever
    # stops happening (e.g. a session that never fires this hook again).
    state["entries"] = entries[-MAX_PENDING:]
    state.save()


def _record(playbook: dict, approach: str, outcome: str, example: str = "") -> None:
    """Increment playbook[approach]'s helpful/harmful counter in place."""
    if approach not in playbook:
        playbook[approach] = {"helpful": 0, "harmful": 0, "example": ""}
    if outcome == "helpful":
        playbook[approach]["helpful"] += 1
        if example:
            playbook[approach]["example"] = example
    else:
        playbook[approach]["harmful"] += 1


def _resolve_pending(
    pending: list[dict], playbook: dict, now: float, last_test: float
) -> list[dict]:
    """Resolve deferred edit-only turns against the latest verified test pass.

    An entry resolves to 'helpful' the moment ANY later verified pass
    happens — typically a separate agent's turn (tester, after builder),
    matching this repo's own build-squad split-worktree pattern.
    commit_test_gate.json has no session dimension (limitation #3 above), so
    this deliberately allows cross-session/cross-agent resolution — the same
    trade-off already accepted for immediate 'helpful' detection.

    An entry still unresolved after PENDING_EXPIRY_SECONDS resolves to
    'harmful', preserving the original conservative default for edits that
    genuinely never got verified — not silently forgiven forever.
    """
    still_pending = []
    for entry in pending:
        turn_start = entry.get("turn_start") or 0
        if last_test > turn_start:
            _record(playbook, entry.get("approach", "general"), "helpful", entry.get("example", ""))
        elif now - (entry.get("stamped_at") or now) > PENDING_EXPIRY_SECONDS:
            _record(playbook, entry.get("approach", "general"), "harmful")
        else:
            still_pending.append(entry)
    return still_pending


# --- Playbook I/O ------------------------------------------------------------


def _load_playbook() -> dict[str, dict]:
    """Parse playbook.md into {approach: {helpful, harmful, example}}."""
    if not PLAYBOOK_PATH.exists():
        return {}

    entries: dict[str, dict] = {}
    current_key: str | None = None

    for line in PLAYBOOK_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("### "):
            current_key = line[4:].strip()
            entries[current_key] = {"helpful": 0, "harmful": 0, "example": ""}
        elif current_key:
            if line.startswith("- helpful:"):
                try:
                    entries[current_key]["helpful"] = int(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass
            elif line.startswith("- harmful:"):
                try:
                    entries[current_key]["harmful"] = int(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass
            elif line.startswith("- example:"):
                entries[current_key]["example"] = line.split(":", 1)[1].strip()

    return entries


def _save_playbook(entries: dict[str, dict]) -> None:
    """Write playbook.md, sorted by net score (helpful - harmful) descending."""
    PLAYBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)

    # WHY: net score = helpful - harmful. High net score = reliably effective approach.
    ranked = sorted(
        entries.items(),
        key=lambda x: x[1].get("helpful", 0) - x[1].get("harmful", 0),
        reverse=True,
    )

    lines = [
        "# ACE Playbook\n\n",
        "_Auto-generated by ace_reflector.py. Delta updates only — do not hand-edit._\n\n",
    ]
    for key, data in ranked[:MAX_ENTRIES]:
        lines.append(f"### {key}\n")
        lines.append(f"- helpful: {data.get('helpful', 0)}\n")
        lines.append(f"- harmful: {data.get('harmful', 0)}\n")
        lines.append(f"- example: {data.get('example', '')}\n")
        lines.append("\n")

    PLAYBOOK_PATH.write_text("".join(lines), encoding="utf-8")


# --- Main --------------------------------------------------------------------


def main() -> None:
    data = parse_stdin()

    # WHY this discriminator: PreToolUse payloads always carry tool_name;
    # SubagentStop payloads never do (they carry last_assistant_message/
    # session_id instead). Same convention as iteration_guard.py.
    if "tool_name" in data:
        if data.get("tool_name") == "Agent":
            session = data.get("session_id", "default")
            _stamp_turn_start(session)
        sys.exit(0)

    # WHY outcome is checked BEFORE the message-length gate (cross-model
    # review, 2026-07-09): the old order let a terse agent message ("Done.")
    # skip outcome recording even when a REAL verified test pass happened
    # this turn -- the external-verification fix would have been silently
    # defeated by message length instead of message keywords. Length only
    # gates approach classification (which genuinely needs message text to
    # be meaningful), never outcome detection (which never reads the
    # message at all).
    session = data.get("session_id", "default")
    outcome = _determine_outcome(session)

    message: str = data.get("last_assistant_message", "")
    approach = _classify_approach(message) if len(message) >= MIN_RESPONSE_LEN else "general"
    example = message.strip().split("\n")[0][:120] if message.strip() else ""

    # WHY the lock wraps the FULL load-mutate-save (F-09): locking only the
    # final _save_playbook() would still let two concurrent sessions both
    # load the "before" entries, then race to save -- one counter increment
    # silently lost. Fail-open on timeout (skip, exit 0): a missed telemetry
    # increment is acceptable, a hung hook call is not (this file has no
    # security consequence -- it's a learning scoreboard, per the audit).
    with file_lock(PLAYBOOK_PATH.with_suffix(".lock"), timeout=5.0) as acquired:
        if not acquired:
            sys.exit(0)
        entries = _load_playbook()

        # WHY sweep unconditionally, even when THIS turn's own outcome is
        # None (2026-07-17 fix): a read-only/research turn's SubagentStop
        # can still be the moment that resolves ANOTHER agent's pending
        # entry -- e.g. tester's own SubagentStop, firing after builder's
        # earlier edit-only turn already deferred itself. WHY guard writes
        # on "did anything actually change": preserves the pre-fix contract
        # that a turn with zero verifiable signal (outcome is None, nothing
        # pending to resolve) never touches playbook.md/pending state at
        # all, not even to write back unchanged/empty data.
        last_test = _read_last_test()
        pending = _load_pending()
        pending_before = len(pending)
        if last_test is not None:
            pending = _resolve_pending(pending, entries, time.time(), last_test)
        resolved_count = pending_before - len(pending)  # entries a sweep recorded+removed
        playbook_changed = resolved_count > 0

        status = None
        if outcome == "helpful":
            # WHY: delta update — increment only the relevant counter, not
            # rewrite. This is the key ACE insight: local edits preserve
            # past learning.
            _record(entries, approach, "helpful", example)
            status = "helpful+1"
            playbook_changed = True
        elif outcome == "harmful":
            # WHY deferred, not recorded immediately (2026-07-17 fix): see
            # module docstring "FIXED" section. This repo's own build-squad
            # splits edit (builder) and verify (tester) into separate
            # worktree-isolated turns by design -- recording "harmful" the
            # instant an edit-only turn ends punished that split on sight,
            # regardless of whether the edit was actually fine. Defer to
            # the pending queue; _resolve_pending promotes it to "helpful"
            # the moment a later verified pass exists, or lets it expire to
            # "harmful" after PENDING_EXPIRY_SECONDS with none.
            pending.append(
                {
                    "session": session,
                    "approach": approach,
                    "turn_start": _get_turn_start(session),
                    "example": example,
                    "stamped_at": time.time(),
                }
            )
            status = "deferred (awaiting later verification)"

        # WHY not a length comparison here (would false-negative if a sweep
        # removed N and the harmful branch appended N in the same pass):
        # track explicitly instead -- pending changed iff a sweep resolved
        # anything OR this turn appended a new deferred entry.
        pending_changed = resolved_count > 0 or outcome == "harmful"
        if pending_changed:
            _save_pending(pending)
        if playbook_changed:
            _save_playbook(entries)

    if status:
        print(
            f"[ace-reflector] {status} | approach={approach} | outcome-source=commit_test_gate",
            file=sys.stderr,
        )
    sys.exit(0)


if __name__ == "__main__":
    hook_main(main)
