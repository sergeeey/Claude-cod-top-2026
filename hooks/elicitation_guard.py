#!/usr/bin/env python3
"""Elicitation / ElicitationResult hook: audit MCP elicitation events.

WHY: MCP elicitation events are invisible by default. Logging them
creates an audit trail for MCP server interactions that request user input.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from utils import parse_stdin


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    event = data.get("hook_event_name", "unknown")
    session_id = data.get("session_id", "unknown")

    log_dir = Path.home() / ".claude" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "elicitation.jsonl"

    try:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "session_id": session_id,
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


if __name__ == "__main__":
    main()
