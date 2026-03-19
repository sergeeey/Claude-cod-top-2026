#!/usr/bin/env python3
"""PreToolUse hook: remind to Read before Edit/Write.

Outputs a warning via stderr when Edit or Write is called,
reminding Claude to verify that the target file was Read first.
Does NOT block — soft nudge that works with Evidence Policy.

Matcher: Edit|Write
"""

import sys

from utils import parse_stdin


def main():
    data = parse_stdin()
    if not data:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Write to new files is always OK (no existing content to read)
    # For Edit, always remind
    if tool_name == "Edit":
        print(
            f"[read-before-edit] Editing {file_path}. "
            f"Confirm: did you Read this file first? "
            f"If not, Read it before editing — [MEMORY] does not replace [VERIFIED].",
            file=sys.stderr,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
