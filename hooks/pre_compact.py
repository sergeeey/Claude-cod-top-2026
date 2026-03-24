#!/usr/bin/env python3
"""PreCompact hook: save critical context before compression.

WHY: When Claude compresses context, details of current work are lost.
This hook updates the timestamp AND extracts pending tasks from
activeContext.md into goals.md so they survive the /clear cycle.
"""

import os
import re
from datetime import datetime
from pathlib import Path

from utils import find_project_memory

# WHY: these markers signal unfinished work that must survive compaction
PENDING_PATTERNS = re.compile(
    r"^[-*]\s*\[?\s?\]?\s*(TODO|NEXT|PENDING|BLOCKED|WIP|IN.PROGRESS)\b.*",
    re.IGNORECASE,
)


def extract_pending_items(content: str) -> list[str]:
    """Extract lines matching TODO/NEXT/PENDING/BLOCKED from activeContext."""
    return [line.strip() for line in content.splitlines() if PENDING_PATTERNS.match(line.strip())]


def save_pending_to_goals(items: list[str], active_path: Path) -> None:
    """Append pending items to goals.md in the same memory directory."""
    if not items:
        return
    goals_path = active_path.parent / "goals.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    block = f"\n### Carried from compaction ({timestamp})\n"
    block += "\n".join(f"- {item}" for item in items) + "\n"

    if goals_path.exists():
        existing = goals_path.read_text(encoding="utf-8")
        goals_path.write_text(existing.rstrip() + "\n" + block, encoding="utf-8")
    else:
        goals_path.write_text(f"# Goals\n{block}", encoding="utf-8")


def main():
    active = find_project_memory()
    if active is not None:
        content = active.read_text(encoding="utf-8")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 1. Extract pending tasks before they are lost
        pending = extract_pending_items(content)
        if pending:
            save_pending_to_goals(pending, active)
            print(f"[PreCompact] Saved {len(pending)} pending items to goals.md")

        # 2. Update the "Updated:" line
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
