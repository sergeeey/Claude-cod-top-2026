#!/usr/bin/env python3
"""ConfigChange hook: audit trail for settings modifications.

WHY: Unauthorized or accidental config changes can weaken security.
Logging every change creates an audit trail for troubleshooting.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from utils import parse_stdin


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    source = data.get("source", "unknown")
    file_path = data.get("file_path", "unknown")
    timestamp = datetime.now(timezone.utc).isoformat()

    # WHY: append-only log ensures no entries can be silently removed
    log_dir = Path.home() / ".claude" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "config_audit.log"

    try:
        entry = {
            "timestamp": timestamp,
            "source": source,
            "file_path": file_path,
            "event": "ConfigChange",
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


if __name__ == "__main__":
    main()
