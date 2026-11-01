#!/usr/bin/env python3
"""SubagentStop hook: machine-log every reviewer/security-guard verdict, so a
suspected-false-PASS rate can eventually be computed instead of assumed.

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

Also records `model` and `run_outcome`, read from the subagent's own transcript at
<projects>/<project>/<session>/subagents/agent-<agent_id>.jsonl. Either one is "unknown" when its
source is missing or unrecognised: no transcript on disk, several transcripts matching the ids,
an unreadable file, unsafe or missing ids in the event, no model or stop_reason on the final
message, or a value outside the documented set. When the transcript cannot be located or read,
both fields are "unknown". A gap is recorded as a gap, never estimated.

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

from lib.discovery import find_file_upward
from lib.state import file_lock

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


# WHY: model and run_outcome exist only in the subagent's own transcript, and that file is
# found by path. Both ids are checked against _ID_RE before they reach a glob, so text from
# the event payload cannot widen the search beyond <projects>/*/<session>/subagents/.
_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")
# Mapping from the final message's stop_reason. end_turn, max_tokens and refusal are the
# documented meanings; tool_use -> interrupted is an inference: the run ended on a tool call,
# before any answer to it. Any other value is recorded as "unknown", never guessed.
_STOP_TO_OUTCOME = {
    "end_turn": "completed",
    "max_tokens": "truncated",
    "refusal": "refused",
    "tool_use": "interrupted",
}


def _subagent_transcript(data: dict[str, object]) -> Path | None:
    """Return the subagent's transcript path, or None if it is not on disk."""
    session_id = data.get("session_id")
    agent_id = data.get("agent_id")
    if not (isinstance(session_id, str) and isinstance(agent_id, str)):
        return None
    if not (_ID_RE.fullmatch(session_id) and _ID_RE.fullmatch(agent_id)):
        return None
    root = Path.home() / ".claude" / "projects"
    matches = sorted(root.glob(f"*/{session_id}/subagents/agent-{agent_id}.jsonl"))
    # WHY: the same session id under two project folders would make the model a guess, so an
    # ambiguous match counts as absent and is recorded as "unknown".
    return matches[0] if len(matches) == 1 else None


def _last_assistant_meta(path: Path) -> tuple[str | None, str | None]:
    """Return (model, stop_reason) of the final non-synthetic assistant message."""
    # WHY: model and stop_reason come from that one message only. A last-non-null scan over the
    # whole file let an earlier turn's tool_use stand in for a final message with no stop_reason,
    # which mislabelled tool-using runs as interrupted (found on real reviewer transcripts,
    # 2026-10-16).
    last_id: str | None = None
    model_by_id: dict[str, str] = {}
    stop_by_id: dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh):
            if '"assistant"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            msg = rec.get("message")
            if not isinstance(msg, dict) or (msg.get("role") or rec.get("type")) != "assistant":
                continue
            if msg.get("model") == "<synthetic>":
                continue
            # one assistant message is written as several records that share its id
            raw_id = msg.get("id")
            mid = raw_id if isinstance(raw_id, str) else f"line-{n}"
            last_id = mid
            if isinstance(msg.get("model"), str):
                model_by_id[mid] = msg["model"]
            if isinstance(msg.get("stop_reason"), str):
                stop_by_id[mid] = msg["stop_reason"]
    if last_id is None:
        return None, None
    return model_by_id.get(last_id), stop_by_id.get(last_id)


def _run_meta(data: dict[str, object]) -> tuple[str, str]:
    """Return (model, run_outcome) for this subagent run; ("unknown", "unknown") on any gap."""
    try:
        transcript = _subagent_transcript(data)
        if transcript is None:
            return "unknown", "unknown"
        model, stop_reason = _last_assistant_meta(transcript)
    except (OSError, RuntimeError, ValueError):  # RuntimeError: Path.home() with no HOME set
        return "unknown", "unknown"
    model_value = model if model and len(model) <= 100 and model.isprintable() else "unknown"
    return model_value, _STOP_TO_OUTCOME.get(stop_reason or "", "unknown")


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    result = extract(str(data.get("last_assistant_message", "") or ""))
    if result is None:
        sys.exit(0)
    agent, verdict = result

    # Defensive corroboration only (external review, 2026-07-21, asked "why not read
    # subagent_type/agent_name off the event instead of inferring from label casing").
    # Evidenced answer: iteration_guard.py's own docstring/code establishes that THIS
    # payload shape (SubagentStop) never carries tool_input -- unlike PreToolUse/
    # PostToolUse, it only has last_assistant_message/session_id -- which is exactly why
    # iteration_guard.py, agent_lifecycle.py, and boyko_protocol_guard.py all resort to the
    # same message-content inference this hook uses. If a future Claude Code version DOES
    # add a top-level field, prefer it over the casing heuristic without extra cost; if not
    # (the documented status quo), this is a no-op.
    for key in ("subagent_type", "agent_type", "agent_name"):
        declared = data.get(key)
        if isinstance(declared, str) and declared.strip().lower().replace("_", "-") in (
            "reviewer",
            "security-guard",
        ):
            agent = declared.strip().lower().replace("_", "-")
            break

    log_path = _log_path()
    if log_path is None:
        sys.exit(0)  # not inside a project with .claude/memory/ -- nothing to anchor to

    model, run_outcome = _run_meta(data)
    record = {
        "schema_version": SCHEMA_VERSION,
        "ts": datetime.now(UTC).isoformat(),
        "agent": agent,
        "verdict": verdict,
        "session_id": str(data.get("session_id", "") or ""),
        "git_head": _git(["rev-parse", "HEAD"]),
        "files": _touched_files(),
        "model": model,
        "run_outcome": run_outcome,
    }

    # WHY file_lock (external review, 2026-07-21): parallel subagents (review-squad runs
    # reviewer + security-guard concurrently) can both hit SubagentStop close together,
    # racing an unlocked `open("a")` append -- POSIX appends are usually safe, but Windows
    # (this repo's own dev environment) has no such append-atomicity guarantee. Same idiom
    # as observation_capture.py: acquire, or skip -- never raise into the session over
    # telemetry, matching this hook's own fail-open contract.
    lock_path = log_path.with_suffix(".lock")
    try:
        with file_lock(lock_path, timeout=5.0) as acquired:
            if not acquired:
                sys.exit(0)  # telemetry only -- skip rather than risk a torn write
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass  # telemetry only -- never fail the session over a write error

    sys.exit(0)


if __name__ == "__main__":
    main()
