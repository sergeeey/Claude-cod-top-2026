#!/usr/bin/env python3
"""PreToolUse hook: auto-trigger security review for sensitive file edits.

WHY: Edits to auth, payment, migration, and secret files are high-risk.
Auto-suggesting sec-auditor review prevents accidental security regressions.
"""

import re
import sys

from utils import emit_permission_decision, get_tool_input, is_sensitive_file, parse_stdin

# WHY: a Bash command has no file_path field at all -- "printf secret > .env"
# or "echo x >> config/secrets.yml" previously bypassed this gate entirely,
# since main() only ever looked at tool_input["file_path"]. This extracts the
# write target of any shell redirection (>, >>, the 1>/2> fd variants, and the
# >| force-overwrite operator) so it can be checked with is_sensitive_file().
# The optional \|? after >{1,2} matches force-redirect (">|") without also
# matching an unrelated pipe later in the command ("> file | cmd").
_REDIRECT_TARGET_RE = re.compile(r"[012]?>{1,2}\|?\s*(\"[^\"]*\"|'[^']*'|\S+)")

# WHY (cross-model review, 2026-07-06): the redirect-only regex above missed
# two other common ways a shell command writes to a file -- `tee` (reads
# stdin, writes via its own argument, no `>` at all) and `dd of=target`.
# Both were independently demonstrated as live bypasses ("printf SECRET | tee
# .env", "dd if=/dev/null of=.env") by a reviewer-agent pass and a Codex
# cross-model pass before this was closed.
_TEE_TARGET_RE = re.compile(r"\btee\b((?:\s+-\S+)*(?:\s+(?:\"[^\"]*\"|'[^']*'|\S+))+)")
_DD_OF_TARGET_RE = re.compile(r"\bof=(\"[^\"]*\"|'[^']*'|\S+)")
_TOKEN_RE = re.compile(r"\"[^\"]*\"|'[^']*'|\S+")
_SHELL_METACHAR = re.compile(r"[;&|]")


def _strip_quotes(token: str) -> str:
    """Unwrap a matched "quoted path" or 'quoted path' -- so a target with a
    space (e.g. "safe dir/.env") is checked as the real path, not the leading
    quote-plus-first-word fragment a bare \\S+ match would otherwise capture."""
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


def _bash_redirect_targets(command: str) -> list[str]:
    """Return every file path a shell command writes to, via redirection
    (>, >>, N>, >|), `tee`, or `dd of=`."""
    targets = [_strip_quotes(m) for m in _REDIRECT_TARGET_RE.findall(command)]

    for match in _TEE_TARGET_RE.finditer(command):
        for token in _TOKEN_RE.findall(match.group(1)):
            # WHY: skip flags (-a) and stop treating anything containing a
            # shell control character as a file target -- it's the start of
            # the next chained command (&&, ||, ;, |), not a tee argument.
            if token.startswith("-") or _SHELL_METACHAR.search(token):
                continue
            targets.append(_strip_quotes(token))

    targets.extend(_strip_quotes(m) for m in _DD_OF_TARGET_RE.findall(command))
    return targets


def main() -> None:
    """Entry point: parse hook data and emit warning for sensitive files."""
    data = parse_stdin()
    if not data:
        # WHY: Empty stdin means hook was invoked outside normal Claude Code flow.
        # Exit silently — do not block any operation on a parse failure.
        sys.exit(0)

    tool_input = get_tool_input(data)
    file_path = tool_input.get("file_path", "")
    command = tool_input.get("command", "")

    targets = [file_path] if file_path else []
    if command:
        targets.extend(_bash_redirect_targets(command))

    if not targets:
        sys.exit(0)

    sensitive_target = next((t for t in targets if is_sensitive_file(t)), None)
    if sensitive_target:
        # WHY: permissionDecision "ask" (not "deny") — user may have intentionally
        # requested editing a sensitive file. We surface the risk and let them confirm
        # rather than silently blocking. This matches ResearchOps "quality" class:
        # fail-open, user retains control.
        emit_permission_decision(
            decision="ask",
            reason=(
                f"Sensitive file detected: {sensitive_target}. "
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
