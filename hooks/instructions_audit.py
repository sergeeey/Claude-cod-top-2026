#!/usr/bin/env python3
"""InstructionsLoaded hook: log which rules and CLAUDE.md files are loaded.

WHY: Debugging config drift — knowing which instructions loaded helps
diagnose why behavior changed between sessions or across machines.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from utils import parse_stdin


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    file_path = data.get("file_path", "unknown")
    load_reason = data.get("load_reason", "unknown")
    memory_type = data.get("memory_type", "unknown")
    session_id = data.get("session_id", "unknown")

    log_dir = Path.home() / ".claude" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "instructions.jsonl"

    try:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": "InstructionsLoaded",
            "file_path": file_path,
            "load_reason": load_reason,
            "memory_type": memory_type,
            "session_id": session_id,
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


if __name__ == "__main__":
    main()
