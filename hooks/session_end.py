#!/usr/bin/env python3
"""SessionEnd hook: cleanup and final memory persistence.

WHY: Ensures logs are trimmed and session end is audited.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from utils import rotate_log_if_large


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)
    log_path = Path.home() / ".claude" / "logs" / "sessions.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # WHY (LOW, cross-model audit): every SessionEnd appends here, but
        # unlike tool_failures.jsonl/api_errors.jsonl below, this file was
        # never trimmed -- it grows forever on a long-lived machine.
        rotate_log_if_large(log_path)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "event": "session_end",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "reason": data.get("matcher", "unknown"),
                    }
                )
                + "\n"
            )
    except OSError:
        pass
    for log_file in ("tool_failures.jsonl", "api_errors.jsonl"):
        fpath = Path.home() / ".claude" / "logs" / log_file
        if fpath.exists():
            try:
                lines = fpath.read_text(encoding="utf-8").strip().split("\n")
                if len(lines) > 100:
                    fpath.write_text("\n".join(lines[-100:]) + "\n", encoding="utf-8")
            except OSError:
                pass
    sys.exit(0)


if __name__ == "__main__":
    main()
