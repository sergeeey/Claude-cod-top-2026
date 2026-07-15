#!/usr/bin/env python3
"""Pre-Vault Write Validation — enforce vault methodology.

WHY: Multiple Claude Code sessions can violate vault structure rules
(personal projects in repo-intel, metadata without Path, docs in wrong place).
This hook validates BEFORE writing to prevent structure drift.

WHEN: Pre-tool-use (Write, Edit) when target is in vault
"""

import re
from pathlib import Path

from utils import HookInputError, emit_permission_decision, get_tool_input, parse_stdin


def validate_vault_write(file_path: str, content: str) -> dict:
    """Validate write operation against vault methodology.

    Returns:
        dict with {allowed: bool, reason: str, suggestion: str}
    """

    vault_root = Path.home() / ".claude" / "memory"

    # Normalize path
    # WHY .resolve() on BOTH sides (HIGH, cross-model audit): without it,
    # a file_path like "<vault_root>/projects/../_auto/foo.md" keeps its
    # literal ".." segment through relative_to(), producing rel_path =
    # "projects/../_auto/foo.md" -- which does NOT start with "_auto/", so
    # Check 4 below never fires, even though the OS will actually resolve
    # the ".." and write into the read-only _auto/ folder. Resolving first
    # normalizes the traversal before any prefix check runs.
    try:
        rel_path = Path(file_path).resolve().relative_to(vault_root.resolve())
    except ValueError:
        # Not in vault — skip validation
        return {"allowed": True}

    rel_path_str = str(rel_path).replace("\\", "/")

    # Check 1: Personal project in repo-intel?
    if "repo-intel/" in rel_path_str:
        if "sergeeey" in content.lower() or "github.com/sergeeey" in content:
            return {
                "allowed": False,
                "reason": "Personal project detected in repo-intel/ folder",
                "suggestion": "Move to projects/ — repo-intel is for external repos only",
                "rule": "CLAUDE.md § Hard Rules #1",
            }

    # Check 2: Project metadata without Path?
    if rel_path_str.startswith("projects/") and file_path.endswith(".md"):
        # Skip special files
        special_files = ["Dashboard", "_docs", "_archive", "_auto", "CLAUDE.md"]
        if not any(s in file_path for s in special_files):
            if "## Path:" not in content:
                return {
                    "allowed": False,
                    "reason": "Project metadata file missing ## Path: field",
                    "suggestion": "Add '## Path: Drive:/Folder Name/' after title",
                    "rule": "CLAUDE.md § Hard Rules #2",
                }

    # Check 3: Documentation in projects root (not _docs/)?
    if rel_path_str.startswith("projects/") and not rel_path_str.startswith("projects/_"):
        # Check frontmatter type
        if match := re.search(r"type:\s*(roadmap|strategy|spec|report|plan)", content):
            doc_type = match.group(1)
            return {
                "allowed": False,
                "reason": f"Documentation (type={doc_type}) in projects/ root instead of _docs/",
                "suggestion": f"Move to projects/_docs/[project-name]/{Path(file_path).name}",
                "rule": "CLAUDE.md § Hard Rules #3",
            }

    # Check 4: Editing _auto/?
    if rel_path_str.startswith("_auto/"):
        return {
            "allowed": False,
            "reason": "_auto/ folder is read-only (auto-generated content)",
            "suggestion": "Edit raw/ instead — changes will auto-sync to _auto/wiki/",
            "rule": "CLAUDE.md § Hard Rules #4",
        }

    # All checks passed
    return {"allowed": True}


def _reconstruct_content(file_path: str, tool_input: dict) -> str:
    """Best-effort reconstruction of the file's content AFTER this write.

    WHY (mirrors promotion_gate_guard.py's _reconstruct_content, same
    reasoning): Write's `content` IS the full proposed file. Edit only
    carries old_string/new_string, so checking new_string alone can miss
    an already-present violation elsewhere in the file (e.g. a "## Path:"
    field the edit doesn't touch) or wrongly flag a violation the edit
    doesn't actually introduce. Reconstructing against the CURRENT on-disk
    content gives validate_vault_write() the same full-file view Write gets.
    """
    if "content" in tool_input:
        return str(tool_input.get("content", ""))

    old_string = str(tool_input.get("old_string", ""))
    new_string = str(tool_input.get("new_string", ""))
    try:
        current = Path(file_path).read_text(encoding="utf-8")
    except OSError:
        return new_string  # file doesn't exist yet -- best available guess

    if old_string and old_string in current:
        return current.replace(old_string, new_string, 1)
    return current


def main() -> None:
    """Hook entry point.

    WHY get_tool_input(), not hook_input["parameters"] (HIGH, external
    re-audit 2026-07-07): the real Claude Code PreToolUse envelope carries
    the tool's arguments under `tool_input`, not `parameters` -- every other
    hook in this repo uses get_tool_input() for exactly this reason. Reading
    the wrong field meant file_path was always "", so this hook silently
    allowed every write regardless of vault methodology violations, AND
    (separately) was never even registered in settings.json -- dead code
    that looked like a working guard.

    WHY silent on allow, not an explicit emit_permission_decision("allow")
    call: matches this repo's established convention (security_verify.py) --
    a PreToolUse hook that has no objection stays silent rather than printing
    a redundant "allow" every single Write/Edit call.
    """
    # WHY strict=True + explicit deny (issue #195, external audit 2026-07-15
    # follow-up): parse_stdin()'s default {} return on malformed JSON was
    # indistinguishable from "nothing to check", so `if not hook_input:
    # return` silently bypassed hook_main(fail_closed=True) entirely -- no
    # exception ever propagated for fail_closed's crash handling to catch.
    # A malformed tool_input means this hook could not check for a vault
    # methodology violation, which is not evidence the write is safe.
    try:
        hook_input = parse_stdin(strict=True)
    except HookInputError:
        emit_permission_decision(
            decision="deny",
            reason="[pre-vault-write] Malformed tool_input JSON — cannot check vault "
            "methodology, failing closed.",
        )
        return
    if not hook_input:
        return

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        return

    tool_input = get_tool_input(hook_input)
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return

    content = _reconstruct_content(file_path, tool_input)

    # WHY no separate "/.claude/memory" substring pre-check here (second bug
    # found alongside the schema fix): that literal forward-slash check
    # never matches a Windows-style file_path (backslashes), which would
    # make this hook a no-op on this repo's primary dev OS even after fixing
    # the schema above. validate_vault_write() already does the correct,
    # portable check via Path(...).resolve().relative_to(vault_root) and
    # returns {"allowed": True} for anything outside the vault -- it's the
    # single source of truth for "is this even in scope", not duplicated here.
    result = validate_vault_write(file_path, content)

    if not result["allowed"]:
        reason = (
            f"🚫 Vault Methodology Violation\n\n"
            f"{result['reason']}\n\n"
            f"💡 Suggestion: {result['suggestion']}\n\n"
            f"📖 Rule: {result.get('rule', 'CLAUDE.md')}\n\n"
            f"See: {Path.home() / '.claude' / 'memory' / 'CLAUDE.md'} for details"
        )
        emit_permission_decision(decision="deny", reason=reason)


if __name__ == "__main__":
    from utils import hook_main

    # WHY fail_closed=True (F-10, external audit 2026-07-15): this hook can
    # genuinely DENY a vault write (PreToolUse, Edit|Write matcher) — a
    # timeout/crash must not silently allow the write it exists to gate.
    hook_main(main, fail_closed=True)
