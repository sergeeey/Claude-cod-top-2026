#!/usr/bin/env python3
"""Stop hook: update global activeContext timestamp, log session end, check memory staleness.

WHY: This is the last chance to remind Claude to update memory before
the user leaves. We check: if activeContext.md was not updated for >30 min,
but git log shows fresh commits — memory is stale.

WHY split from the Raw→Wiki pipeline (2026-08-28, /tracy strategic pass after
deletion-test found this file was a 1043-line God-module with two unrelated
responsibilities): this hook's job is session-end bookkeeping (timestamp,
log, staleness warning) — a fundamentally different concern from converting
raw notes into wiki entries. See hooks/raw_to_wiki.py for that pipeline,
split out the same day. Both remain registered on Stop independently,
matching the existing multi-hook-per-event pattern already used by
webhook_notify.py/wiki_reminder.py/thematic_index_router.py.
"""

import contextlib
import os
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from utils import find_project_memory, rotate_log_if_large

# WHY: recursion guard — if this hook is triggered inside an Agent SDK
# sub-invocation (e.g., compile.py spawns Claude), exit immediately to
# prevent double-processing and infinite loops.
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

# WHY: dry-run mode — set CLAUDE_DRY_RUN=1 to preview what this hook
# would write without touching any files. Useful for testing and CI.
# Based on Evolver review gate pattern: show → confirm → execute.
DRY_RUN = os.environ.get("CLAUDE_DRY_RUN") == "1"


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


def atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically using tmp+rename.

    WHY: bare open("w") on a shared file loses data when two processes
    (e.g. session_start + session_save running concurrently) write simultaneously.
    tmp+rename is atomic on POSIX; on Windows it's best-effort but still safer.
    """
    path = Path(path)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)  # atomic on POSIX, best-effort on Windows
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def main() -> None:
    try:
        if DRY_RUN:
            print("[dry-run] session_save.py — preview mode (CLAUDE_DRY_RUN=1)")
            print("[dry-run] no files will be written")

        # 1. Update global activeContext timestamp
        global_path = os.path.expanduser("~/.claude/memory/_auto/activeContext.md")
        if os.path.exists(global_path):
            with open(global_path, encoding="utf-8") as f:
                content = f.read()
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "## Last update" in line and i + 1 < len(lines):
                    lines[i + 1] = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
                    break
            if not DRY_RUN:
                atomic_write(Path(global_path), "\n".join(lines))
            else:
                print(f"[dry-run] would update timestamp in: {global_path}")

        # 2. Log session
        log_dir = os.path.expanduser("~/.claude/logs")
        log_path = os.path.join(log_dir, "sessions.log")
        if not DRY_RUN:
            os.makedirs(log_dir, exist_ok=True)
            rotate_log_if_large(Path(log_path))
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now(UTC).isoformat()} | SESSION_END\n")
        else:
            print(f"[dry-run] would append SESSION_END to: {log_path}")

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
                f"[session-save] WARNING: activeContext.md is"
                f" {stale_min:.0f} min behind latest commit."
            )
            print(
                f"[session-save] Last commit: {commit_age_min:.0f} min ago,"
                f" activeContext: {ctx_age_min:.0f} min ago."
            )
            print("[session-save] Memory should be updated before ending session.")
            # WHY not a separate hook: this Stop hook already detects the exact
            # "memory is behind the work" signal that means a pause is risky, so
            # the /mothball pointer lives here rather than as a new hook (which
            # would duplicate this detection and add a doc-count cascade). Scoped
            # to a LONG pause so it doesn't nag on every ordinary session end —
            # /session-retrospective is the lighter option for a short wrap-up.
            print(
                "[session-save] For a LONG pause (days+): run /mothball to conserve"
                " full context (Land-the-Plane + memory dump + resume section)."
            )

    except Exception as e:
        import traceback

        # WHY: F14 — previously swallowed silently — at least log to stderr so user sees it.
        # WHY stderr: stdout is the hook protocol, must not contaminate.
        print(f"[session_save error] {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)


if __name__ == "__main__":
    main()
