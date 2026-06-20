#!/usr/bin/env python3
"""Pre-Vault Write Validation — enforce vault methodology.

WHY: Multiple Claude Code sessions can violate vault structure rules
(personal projects in repo-intel, metadata without Path, docs in wrong place).
This hook validates BEFORE writing to prevent structure drift.

WHEN: Pre-tool-use (Write, Edit) when target is in vault
"""

import json
import re
import sys
from pathlib import Path


def validate_vault_write(file_path: str, content: str) -> dict:
    """Validate write operation against vault methodology.

    Returns:
        dict with {allowed: bool, reason: str, suggestion: str}
    """

    vault_root = Path("C:/Users/serge/.claude/memory")

    # Normalize path
    try:
        rel_path = Path(file_path).relative_to(vault_root)
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


def main():
    """Hook entry point."""

    # Read hook input
    hook_input = json.loads(sys.stdin.read())

    tool_name = hook_input.get("tool_name", "")
    params = hook_input.get("parameters", {})

    # Only validate Write/Edit to vault
    if tool_name not in ["Write", "Edit"]:
        print(json.dumps({"allowed": True}))
        return 0

    file_path = params.get("file_path", "")

    # Skip if not in vault
    if "/.claude/memory" not in file_path:
        print(json.dumps({"allowed": True}))
        return 0

    # Get content
    if tool_name == "Write":
        content = params.get("content", "")
    else:  # Edit
        # For Edit, we need to read current file + apply changes
        # Simplified: just check new_string
        content = params.get("new_string", "")

    # Validate
    result = validate_vault_write(file_path, content)

    if not result["allowed"]:
        # Block with explanation
        print(
            json.dumps(
                {
                    "allowed": False,
                    "message": f"""
🚫 Vault Methodology Violation

{result["reason"]}

💡 Suggestion: {result["suggestion"]}

📖 Rule: {result.get("rule", "CLAUDE.md")}

See: C:/Users/serge/.claude/memory/CLAUDE.md for details
""",
                }
            )
        )
        return 1

    # Allow
    print(json.dumps({"allowed": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
