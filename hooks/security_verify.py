#!/usr/bin/env python3
"""PreToolUse hook: auto-trigger security review for sensitive file edits.

WHY: Edits to auth, payment, migration, and secret files are high-risk.
Auto-suggesting sec-auditor review prevents accidental security regressions.
"""

import sys

from utils import emit_permission_decision, get_tool_input, is_sensitive_file, parse_stdin


def main() -> None:
    """Entry point: parse hook data and emit warning for sensitive files."""
    data = parse_stdin()
    if not data:
        # WHY: Empty stdin means hook was invoked outside normal Claude Code flow.
        # Exit silently — do not block any operation on a parse failure.
        sys.exit(0)

    tool_input = get_tool_input(data)
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    if is_sensitive_file(file_path):
        # WHY: permissionDecision "ask" (not "deny") — user may have intentionally
        # requested editing a sensitive file. We surface the risk and let them confirm
        # rather than silently blocking. This matches ResearchOps "quality" class:
        # fail-open, user retains control.
        emit_permission_decision(
            decision="ask",
            reason=(
                f"Sensitive file detected: {file_path}. "
                "This file may contain secrets, auth logic, or payment processing. "
                "Consider running the sec-auditor agent before proceeding."
            ),
            context=(
                "[SEC-VERIFY] High-risk edit. "
                "Run: Agent(sec-auditor, prompt='Review changes to ...') after editing."
            ),
        )


if __name__ == "__main__":
    main()
