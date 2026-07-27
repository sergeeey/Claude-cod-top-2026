#!/usr/bin/env python3
"""TaskCreated / TaskCompleted hook: audit trail for task lifecycle.

WHY: Tracking task creation and completion provides session-level
productivity metrics and helps debug abandoned tasks.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from utils import parse_stdin, rotate_log_if_large


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    event = data.get("hook_event_name", "unknown")
    task_id = data.get("task_id", "unknown")
    task_subject = data.get("task_subject", "")
    session_id = data.get("session_id", "unknown")

    log_dir = Path.home() / ".claude" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "tasks.jsonl"
    rotate_log_if_large(log_file)

    try:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "task_id": task_id,
            "task_subject": task_subject,
            "session_id": session_id,
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as exc:
        # WHY stderr, not silent (LOW, cross-model audit): a write failure
        # here means the task lifecycle record for this event silently
        # disappears with zero signal. stderr (not stdout -- stdout is the
        # hook protocol channel) surfaces it without affecting hook output.
        print(f"[task-audit] WARNING: failed to write task log: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
