#!/usr/bin/env python3
"""PreCompact hook: save critical context before compression.

WHY: When Claude compresses context, details of current work are lost.
This hook automatically updates the timestamp in activeContext.md,
so that on next load it is clear when compression occurred.
"""

import os
from datetime import datetime

from utils import find_project_memory


def main():
    # Update project activeContext.md
    active = find_project_memory()
    if active is not None:
        content = active.read_text(encoding="utf-8")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        # Update the "Updated:" line
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("## Updated:"):
                lines[i] = f"## Updated: {timestamp} (pre-compact)"
                break
        active.write_text("\n".join(lines), encoding="utf-8")
        print(f"[PreCompact] Updated {active} timestamp to {timestamp}")
    else:
        print("[PreCompact] No project activeContext.md found.")

    # Log compaction event
    log_dir = os.path.expanduser("~/.claude/logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "sessions.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} | COMPACT | cwd={os.getcwd()}\n")


if __name__ == "__main__":
    main()
