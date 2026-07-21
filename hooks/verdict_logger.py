#!/usr/bin/env python3
"""SubagentStop hook: machine-log every reviewer/security-guard verdict, so a false-PASS
rate can eventually be computed instead of assumed.

WHY: reviewer.md and security-guard.md both issue a structured verdict (VERDICT: LGTM |
NEEDS_WORK | BLOCK, and Verdict: PASS | BLOCK respectively), but today that verdict only
ever exists as chat text -- nothing persists it against the commit/files it was actually
about. There is no way to answer "how often did a reviewer LGTM turn out wrong later?"
without that record. iteration_guard.py already proved this exact extraction pattern works
(SubagentStop -> last_assistant_message -> VERDICT regex) for its own, narrower purpose
(the cap=3 escalation counter); this hook reuses the same shape for a different one:
append-only evidence, not enforcement.

Deliberately NOT reused from iteration_guard.py: this hook is independent (no cross-hook
import) per this repo's own hook-independence convention (hooks/CLAUDE.md: share utils.py,
not each other) -- and its failure mode is different: iteration_guard blocks on the internal
signed eo_loop.json state; this hook only ever appends telemetry and must never affect
control flow if it fails.

Honest scope: only reviewer and security-guard have a machine-parseable verdict format
today. Other agents (verifier, sec-auditor, skeptic, ...) are invisible to this log until
they adopt an equally strict format -- silently skipped, not estimated.

Fires on: SubagentStop. Never blocks, never denies, fail-open on every error path.
State: <project>/.claude/memory/verdict_log.jsonl (append-only JSONL, one record per line).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

# Recursion guard -- must never re-enter when Claude spawns subagents.
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

from utils import find_file_upward  # noqa: E402

SCHEMA_VERSION = 1

# Same shape as iteration_guard.py's _VERDICT_RE, kept independent (see module docstring).
# Case-SENSITIVE on purpose: reviewer.md's template literally reads "VERDICT: LGTM |
# NEEDS_WORK | BLOCK" (all-caps label); security-guard.md's reads "Verdict: PASS / BLOCK"
# (title-case label). For LGTM/NEEDS_WORK/PASS the two never collide anyway, but BLOCK is
# a value both formats use -- label casing is the only real signal that disambiguates it,
# so IGNORECASE would silently misattribute every security-guard BLOCK to reviewer
# (caught by test_extracts_security_guard_block, which is why this isn't IGNORECASE).
_REVIEWER_RE = re.compile(r"VERDICT:\s*(LGTM|NEEDS_WORK|BLOCK)")
_SECURITY_GUARD_RE = re.compile(r"Verdict:\s*(PASS|BLOCK)")


def extract(message: str) -> tuple[str, str] | None:
    """Return (agent, verdict) from a subagent's final message, or None if unrecognized."""
    if not message:
        return None
    m = _REVIEWER_RE.search(message)
    if m:
        return "reviewer", m.group(1).upper()
    m = _SECURITY_GUARD_RE.search(message)
    if m:
        return "security-guard", m.group(1).upper()
    return None


def _git(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _touched_files() -> list[str]:
    """Best-effort union of the last commit's files and the current working-tree diff --
    the verdict could be about either, depending on when in the commit cycle it fired."""
    files: set[str] = set()
    last_commit = _git(["diff", "--name-only", "HEAD~1..HEAD"])
    if last_commit:
        files.update(line for line in last_commit.splitlines() if line)
    working_tree = _git(["diff", "--name-only", "HEAD"])
    if working_tree:
        files.update(line for line in working_tree.splitlines() if line)
    return sorted(files)


def _log_path() -> Path | None:
    anchor = find_file_upward(str(Path(".claude") / "memory" / "activeContext.md"))
    if anchor is None:
        return None
    return anchor.parent / "verdict_log.jsonl"


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    result = extract(str(data.get("last_assistant_message", "") or ""))
    if result is None:
        sys.exit(0)
    agent, verdict = result

    log_path = _log_path()
    if log_path is None:
        sys.exit(0)  # not inside a project with .claude/memory/ -- nothing to anchor to

    record = {
        "schema_version": SCHEMA_VERSION,
        "ts": datetime.now(UTC).isoformat(),
        "agent": agent,
        "verdict": verdict,
        "session_id": str(data.get("session_id", "") or ""),
        "git_head": _git(["rev-parse", "HEAD"]),
        "files": _touched_files(),
    }

    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass  # telemetry only -- never fail the session over a write error

    sys.exit(0)


if __name__ == "__main__":
    main()
