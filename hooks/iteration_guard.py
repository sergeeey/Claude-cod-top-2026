#!/usr/bin/env python3
"""Enforce the Evaluator-Optimizer cap=3 iteration limit.

WHY: CLAUDE.md and reviewer.md define a hard cap — after 3 reviewer→builder
cycles without LGTM, escalate to the user, never start a 4th silently. But this
lived only in prompts: an isolated reviewer agent cannot count its own prior
iterations. Enforcement needs persistent state across subagent runs.

This hook keeps a per-session counter of consecutive non-LGTM reviewer verdicts.
LGTM resets it; NEEDS_WORK/BLOCK increments.

Two enforcement legs (2026-07-07, cross-model audit gap #8 -- "cap=3 not
enforced, only additionalContext on the 4th cycle" -- closed per explicit user
decision: "should block, not just warn"):

  1. SubagentStop: updates the counter and, at >=3, emits an immediate
     additionalContext nudge right when the offending cycle's subagent stops.
  2. PreToolUse(Agent): the actual gate. Denies the NEXT Agent(subagent_type=
     reviewer|builder) call outright (permissionDecision: deny) while the
     counter is still >=3, so the orchestrator cannot silently start a 4th
     cycle. Uses the same permissionDecision:deny mechanism this repo already
     relies on in production for Bash (see pre_commit_guard.py, utils.py's
     emit_permission_decision) -- per Claude Code's tools-reference docs this
     also applies to the Agent tool, though that specific claim is
     [HYPOTHESIS, external-docs-sourced] pending a live end-to-end
     confirmation in this repo (rewriting the Agent's input is NOT supported,
     per agent_context_filter.py's own docstring, but denying the call
     outright is a documented, separate capability).

Honest limitation: relies on the reviewer emitting a `VERDICT:` line (reviewer.md
format). Agents that don't follow the contract are invisible to this counter.
The gate only scopes to subagent_type in {reviewer, builder} -- other agent
types (explorer, tester, boyko-agent, ...) are never blocked by this.

Fires on: SubagentStop, PreToolUse(Agent). State: <cwd>/.claude/state/eo_loop.json
"""

import hashlib
import json
import os
import re
import sys

from hook_state import HookState
from lib.runtime import hook_main

CAP = 3
_VERDICT_RE = re.compile(r"VERDICT:\s*(LGTM|NEEDS_WORK|BLOCK)", re.IGNORECASE)
_CYCLE_AGENTS = frozenset({"reviewer", "builder"})

# WHY (F-04, security audit 2026-07-12): the counter in eo_loop.json is a
# plain, unprotected JSON file writable by the exact Write/Edit/Bash tool
# surface this cap is meant to constrain -- an agent can trivially reset it
# to 0 by editing/deleting the file. This is NOT a hard security boundary
# against a determined agent with shell access (that's an inherent property
# of any guard running on the same machine as the thing it guards, not fixable
# here) -- it raises the bar against ACCIDENTAL/CASUAL tampering (a stray
# `Edit` on the state file, a copy-pasted example value) and makes THAT class
# detectable rather than silent. On mismatch, fail CLOSED (treat as at-cap),
# never open (never trust an unsigned/mismatched count), matching this
# repo's stated fail-open-only-for-corruption (not fail-open-for-tampering)
# convention.
#
# CORRECTION (2026-08-29, /boyko-project-radar autonomy-subsystem scan +
# independent tool-verification): an earlier version of this comment claimed
# "deliberate tampering detectable rather than silent" without qualification.
# That overclaims what a hardcoded, source-readable salt can do. `_SIG_SALT`
# below is a literal string in this file -- any agent with Read access (this
# repo's own settings.json grants Read(*)/Bash(*) globally) can compute a
# valid {count, sig} pair for any count it wants and forge a fresh entry that
# is INDISTINGUISHABLE from one this hook wrote itself. This is a checksum
# against naive/accidental corruption, NOT a security boundary against the
# agent whose behavior it constrains -- that would require the count to live
# somewhere the agent cannot both read and write (a different OS principal,
# an external service, an append-only log it can't rewrite), which this
# single-process/single-principal hook architecture cannot provide on its
# own. Moving the salt to a file instead of a literal would not fix this:
# the same Read(*) access that lets an agent see this docstring lets it see
# any file colocated with it.
#
# NOTED (2026-08-29, independent security-audit review): `_SIG_SALT` is
# shared by every project using this hook. If it's ever changed (version
# bump, refactor), every currently-outstanding {count, sig} entry across
# every such project fails its signature check on next read and gets
# force-set to CAP (see the fail-closed comment above) -- indistinguishable
# from real tampering, and recovery needs a new session_id or a manual
# state-file edit, not an in-session LGTM (PreToolUse would deny the very
# reviewer/builder call needed to produce one). Mild impact, matches this
# file's already-accepted "extra required LGTM" tradeoff elsewhere.
# git log confirms this salt has never actually changed since introduction --
# untriggered so far, not observed in practice.
_SIG_SALT = "iteration_guard.eo_loop.v1"


def _sign(session: str, count: int) -> str:
    return hashlib.sha256(f"{session}:{count}:{_SIG_SALT}".encode()).hexdigest()[:16]


def _extract_verdict(text: str) -> str | None:
    """Return LGTM | NEEDS_WORK | BLOCK from a reviewer message, or None."""
    m = _VERDICT_RE.search(text or "")
    return m.group(1).upper() if m else None


def _next_count(prev: int, verdict: str) -> int:
    """LGTM resets the loop; any failing verdict extends it."""
    if verdict == "LGTM":
        return 0
    return prev + 1


def _lgtm_follows_stale_tests() -> bool:
    """True if commit_test_gate.py's own state shows source edited after the
    last test run for this working directory.

    WHY (bottleneck #1, /boyko-project-radar autonomy-subsystem scan,
    2026-08-29): this hook and commit_test_gate.py are independent silos --
    a reviewer can emit VERDICT: LGTM (resetting this cap to 0) on code
    edited AFTER the last pytest run, and neither hook ever surfaces that.
    Read-only cross-check against the sibling hook's own state file; does
    NOT write to it, and does NOT override the reviewer's verdict -- a
    human reviewer choosing LGTM is not this hook's call to second-guess,
    it only makes the staleness visible instead of silent.

    KNOWN SCOPE LIMIT (found in review, not yet fixed): HookState is always
    <Path.cwd()>/.claude/state/<name>.json (hook_state.py). `builder`/
    `tester` declare `isolation: worktree` (agents/builder.md,
    agents/tester.md) and so run -- and stamp commit_test_gate's state --
    from a DIFFERENT cwd (`.claude/worktrees/<id>/`) than the non-isolated
    `reviewer` whose SubagentStop fires this check from the main repo cwd.
    In that flow this reads the orchestrator's own main-repo state, not the
    worktree's -- it can go silent (no warning even though the reviewed
    code is genuinely untested) or, less likely, fire on unrelated activity
    in the main repo. Verified accurate for the common non-worktree case
    (everything in one cwd, as this repo's own sessions typically run);
    not yet extended to cross-worktree state resolution.
    """
    try:
        cts_state = HookState("commit_test_gate")
        last_edit = float(str(cts_state.get("last_edit", 0) or 0))
        last_test = float(str(cts_state.get("last_test", 0) or 0))
    except Exception:
        return False  # missing/corrupt sibling state -- not this hook's concern
    return last_edit > last_test


def _should_escalate(count: int) -> bool:
    return count >= CAP


def _extract_subagent_type(tool_input: dict) -> str:
    """Same field-name fallback as agent_context_filter.py's _extract_subagent
    -- the Agent tool has used different key names across SDK versions."""
    for key in ("subagent_type", "agent_type", "agent", "type"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value.strip().lower()
    return ""


def _get_session_count(data: dict, state: HookState) -> tuple[str, int]:
    """Return (session_id, current count).

    Only two outcomes now (revised after self-review caught a real bypass in
    an earlier draft of this fix, F-04, security audit 2026-07-12):
    - Missing entry -- count=0. Never recorded yet, legitimately zero, not
      an attack: a fresh session_id can't collide with prior state.
    - Present entry -- trust ONLY a correctly-signed {count, sig} dict.
      Anything else (a bare int, a string, a dict missing "sig", a wrong
      signature) fails CLOSED to CAP.

    NOTE (2026-07-19, hook_state.py pruning): "missing entry" can now ALSO mean
    a real, long-lived session whose entry aged out of eo_loop.json's cap
    (HookState.DEFAULT_MAX_ENTRIES=50) because 50 other sessions churned
    through since it last touched this file -- not only "brand new session."
    This resets that session's cycle counter to 0, the same permissive path.
    Accepted tradeoff (growth-bound state > perfect cap accuracy for a rarely
    -hit edge): worst case is one extra allowed reviewer/builder cycle for a
    session that was already at the cap, not a security regression.

    WHY no "legacy bare-int" trust path (removed from an earlier draft of
    this exact fix): a bare int is indistinguishable from `Write(".claude/
    state/eo_loop.json", '{"sess1": 0}')` -- exactly the reset-to-zero
    attack this fix exists to close. The "backward compat for pre-fix
    files" justification for trusting it doesn't hold up: session_id is
    fresh per session (see `data.get("session_id", "default")` above), so a
    genuinely pre-existing legacy entry can only collide with a NEW
    session's state in the single-session-spans-the-upgrade edge case --
    and even there, failing closed (one extra required LGTM) is a mild
    inconvenience, not a break, versus silently accepting the exact shape
    of the intended attack.
    """
    session = data.get("session_id", "default")
    raw = state.get(session)
    if raw is None:
        return session, 0  # never recorded yet — legitimately zero, not tampered
    if isinstance(raw, dict) and "count" in raw and "sig" in raw:
        try:
            count = int(raw["count"])
        except (TypeError, ValueError):
            pass  # falls through to the fail-closed return below
        else:
            if _sign(session, count) == raw.get("sig"):
                return session, count
    print(
        f"[iteration-guard] state integrity check failed for session "
        f"{session!r} -- eo_loop.json entry present but not a validly-"
        f"signed {{count, sig}} value (resembles a hand edit or bypass "
        f"attempt, not this hook's own write). Treating as tampered: "
        f"forcing count to cap ({CAP}) rather than trusting an unsigned "
        f"value.",
        file=sys.stderr,
    )
    return session, CAP  # fail CLOSED — never trust an unsigned/malformed entry


def _handle_subagent_stop(data: dict) -> None:
    message = data.get("last_assistant_message", "")
    verdict = _extract_verdict(message)
    if verdict is None:
        sys.exit(0)  # not a reviewer-style output — ignore

    state = HookState("eo_loop")
    session, prev = _get_session_count(data, state)
    count = _next_count(prev, verdict)
    state[session] = {"count": count, "sig": _sign(session, count)}
    state.save()

    if not _should_escalate(count):
        if verdict == "LGTM" and _lgtm_follows_stale_tests():
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "SubagentStop",
                            "additionalContext": (
                                "[iteration-guard] ⚠️ LGTM verdict follows source "
                                "changes made AFTER the last recorded test run "
                                "(per commit_test_gate.py's last_edit/last_test "
                                "timestamps) -- this LGTM may be certifying code "
                                "that was never actually re-tested. The cycle "
                                "counter was still reset (a reviewer's LGTM is "
                                "not overridden by this check) -- but re-run "
                                "tests before treating this as verified."
                            ),
                        }
                    }
                )
            )
        sys.exit(0)

    msg = (
        f"[iteration-guard] 🛑 Evaluator-Optimizer cap reached: {count} consecutive "
        f"non-LGTM reviewer verdicts (limit {CAP}).\n"
        "→ Do NOT start another reviewer→builder cycle silently. Escalate to the user: "
        "report what changed across the cycles and what is still blocked. "
        "Repeated fixing past the cap usually means the approach is wrong, not the code. "
        "The next reviewer/builder Agent call will be blocked until the counter resets."
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SubagentStop",
                    "additionalContext": msg,
                }
            }
        )
    )


def _handle_pre_tool_use(data: dict) -> None:
    tool_name = data.get("tool_name", "")
    if tool_name != "Agent":
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    subagent = _extract_subagent_type(tool_input)
    if subagent not in _CYCLE_AGENTS:
        sys.exit(0)  # only the reviewer<->builder pair is gated

    state = HookState("eo_loop")
    _session, count = _get_session_count(data, state)

    if not _should_escalate(count):
        sys.exit(0)  # cap not reached yet — allow

    reason = (
        f"[iteration-guard] Evaluator-Optimizer cap reached: {count} consecutive "
        f"non-LGTM reviewer verdicts (limit {CAP}). Blocking this {subagent} call.\n"
        "Do NOT start another reviewer<->builder cycle silently — escalate to the "
        "user: report what changed across the cycles and what is still blocked. "
        "Repeated fixing past the cap usually means the approach is wrong, not the "
        "code. This gate stays closed until an LGTM verdict resets the counter, "
        "or a new session starts."
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def main() -> None:
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    # WHY this discriminator: PreToolUse/PostToolUse payloads always carry
    # tool_name; SubagentStop payloads never do (they carry
    # last_assistant_message/session_id instead). tool_response would also
    # distinguish Pre from Post, but this hook is only registered for
    # PreToolUse(Agent), not PostToolUse, so that split isn't needed here.
    if "tool_name" in data:
        _handle_pre_tool_use(data)
    else:
        _handle_subagent_stop(data)


if __name__ == "__main__":
    # WHY fail_closed=True (Gate 12a, 2026-08-28: this hook previously ran
    # main() bare -- no timeout protection, and an uncaught exception in
    # _handle_pre_tool_use would crash silently via Python's default
    # traceback-to-stderr path, which PreToolUse's protocol ignores (see
    # hooks/CLAUDE.md's blocking protocol -- only stdout JSON blocks, not
    # exit code). This hook's PreToolUse leg exists specifically to DENY the
    # 4th reviewer<->builder cycle once the Evaluator-Optimizer cap is hit;
    # a crash/hang there must not silently allow the very Agent call this
    # hook exists to block.
    hook_main(main, fail_closed=True)
