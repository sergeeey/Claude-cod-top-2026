#!/usr/bin/env python3
"""Stop hook: update timestamp and check memory staleness.

ПОЧЕМУ: Это последний шанс напомнить Claude обновить память перед тем как
пользователь уйдёт. Проверяем: если activeContext.md не обновлялся >30 мин,
а git log показывает свежие коммиты — память устарела.
"""

import os
import subprocess
import time
from datetime import datetime
from pathlib import Path


def find_project_memory() -> Path | None:
    """Find project .claude/memory/ walking up from CWD."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".claude" / "memory" / "activeContext.md"
        if candidate.exists():
            return candidate
    return None


def get_last_commit_time() -> float | None:
    """Get timestamp of the last git commit."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def main():
    try:
        # 1. Update global activeContext timestamp
        global_path = os.path.expanduser("~/.claude/memory/activeContext.md")
        if os.path.exists(global_path):
            with open(global_path, encoding="utf-8") as f:
                content = f.read()
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "## Последнее обновление" in line and i + 1 < len(lines):
                    lines[i + 1] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    break
            with open(global_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

        # 2. Log session
        log_dir = os.path.expanduser("~/.claude/logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "sessions.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} | SESSION_END\n")

        # 3. Check project memory staleness
        project_ctx = find_project_memory()
        if project_ctx is None:
            return

        ctx_mtime = project_ctx.stat().st_mtime
        ctx_age_min = (time.time() - ctx_mtime) / 60

        last_commit = get_last_commit_time()
        if last_commit is None:
            return

        commit_age_min = (time.time() - last_commit) / 60

        # If commit is newer than activeContext by >5 min → stale
        if last_commit > ctx_mtime and (last_commit - ctx_mtime) > 300:
            stale_min = (last_commit - ctx_mtime) / 60
            print(
                f"[session-save] WARNING: activeContext.md is "
                f"{stale_min:.0f} min behind latest commit."
            )
            print(
                f"[session-save] Last commit: {commit_age_min:.0f} min ago, "
                f"activeContext: {ctx_age_min:.0f} min ago."
            )
            print("[session-save] Memory should be updated before ending session.")

    except Exception:
        pass


if __name__ == "__main__":
    main()
