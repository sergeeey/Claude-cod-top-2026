#!/usr/bin/env python3
"""PostToolUse(Bash) hook: reindex gitnexus after a successful git commit.

WHY: CLAUDE.md claims "After git commit: run npx gitnexus analyze to refresh
index (hook does this automatically)". Audited 2026-07-21 and found FALSE: no
git post-commit hook and no Claude Code hook existed anywhere in this setup.
gitnexus's own index for this repo's root checkout was stale since 2026-04-15
while dozens of commits had landed since (confirmed live via
mcp__gitnexus__list_repos). This hook closes that gap.

Detection: the same commit-detection heuristic as post_commit_memory.py (the
closest functional analog -- also reacts to "a commit just happened" for a
non-security purpose): a bare `"git commit" in command` + is_failed_commit()
check. This is a KNOWN weaker check than pre_commit_guard.py's shlex/heredoc-
aware detector (misses `git -C <repo> commit`), accepted here for the same
reason post_commit_memory.py accepts it: a missed trigger just leaves the
index stale until the NEXT commit's hook fires -- self-healing, not a
security gap (unlike pre_commit_guard's push-protection, where a miss matters
far more and justifies the heavier detector).

cwd correctness DOES matter here, unlike the detection heuristic: this user
routinely runs Claude Code from many different project directories in one
session. Without handling a leading `cd <dir> &&`, this hook would reindex
the WRONG repo -- wasting ~30s and leaving the actually-committed-to repo
still stale. Reuses utils.extract_command_cwd rather than reimplementing it.

Fire-and-forget via async_wrapper (see hooks/CLAUDE.md): reindexing measured
at 27.5s for this repo -- far too slow for a synchronous PostToolUse hook.
This hook has nothing to report back to Claude (pure background maintenance),
which is exactly why async_wrapper is correct here: per hooks/CLAUDE.md's own
warning ("Never wrap a hook in async_wrapper if it needs to inject context"),
this hook deliberately never calls emit_hook_result.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from utils import (
    extract_command_cwd,
    extract_tool_response,
    file_lock,
    get_tool_input,
    is_failed_commit,
    parse_stdin,
)

# WHY 120s, not the measured ~27.5s: generous headroom for a larger repo or a
# slow machine, while still bounded -- a hung npx process must not leak forever.
_REINDEX_TIMEOUT_SECONDS = 120

# WHY a lock at all (reviewer finding, 2026-07-21): two rapid commits in the
# same repo each spawn their own async_wrapper'd hook instance -- with no
# guard, both would run `npx gitnexus analyze` concurrently against the same
# repo, wasting a full ~27s reindex twice for no benefit (the second run's
# result is a superset of the first's). WHY skip-not-raise (unlike the
# read-modify-write callers in utils.file_lock's own docstring, who raise on
# a missed lock because losing an update is a real correctness bug): this
# lock only dedups redundant WORK, it doesn't protect shared state -- if the
# lock is already held, a reindex for this exact repo is already in flight
# and will pick up everything this call would have, so skipping is strictly
# equivalent to waiting, at zero cost. WHY 0.5s timeout, not 15s like the
# state-file callers: this call only needs to detect "is one already
# running RIGHT NOW", not wait one out -- a real reindex takes ~27s, so a
# short timeout still reliably distinguishes "someone else just grabbed it"
# from "stale".
_LOCK_ACQUIRE_TIMEOUT_SECONDS = 0.5
_LOCK_DIR = Path.home() / ".claude" / "cache" / "gitnexus_reindex_locks"


def _lock_path_for(target_dir: str) -> Path:
    """One lock file per distinct repo dir (hashed -- paths may contain
    characters unsafe for a filename, e.g. Windows drive letters/colons)."""
    digest = hashlib.sha256(target_dir.encode("utf-8")).hexdigest()[:16]
    return _LOCK_DIR / f"{digest}.lock"


def should_reindex(command: str, response_text: str) -> bool:
    """Pure core (no I/O -- unit-testable): does this Bash call represent a
    SUCCESSFUL git commit?"""
    if "git commit" not in command:
        return False
    return not is_failed_commit(response_text)


def resolve_target_dir(command: str) -> str:
    """The directory gitnexus should reindex: a leading `cd <dir> &&` target,
    or the hook process's own cwd if the command never changed directory."""
    return extract_command_cwd(command) or os.getcwd()


def main() -> None:
    # WHY: recursion guard -- a subagent's own commits must not re-trigger this.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    data = parse_stdin()
    if not data:
        sys.exit(0)

    tool_input = get_tool_input(data)
    command = str(tool_input.get("command") or "")
    response_text = extract_tool_response(data)

    if not should_reindex(command, response_text):
        sys.exit(0)

    target_dir = resolve_target_dir(command)

    try:
        with file_lock(
            _lock_path_for(target_dir), timeout=_LOCK_ACQUIRE_TIMEOUT_SECONDS
        ) as acquired:
            if not acquired:
                return  # a reindex for this repo is already in flight -- skip, don't queue
            subprocess.run(
                ["npx", "gitnexus", "analyze"],
                cwd=target_dir,
                timeout=_REINDEX_TIMEOUT_SECONDS,
                capture_output=True,
                check=False,
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # WHY silent: pure background maintenance -- a failed reindex must
        # never surface as an error; the next commit's hook simply retries.
        pass


if __name__ == "__main__":
    main()
