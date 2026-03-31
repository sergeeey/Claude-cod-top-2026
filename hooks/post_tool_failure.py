#!/usr/bin/env python3
"""PostToolUseFailure hook: error recovery guidance.

WHY: When tools fail repeatedly, Claude retries the same approach.
This hook tracks failures and suggests the 4-tier recovery protocol.
"""
import json
import sys
from pathlib import Path

FAILURE_LOG = Path.home() / ".claude" / "logs" / "tool_failures.jsonl"


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)
    tool_name = data.get("tool_name", "unknown")
    error = data.get("error", "")
    FAILURE_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(FAILURE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"tool": tool_name, "error": str(error)[:200]}) + "\n")
    except OSError:
        pass
    recent_count = 0
    try:
        lines = FAILURE_LOG.read_text(encoding="utf-8").strip().split("\n")
        for line in lines[-10:]:
            try:
                if json.loads(line).get("tool") == tool_name:
                    recent_count += 1
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    if recent_count >= 3:
        print(json.dumps({"result": "info", "message":
            f"[error-recovery] Tool '{tool_name}' failed {recent_count}x. "
            "4-tier recovery: T1 re-read error, T2 refresh context, "
            "T3 different approach, T4 STOP and report to user."}))
    sys.exit(0)


if __name__ == "__main__":
    main()
