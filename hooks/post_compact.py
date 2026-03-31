#!/usr/bin/env python3
"""PostCompact hook: re-inject critical context after compaction.

WHY: Compaction may lose CLAUDE.md instructions and current focus.
This hook reminds Claude to re-read key context files.
"""
import json
import sys
from pathlib import Path


def main() -> None:
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        pass
    reminders = ["[post-compact] Context compacted."]
    for parent in [Path.cwd(), *Path.cwd().parents]:
        ctx = parent / ".claude" / "memory" / "activeContext.md"
        if ctx.exists():
            reminders.append(f"Re-read {ctx} to restore focus.")
            break
    if (Path.cwd() / ".scope-fence.md").exists():
        reminders.append("Re-read .scope-fence.md for scope boundaries.")
    reminders.append("Key rules: Evidence Policy, Plan-First (3+ files), 80/20.")
    print(json.dumps({"result": "info", "message": " ".join(reminders)}))
    sys.exit(0)


if __name__ == "__main__":
    main()
