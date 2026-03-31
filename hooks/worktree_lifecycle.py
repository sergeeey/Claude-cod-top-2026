#!/usr/bin/env python3
"""WorktreeCreate/WorktreeRemove hook: track worktree lifecycle.

WHY: Audits experiment creation/cleanup for traceability.
"""
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)
    event = "create" if "Create" in data.get("hook_event", str(data)) else "remove"
    worktree_path = data.get("worktree_path", "unknown")
    log_path = Path.home() / ".claude" / "logs" / "worktrees.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "event": event, "path": str(worktree_path),
                "timestamp": datetime.now(UTC).isoformat(),
            }) + "\n")
    except OSError:
        pass
    if event == "create":
        print(f"[worktree] Created: {worktree_path}. Isolated experiment.", file=sys.stderr)
    else:
        print(f"[worktree] Removed: {worktree_path}. Cleanup complete.", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
