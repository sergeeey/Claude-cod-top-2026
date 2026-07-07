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

# WHY (HIGH, external security audit 2026-07-07, independently confirmed): a
# read-only shell command is not automatically a SAFE one to auto-allow --
# `cat ~/.ssh/id_rsa` or `cat .env` starts with the auto-allowed "cat "
# prefix, has no chain operator, and would disclose real secrets straight
# into Claude's context with zero user confirmation. Same denylist shape
# already used by pre_commit_guard.py's staged-secrets check, extended with
# a few more common credential-file names relevant to a READ (not commit)
# context.
SENSITIVE_PATH_PATTERNS: tuple[str, ...] = (
    ".env",
    ".ssh",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    "credentials",
    ".pem",
    ".key",
    ".npmrc",
    ".netrc",
    ".aws",
    ".git-credentials",
    "known_hosts",
    "secret",
    "token",
    "password",
    "gh/hosts",  # GitHub CLI's OAuth token file (~/.config/gh/hosts.yml)
    ".docker/config",  # Docker registry auth
    ".kube/config",  # Kubernetes cluster credentials
    ".pgpass",
    "shadow",
)

# WHY only these three: they are the read-only prefixes in SAFE_BASH_PREFIXES
# that take an arbitrary file path argument. "echo "/"ls"/"pwd"/etc. don't
# read file CONTENT the way cat/head/tail do.
_PATH_SENSITIVE_READ_PREFIXES: tuple[str, ...] = ("cat ", "head ", "tail ")


def _reads_sensitive_path(cmd_lower: str) -> bool:
    """True if a cat/head/tail command's target path looks like a secret."""
    for prefix in _PATH_SENSITIVE_READ_PREFIXES:
        if cmd_lower.startswith(prefix):
            return any(pattern in cmd_lower for pattern in SENSITIVE_PATH_PATTERNS)
    return False


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
# WHY ">" is here too: redirection is a write operation, not just chaining,
# but the same "any of these chars disqualifies auto-allow" gate covers it
# correctly. Without it, "echo payload > .env" auto-approved via the "echo "
# safe prefix, since redirection was never treated as unsafe — a single ">"
# substring check also catches "1>", "2>", and ">>" variants for free.
CHAIN_OPERATORS: tuple[str, ...] = ("&&", "||", ";", "|", "`", "$(", "\n", ">")


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

        # WHY checked before the safe-prefix loop below: cat/head/tail are
        # "safe" prefixes for ordinary files, but reading a secret is not
        # made safe just because the read itself has no side effects.
        if _reads_sensitive_path(cmd_lower):
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
