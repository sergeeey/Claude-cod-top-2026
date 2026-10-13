#!/usr/bin/env python3
"""PostModelSwitch hook — append-only record of every session model change.

WHY this exists: `hooks/resource_router.py` predicts a tier (T0-T3) and
recommends a model in prose, and nothing anywhere records which model the
session ACTUALLY ended up on. So the router has never been checkable: a
recommendation that is routinely ignored, and one that is routinely followed,
produce the identical advisory text and leave the identical trace (none).
This hook supplies the second half of that pair -- the observed side.

WHY PostModelSwitch and NOT PreModelSwitch: PreModelSwitch can block a switch
with exit code 2. Blocking is more authority than a measurement needs, and
wiring a blocking hook before there is any data on how often switches even
happen would be deciding the answer before running the experiment. This hook
observes and never blocks. If the data later justifies enforcement,
PreModelSwitch is a separate change with its own evidence.

WHY it captures switches Claude Code makes on its own: the docs state
PostModelSwitch also fires for changes Claude Code initiates -- restoring a
model when a session resumes, for instance. Those are exactly the transitions a
human would never think to record, and they change what model a task actually
ran on just as much as a deliberate switch does.

Deliberately NOT correlated with the router's prediction here: the router does
not log its verdict yet, so there is nothing to join against. Adding that write
touches a live advisory path and is a separate change (one fix per PR). Until
then this log stands alone and answers a narrower but still real question -- how
often the model changes, in which direction, and whether Claude Code or a human
initiated it.

Timeout: PostModelSwitch fires asynchronously with a reduced 30 s default,
which is `hook_main`'s default, so no override is needed.

Log format: ~/.claude/logs/model_switches.jsonl (one JSON line per switch).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from lib.state import rotate_log_if_large

LOG_FILE = Path.home() / ".claude" / "logs" / "model_switches.jsonl"


def main() -> None:
    # WHY: same recursion guard as model_usage_tracker.py -- a switch that
    # happens inside a subagent invocation would otherwise be recorded twice,
    # once by the subagent's own hook process and once by the parent's.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        return

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        return

    from_model = data.get("from_model")
    to_model = data.get("to_model")

    # WHY skip when to_model is absent rather than logging a null: a row that
    # cannot say what the model became answers no question this log exists for,
    # and silently-null rows are how a telemetry file becomes untrustworthy.
    if not to_model:
        return

    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "sid": (data.get("session_id") or "")[:8],
        "from_model": from_model,
        "to_model": to_model,
        # WHY record this explicitly instead of inferring it later: "no previous
        # model" is the shape of a session start or a resume-restore, and it is
        # NOT the same event as a human switching mid-task. Deriving that
        # distinction from a null months later is guesswork; recording it now is
        # one boolean.
        "is_initial": from_model is None,
        "cwd": data.get("cwd"),
    }

    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        rotate_log_if_large(LOG_FILE)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        # Telemetry is never worth failing a session over.
        pass


if __name__ == "__main__":
    from lib.runtime import hook_main

    hook_main(main)
