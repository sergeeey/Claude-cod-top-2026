#!/usr/bin/env python3
"""PostToolUse hook for Edit|Write: remind about Plan-First Protocol.

WHY: CLAUDE.md v10.0 requires EnterPlanMode for 3+ files, but the agent may
forget by mid-session. The hook counts unique files and reminds
forcefully — this works at the system level, not "memory".

Mechanism: temp file /tmp/claude_plan_guard_<session>.txt stores paths
of edited files. At >=3 unique files — reminder.

v2: if .claude/plans/ has an active plan file for the current session,
the warning is suppressed — a plan already exists.
"""

import json
import tempfile
import time
from pathlib import Path

from utils import get_tool_input, parse_stdin


def get_tracker_path(session_id: str) -> Path:
    """Get path for session-specific file tracker."""
    # WHY: we use session_id, not PID — PID can be reused,
    # session_id is unique for each Claude Code session
    safe_id = session_id.replace("/", "_").replace("\\", "_")[:32]
    return Path(tempfile.gettempdir()) / f"claude_plan_guard_{safe_id}.txt"


def has_active_plan() -> bool:
    """Check if any plan file exists in .claude/plans/ directory.

    WHY: if a plan already exists (approved or in progress), the warning
    about 3+ files without a plan is a false positive. We check for .md files
    in plans/ as a marker that a plan was created.
    """
    plans_dir = Path.home() / ".claude" / "plans"
    if not plans_dir.exists():
        return False
    # Any .md file modified within the last 24 hours = active plan
    now = time.time()
    for f in plans_dir.glob("*.md"):
        if now - f.stat().st_mtime < 86400:  # 24 hours
            return True
    return False


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    # WHY: we support both formats — nested tool_input and flat (legacy).
    # post_format.py reads file_path from root, but docs describe nesting.
    tool_input = get_tool_input(data)
    file_path = tool_input.get("file_path", "")

    if not file_path:
        return

    # Session tracking
    session_id = data.get("session_id", "unknown")
    tracker = get_tracker_path(session_id)

    # Read existing paths
    existing_paths: set[str] = set()
    if tracker.exists():
        existing_paths = set(tracker.read_text(encoding="utf-8").strip().split("\n"))
        existing_paths.discard("")

    # Add new path (normalize)
    normalized = str(Path(file_path).resolve())
    existing_paths.add(normalized)

    # Write back
    tracker.write_text("\n".join(existing_paths) + "\n", encoding="utf-8")

    count = len(existing_paths)

    # WHY: if a plan exists — do not warn, the agent is working to a plan.
    if has_active_plan():
        return

    # WHY: warn only at meaningful milestones, not on every file after threshold.
    # Firing every edit after 5 files creates alert fatigue — the warning becomes
    # noise and gets ignored. Milestone-only keeps it signal, not noise.
    MILESTONES = {3, 5, 10, 20, 30, 50}

    if count not in MILESTONES:
        return

    if count == 3:
        # Soft reminder at first threshold
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    "[plan-mode-guard] 3 unique files edited in this session. "
                    "CLAUDE.md v10.0 Plan-First Protocol: tasks touching 3+ files "
                    "should use EnterPlanMode first. Consider the 4-phase workflow: "
                    "Explore -> Design (brainstorming skill) -> Plan -> Code. "
                    "If you haven't planned — pause and create a plan."
                ),
            }
        }
        print(json.dumps(result))
    else:
        # Stronger reminder at higher milestones (5, 10, 20, 30, 50)
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"[plan-mode-guard] Milestone: {count} unique files edited this session. "
                    "If working across multiple tasks — this is expected. "
                    "If a single task touches this many files — EnterPlanMode recommended."
                ),
            }
        }
        print(json.dumps(result))


if __name__ == "__main__":
    main()
