#!/usr/bin/env python3
"""SubagentStop hook: enforce the Evaluator-Optimizer cap=3 iteration limit.

WHY: CLAUDE.md and reviewer.md define a hard cap — after 3 reviewer→builder
cycles without LGTM, escalate to the user, never start a 4th silently. But this
lived only in prompts: an isolated reviewer agent cannot count its own prior
iterations. Enforcement needs persistent state across subagent runs.

This hook keeps a per-session counter of consecutive non-LGTM reviewer verdicts.
LGTM resets it; NEEDS_WORK/BLOCK increments. At >=3 it emits an escalation nudge.

Closes gap #1 of the self-fix hardening plan. Soft nudge (never blocks).
Honest limitation: relies on the reviewer emitting a `VERDICT:` line (reviewer.md
format). Agents that don't follow the contract are invisible to this counter.

Fires on: SubagentStop. State: <cwd>/.claude/state/eo_loop.json
"""

import json
import os
import re
import sys
from pathlib import Path

CAP = 3
_VERDICT_RE = re.compile(r"VERDICT:\s*(LGTM|NEEDS_WORK|BLOCK)", re.IGNORECASE)


def _state_path() -> Path:
    return Path.cwd() / ".claude" / "state" / "eo_loop.json"


def _load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(path: Path, state: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass  # WHY: best-effort state; never break on write failure


def _extract_verdict(text: str) -> str | None:
    """Return LGTM | NEEDS_WORK | BLOCK from a reviewer message, or None."""
    m = _VERDICT_RE.search(text or "")
    return m.group(1).upper() if m else None


def _next_count(prev: int, verdict: str) -> int:
    """LGTM resets the loop; any failing verdict extends it."""
    if verdict == "LGTM":
        return 0
    return prev + 1


def _should_escalate(count: int) -> bool:
    return count >= CAP


def main() -> None:
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    message = data.get("last_assistant_message", "")
    verdict = _extract_verdict(message)
    if verdict is None:
        sys.exit(0)  # not a reviewer-style output — ignore

    session = data.get("session_id", "default")
    state_path = _state_path()
    state = _load_state(state_path)

    prev = int(state.get(session, 0))
    count = _next_count(prev, verdict)
    state[session] = count
    _save_state(state_path, state)

    if not _should_escalate(count):
        sys.exit(0)

    msg = (
        f"[iteration-guard] 🛑 Evaluator-Optimizer cap reached: {count} consecutive "
        f"non-LGTM reviewer verdicts (limit {CAP}).\n"
        "→ Do NOT start another reviewer→builder cycle silently. Escalate to the user: "
        "report what changed across the cycles and what is still blocked. "
        "Repeated fixing past the cap usually means the approach is wrong, not the code."
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


if __name__ == "__main__":
    main()
