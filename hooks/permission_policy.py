#!/usr/bin/env python3
"""PermissionRequest hook: programmatic permission decisions.

WHY: Reduces permission prompts by ~75%. Read-only tools are always safe,
dangerous commands are always blocked, everything else asks the user.
"""

import json

from utils import get_tool_input, parse_stdin

ALWAYS_SAFE_TOOLS: tuple[str, ...] = (
    "Read",
    "Glob",
    "Grep",
    "Task",
    "TaskCreate",
    "TaskUpdate",
    "TaskList",
    "TaskGet",
    "WebSearch",
    "WebFetch",
)

SAFE_BASH_PREFIXES: tuple[str, ...] = (
    "git status",
    "git log",
    "git diff",
    "git branch",
    "git show",
    "pytest",
    "python -m pytest",
    "ruff",
    "mypy",
    "npm test",
    "npm run test",
    "npm run lint",
    "ls",
    "pwd",
    "cat ",
    "head ",
    "tail ",
    "wc ",
    "echo ",
    "which ",
    "python --version",
    "node --version",
)

DANGEROUS_PATTERNS: tuple[str, ...] = (
    "rm -rf",
    "rm -r -f",
    "DROP TABLE",
    "DROP DATABASE",
    "TRUNCATE TABLE",
    "DELETE FROM",
    "git push --force",
    "git push -f",
    "git reset --hard",
    "git clean -fd",
    "chmod 777",
    "chmod a+rwx",
    "format C:",
    "format D:",
    "del /s /q",
    "rmdir /s /q",
    "npm publish",
    "pip install --break-system-packages",
    "curl | bash",
    "curl | sh",
    "wget | bash",
    "wget | sh",
    "sudo ",
    "mkfs",
    "dd if=",
    "> /dev/sd",
    "python -c",
    "python3 -c",
    "eval ",
    "base64 -d",
    "base64 --decode",
    "powershell -enc",
    "powershell -e ",
    "certutil -urlcache",
    "reg delete",
    "shutdown",
    "reboot",
    "kill -9",
    "killall",
    "nohup",
)

# WHY: shell metacharacters indicate command chaining — a "safe" prefix
# followed by && or | can execute arbitrary commands after the safe one.
CHAIN_OPERATORS: tuple[str, ...] = ("&&", "||", ";", "|", "`", "$(", "\n")


def decide(tool_name: str, tool_input: dict) -> tuple[str, str]:
    """Return (behavior, message) tuple."""
    # WHY: read-only tools never modify state — safe to auto-approve
    if tool_name in ALWAYS_SAFE_TOOLS:
        return ("allow", "")

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        cmd_lower = command.lower().strip()

        # WHY: check dangerous first — deny takes priority over allow
        for pattern in DANGEROUS_PATTERNS:
            if pattern.lower() in cmd_lower:
                return ("deny", f"Blocked dangerous command: {pattern}")

        # WHY: any command with chaining operators is not safe to auto-approve,
        # even if it starts with a safe prefix like "git status && rm -rf /"
        for op in CHAIN_OPERATORS:
            if op in command:
                return ("ask", "")

        # WHY: safe bash prefixes are read-only or standard dev tools
        # Only checked AFTER chain operators are excluded
        for prefix in SAFE_BASH_PREFIXES:
            if cmd_lower.startswith(prefix.lower()):
                return ("allow", "")

    # WHY: default to asking — explicit user consent for unknown operations
    return ("ask", "")


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    tool_name = data.get("tool_name", data.get("tool", ""))
    tool_input = get_tool_input(data)

    behavior, message = decide(tool_name, tool_input)

    result: dict = {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {"behavior": behavior},
        }
    }
    if message and behavior == "deny":
        result["hookSpecificOutput"]["decision"]["message"] = message

    print(json.dumps(result))


if __name__ == "__main__":
    main()
