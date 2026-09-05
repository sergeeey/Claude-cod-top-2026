#!/usr/bin/env python3
"""PostToolUse hook for Bash: auto-log commits to activeContext.md.

WHY: memory_guard only REMINDS to update context. This hook ACTS —
it automatically appends the commit log to activeContext.md. Double safety net:
1. Auto-log (commit fact recorded)
2. Reminder for Claude to supplement context manually (auto-log is the minimum)

Difference from memory_guard: memory_guard checks file freshness.
post_commit_memory maintains a structured commit log.
"""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from lib.discovery import find_file_upward, find_project_memory, run_git
from lib.runtime import (
    emit_hook_result,
    extract_tool_response,
    get_tool_input,
    is_failed_commit,
    parse_stdin,
)
from lib.state import atomic_write_json, atomic_write_text, load_json_state

# WHY (docs/memory-architecture.md target, implemented 2026-08-22): the
# Auto-commit log in activeContext.md grew unbounded -- this file's own
# section header comment already calls that section "history, not source
# of truth", but nothing capped it, so it kept growing until PreCompact's
# progressive-summary pass collapsed old entries into "[summarized]"
# markers, permanently losing the per-commit detail. Every commit now ALSO
# gets appended to a permanent, per-day archive (history/commits-<date>.md)
# before the active section is capped -- trimming the recent view is then
# safe: nothing is lost, it just isn't duplicated in both places forever.
_ACTIVE_LOG_CAP = 15

# WHY (GitHub issue #354, found via 4 separate Codex-review catches in the
# repo this hook was designed against, 2026-09-04): that repo's own workflow
# always squash- or rebase-merges PRs, which mints a brand-new commit hash
# on `main` and makes the hash logged here at commit time permanently
# unreachable from any remote branch the moment its PR merges -- verified
# repeatedly there with `git branch -r --contains <hash>` returning empty
# for every such commit checked. The hook cannot know at commit time
# whether -- or how -- a branch will eventually be merged (a hard timing
# constraint, not fixable by changing what gets computed here), so the log
# entry itself says plainly when a hash might not stay resolvable, WITHOUT
# presuming any specific merge policy.
#
# WHY this is deliberately NOT worded as "will be squashed" (Codex review,
# PR #355, corrected before merge): this hook is a distributable Claude
# Code config artifact, installed into other people's ~/.claude/hooks/ by
# hooks/CLAUDE.md's own description -- an installation using ordinary merge
# commits (history preserved, hash never rewritten) or a local branch that
# never becomes a PR at all would make a flat "will be squashed" claim
# simply false there. The wording below only says a hash MAY be replaced,
# without asserting which merge strategy (if any) will be used.
#
# WHY detached HEAD gets its OWN category, not lumped in with "stable like
# main" (Codex review, PR #355, second finding, corrected before merge):
# `git branch --show-current` returns "" for detached HEAD exactly like it
# does for "we couldn't determine the branch" -- but a detached-HEAD commit
# has no branch ref retaining it at all and can become unreachable via
# ordinary garbage collection, which is the same class of risk this fix
# exists to flag, not the "this is fine, like main" case an empty string
# was originally treated as.
_MAIN_BRANCH_NAMES = frozenset({"main", "master"})

# WHY (2026-09-05, user report: "тот же бесконечный хвост" -- a burst of
# commits in one session, e.g. a PR-per-fix workflow, made this hook's
# "please update context manually" line fire identically after every single
# commit): the archive + Auto-commit log writes below are the valuable,
# lossless part and must never be throttled -- only the repeated NUDGE TEXT
# is noise once a session already saw it. First commit of a session gets the
# full reminder; commits 2..(N-1) after that get silence (archive still
# happens); every Nth commit repeats it once, so a long session isn't
# reminded exactly once and then never again. Session-scoped (not global)
# so a fresh session always gets the first-commit reminder.
_NUDGE_EVERY_N = 5
_NUDGE_STATE_FILENAME = "post_commit_nudge.json"  # under active_ctx.parent/"state"


def _nudge_commit_count(active_ctx: Path, session_id: str) -> int:
    """Increment and return this session's commit count, for nudge throttling.

    Plain counter, no signing (unlike iteration_guard.py's HMAC-signed
    session state): this gates cosmetic reminder text, not a security
    control, so tampering has zero blast radius -- proportionate effort.

    WHY keyed off `active_ctx.parent` (sibling of the existing `history/`
    dir from `_history_dir()`, same depth, same convention), not
    `Path.cwd()` and not two parents up: cwd during a hook invocation isn't
    guaranteed to be the project root the memory file was actually found
    under (find_project_memory() walks upward), and in tests it's the test
    runner's cwd, not the fixture's tmp_path -- using cwd directly would
    write real state into this repo's own `.claude/state/` during `pytest`.
    Climbing two parents (assuming activeContext.md always sits under a
    `.claude/memory/` pair) is equally fragile: this file's own tests place
    activeContext.md directly in `tmp_path` with no `.claude/memory/`
    nesting, so `.parent.parent` escaped tmp_path into pytest's shared temp
    root and let unrelated tests collide on one counter (caught by
    test_creates_new_section_in_active_context still failing after the
    Path.cwd() fix, for a different reason than the first failure). One
    parent up -- exactly where `_history_dir()` already writes -- makes no
    assumption about directory depth at all.
    """
    state_dir = active_ctx.parent / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / _NUDGE_STATE_FILENAME
    state = load_json_state(state_path)
    count = int(state.get(session_id, 0)) + 1
    state[session_id] = count
    # WHY cap the dict itself, not just rely on session churn: a very
    # long-lived install could otherwise accumulate one entry per session_id
    # forever. Keep only the most recent 200 sessions' counters.
    if len(state) > 200:
        for stale_key in list(state.keys())[: len(state) - 200]:
            del state[stale_key]
    atomic_write_json(state_path, state)
    return count


def _current_branch() -> str:
    """Best-effort current branch name; empty string if unknown/detached."""
    return run_git(["branch", "--show-current"])


def _format_log_entry(commit_hash: str, commit_msg: str, branch: str, now_dt: datetime) -> str:
    """Build one Auto-commit log line, honest about hash instability.

    See the module-level WHY comment above _MAIN_BRANCH_NAMES for the full
    rationale -- this is the one place those decisions are applied.
    """
    timestamp = now_dt.strftime("%Y-%m-%d %H:%M")
    if branch in _MAIN_BRANCH_NAMES:
        return f"- [{timestamp}] `{commit_hash}`: {commit_msg}\n"
    if branch:
        return (
            f"- [{timestamp}] `{commit_hash}` (local, branch `{branch}` -- "
            f"may be replaced if this branch is later merged via squash or "
            f"rebase; check that branch's PR/merge for the surviving hash "
            f"if this one becomes unresolvable): {commit_msg}\n"
        )
    return (
        f"- [{timestamp}] `{commit_hash}` (detached HEAD or unknown branch "
        f"-- not retained by any branch ref; may become unreachable unless "
        f"tagged or merged): {commit_msg}\n"
    )


def _history_dir(active_ctx: Path) -> Path:
    """The history/ directory sibling to activeContext.md."""
    history_dir = active_ctx.parent / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir


def _archive_commit(active_ctx: Path, log_entry: str, now: datetime) -> None:
    """Append this commit's log line to today's permanent daily archive.

    WHY a new file per day, not per commit: a file per commit (mirroring
    DeepSeek Harness's `.agents/notes/<date>-<slug>.md`) would multiply tiny
    files for routine commits (this repo's own "docs(memory): auto-log entry
    for <sha>" churn is a good example) -- the daily archive gives a
    permanent, ungrowing-per-file record without that multiplication. A
    richer, hand-written `<date>-<slug>.md` narrative note (what/why/outcome)
    is still the right artifact for a genuinely noteworthy chunk of work --
    that's authored by the agent doing the work, not generated per commit.
    """
    archive_path = _history_dir(active_ctx) / f"commits-{now.strftime('%Y%m%d')}.md"
    if archive_path.exists():
        existing = archive_path.read_text(encoding="utf-8")
        atomic_write_text(archive_path, existing.rstrip("\n") + "\n" + log_entry)
    else:
        header = f"# Commit log — {now.strftime('%Y-%m-%d')}\n\n"
        atomic_write_text(archive_path, header + log_entry)


def _trim_active_log(lines: list[str], header_idx: int, cap: int) -> list[str]:
    """Keep only the first `cap` log-entry lines directly under the Auto-commit
    log header (newest-first ordering, since new entries are inserted right
    after the header) -- drop the rest from the ACTIVE view. Safe to drop:
    the full record already landed in history/commits-<date>.md above.
    """
    entry_start = header_idx + 1
    entry_end = entry_start
    while entry_end < len(lines) and (
        lines[entry_end].startswith("- [") or lines[entry_end].startswith("[summarized]")
    ):
        entry_end += 1
    # WHY min(): the slice must never reach past entry_end even when cap is
    # larger than the actual entry count -- otherwise it grabs the blank
    # line/next section too, and appending `lines[entry_end:]` right after
    # duplicates them (found by test_under_cap_keeps_everything).
    kept = lines[entry_start : min(entry_end, entry_start + cap)]
    return lines[:entry_start] + kept + lines[entry_end:]


def find_decisions_file() -> Path | None:
    """Find decisions.md walking up from CWD.

    WHY: global vault uses _auto/ subfolder, project vaults keep decisions.md
    directly in memory/. Check both paths with _auto/ first (preferred).
    """
    return find_file_upward(
        str(Path(".claude") / "memory" / "_auto" / "decisions.md")
    ) or find_file_upward(str(Path(".claude") / "memory" / "decisions.md"))


# WHY: Nexus-lite — automatic accumulation of architectural decisions from commit messages.
# Commits with arch:/decision:/security:/pattern: prefixes automatically go to decisions.md.
# This turns the manual memory system into a semi-automatic one.
DECISION_PREFIXES = ("arch:", "decision:", "security:", "pattern:")


def extract_decision(commit_msg: str) -> tuple[str, str] | None:
    """Extract decision type and description from commit message.

    Returns (type, description) if commit message starts with a decision prefix.
    """
    msg_lower = commit_msg.lower()
    for prefix in DECISION_PREFIXES:
        if msg_lower.startswith(prefix):
            description = commit_msg[len(prefix) :].strip()
            # Strip conventional commit prefix if present (e.g., "feat: arch: ...")
            decision_type = prefix.rstrip(":")
            return decision_type, description

        # Also check after conventional commit prefix: "feat: arch: ..."
        for conv in ("feat:", "fix:", "refactor:", "chore:", "docs:"):
            combined = f"{conv} {prefix}"
            if msg_lower.startswith(combined):
                description = commit_msg[len(combined) :].strip()
                decision_type = prefix.rstrip(":")
                return decision_type, description

    return None


def log_decision(commit_hash: str, commit_msg: str) -> str | None:
    """Auto-record decision to decisions.md if commit message has decision prefix."""
    result = extract_decision(commit_msg)
    if result is None:
        return None

    decision_type, description = result
    decisions_file = find_decisions_file()
    if decisions_file is None:
        return f"Decision detected but no decisions.md found: [{decision_type}] {description}"

    now = datetime.now(UTC).strftime("%Y-%m-%d")
    # Format: ### [date] Description. Type: X. Commit: hash
    entry = f"\n### [{now}] {description}\n- Type: {decision_type}\n- Commit: `{commit_hash}`\n"

    content = decisions_file.read_text(encoding="utf-8")
    # Append at the end
    content = content.rstrip() + "\n" + entry
    # WHY: atomic_write_text (tmp + fsync + os.replace) prevents a lost update
    # when two hook invocations read-modify-write this file close together.
    atomic_write_text(decisions_file, content)

    return f"Auto-recorded [{decision_type}] decision to decisions.md"


def main() -> None:
    # WHY: prevent recursion when this hook fires inside a subagent's
    # SessionStart/etc — see hooks/CLAUDE.md "Recursion guard" section.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    data = parse_stdin()
    if not data:
        return

    tool_input = get_tool_input(data)
    command = tool_input.get("command", "")

    if "git commit" not in command:
        return

    response_text = extract_tool_response(data)
    if is_failed_commit(response_text):
        return

    # Get the last commit data
    commit_hash = run_git(["log", "-1", "--format=%h"])
    commit_msg = run_git(["log", "-1", "--format=%s"])

    if not commit_hash:
        return

    # Find activeContext.md
    active_ctx = find_project_memory()
    if active_ctx is None:
        emit_hook_result(
            "PostToolUse",
            "[post-commit-memory] Commit logged but no activeContext.md found. "
            "Consider creating .claude/memory/activeContext.md for project state tracking.",
        )
        return

    # WHY: we append to the file, not overwrite.
    # The "Auto-commit log" section is a structured log, easy to parse.
    now_dt = datetime.now()
    branch = _current_branch()
    log_entry = _format_log_entry(commit_hash, commit_msg, branch, now_dt)

    # WHY first, before touching activeContext.md: the permanent record must
    # land before the active view is capped, so a crash between the two
    # writes below never loses a commit -- worst case is a duplicate in both
    # places, never a gap in the archive.
    _archive_commit(active_ctx, log_entry, now_dt)

    content = active_ctx.read_text(encoding="utf-8")

    # Find existing section or create a new one
    section_header = "## Auto-commit log"
    if section_header in content:
        # Append after the section header (before next section or at end)
        lines = content.split("\n")
        insert_idx = None
        for i, line in enumerate(lines):
            if line.strip() == section_header:
                insert_idx = i + 1
                break
        if insert_idx is not None:
            lines.insert(insert_idx, log_entry.rstrip())
            lines = _trim_active_log(lines, insert_idx - 1, _ACTIVE_LOG_CAP)
            content = "\n".join(lines)
    else:
        # Create section at end of file
        content = content.rstrip() + f"\n\n{section_header}\n{log_entry}"

    # WHY: atomic_write_text (tmp + fsync + os.replace) prevents a lost update
    # when two hook invocations read-modify-write this file close together.
    atomic_write_text(active_ctx, content)

    # Nexus-lite: auto-record decisions from commit message prefixes
    decision_msg = log_decision(commit_hash, commit_msg)

    # Reminder for Claude to supplement context manually -- throttled per
    # session (see _NUDGE_EVERY_N WHY above). The archive + active-log
    # writes above already happened unconditionally; only this text is
    # gated, so no commit is ever silently un-logged.
    # WHY (2026-09-05, found by skeptic dogfooding boyko-scientific-consortium
    # on this exact fix): defaulting a missing session_id to the literal
    # string "default" would collapse every caller that ever omits it onto
    # ONE shared counter -- the opposite failure mode from the one this
    # throttle exists to fix (over-suppression across unrelated callers,
    # instead of under-suppression within one burst). Always nudge when
    # session_id is absent -- a spurious reminder is a safe default, a
    # silently-merged counter across strangers is not.
    session_id = data.get("session_id")
    if session_id is None:
        should_nudge = True
    else:
        nudge_count = _nudge_commit_count(active_ctx, session_id)
        should_nudge = nudge_count == 1 or nudge_count % _NUDGE_EVERY_N == 0

    additional = ""
    if should_nudge:
        additional = (
            f"[post-commit-memory] Commit {commit_hash} auto-logged. "
            "If this was a meaningful change, a short WHAT/WHY note in "
            "activeContext.md helps future sessions — the auto-log alone "
            "only has the commit message."
        )
    if decision_msg:
        additional = (
            f"{additional} | {decision_msg}"
            if additional
            else f"[post-commit-memory] {decision_msg}"
        )

    # WHY: feat/refactor commits often involve architectural decisions that
    # should be recorded in decisions.md. Nudge when not already captured
    # by an explicit decision prefix (arch:/decision:/security:/pattern:).
    # Not throttled like the reminder above -- each feat/refactor commit is
    # its own distinct decision point, not a repeat of the same notice.
    _ADR_PREFIXES = ("feat:", "refactor:")
    _needs_adr_nudge = (
        any(commit_msg.lower().startswith(p) for p in _ADR_PREFIXES)
        and extract_decision(commit_msg) is None
    )
    if _needs_adr_nudge:
        adr_line = (
            "📋 ADR nudge: feat/refactor commit — was an architectural choice made? "
            "If yes, add an entry to decisions.md "
            "(format: ### [date] Decision. Type: arch. Commit: hash)"
        )
        additional = (
            f"{additional} | {adr_line}" if additional else f"[post-commit-memory] {adr_line}"
        )

    if additional:
        emit_hook_result("PostToolUse", additional)


if __name__ == "__main__":
    main()
