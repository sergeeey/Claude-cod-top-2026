#!/usr/bin/env python3
"""PostToolUse hook for Bash: auto-log commits to activeContext.md.

WHY: memory_guard only REMINDS to update context. This hook ACTS —
it automatically appends the commit log to activeContext.md. Double safety net:
1. Auto-log (commit fact recorded)
2. Reminder for Claude to supplement context manually (auto-log is the minimum)

Difference from memory_guard: memory_guard checks file freshness.
post_commit_memory maintains a structured commit log.
"""

from datetime import datetime
from pathlib import Path

from utils import (
    emit_hook_result,
    extract_tool_response,
    find_file_upward,
    find_project_memory,
    get_tool_input,
    is_failed_commit,
    parse_stdin,
    run_git,
)


def find_decisions_file() -> Path | None:
    """Find decisions.md walking up from CWD."""
    return find_file_upward(str(Path(".claude") / "memory" / "decisions.md"))


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

    now = datetime.now().strftime("%Y-%m-%d")
    # Format: ### [date] Description. Type: X. Commit: hash
    entry = f"\n### [{now}] {description}\n- Type: {decision_type}\n- Commit: `{commit_hash}`\n"

    content = decisions_file.read_text(encoding="utf-8")
    # Append at the end
    content = content.rstrip() + "\n" + entry
    decisions_file.write_text(content, encoding="utf-8")

    return f"Auto-recorded [{decision_type}] decision to decisions.md"


def main() -> None:
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
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    log_entry = f"- [{now}] `{commit_hash}`: {commit_msg}\n"

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
            content = "\n".join(lines)
    else:
        # Create section at end of file
        content = content.rstrip() + f"\n\n{section_header}\n{log_entry}"

    active_ctx.write_text(content, encoding="utf-8")

    # Nexus-lite: auto-record decisions from commit message prefixes
    decision_msg = log_decision(commit_hash, commit_msg)

    # Reminder for Claude to supplement context manually
    additional = (
        f"[post-commit-memory] Auto-logged commit {commit_hash} to activeContext.md. "
        "Please also update the context manually with WHAT was done and WHY — "
        "the auto-log only captures the commit message."
    )
    if decision_msg:
        additional += f" | {decision_msg}"

    emit_hook_result("PostToolUse", additional)


if __name__ == "__main__":
    main()
