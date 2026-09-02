#!/usr/bin/env python3
"""PreToolUse hook: auto-trigger security review for sensitive file edits.

WHY: Edits to auth, payment, migration, and secret files are high-risk.
Auto-suggesting sec-auditor review prevents accidental security regressions.
"""

import re
import sys

from lib.runtime import HookInputError, emit_permission_decision, get_tool_input, parse_stdin
from lib.security import is_sensitive_file, shell_statement_tokens, split_shell_statements

# WHY a token-position match instead of a regex over raw command text
# (refactored 2026-08-24, falsification-pilot follow-up sweep, onto the
# shared `split_shell_statements`/`shell_statement_tokens` utilities in
# `hooks/lib/security.py`): the original three separate regexes
# (_REDIRECT_TARGET_RE, _TEE_TARGET_RE, _DD_OF_TARGET_RE) each needed their
# own quote-handling and metacharacter-boundary logic, and still missed two
# real quote-splitting bypasses (`> .e'n'v` kept an embedded quote through
# `_strip_quotes`'s positional-only unwrap; `t'e'e` never matched
# `_TEE_TARGET_RE`'s literal `\btee\b` at all -- both independently
# reproduced before being closed with narrower patches). Real shell
# tokenization (`shlex.split(posix=True)`, already proven correct in
# `pre_commit_guard.py`) reconstructs quote-split words exactly as bash
# would, and per-statement splitting (at &&, ||, ;, |, and heredoc-aware
# newlines) gives a natural end to `tee`'s argument list for free, replacing
# the old "stop at the first shell-metacharacter token" heuristic.
#
# WHY a PREFIX match with a captured remainder, not `^...$` full-token match
# (fixed 2026-08-24, security-audit review of this same migration, verified
# before fixing): shlex has no idea `>` is special, so a no-space redirect
# like `echo x >.env` tokenizes as ONE token `>.env`, which a `^...$`
# full-match against the bare operator never matches at all -- silently
# extracting zero targets. Splitting the operator prefix off and using
# whatever text remains (if any) as the glued-on target, falling back to
# "next token" only when nothing remains, closes this without losing the
# already-correct spaced case.
_REDIRECT_PREFIX_RE = re.compile(r"^([012]?>{1,2}\|?)(.*)$")


def _bash_redirect_targets(command: str) -> list[str]:
    """Return every file path a shell command writes to, via redirection
    (>, >>, N>, >|), `tee`, or `dd of=`."""
    targets: list[str] = []
    for statement in split_shell_statements(command):
        tokens = shell_statement_tokens(statement)
        for i, tok in enumerate(tokens):
            redirect_match = _REDIRECT_PREFIX_RE.match(tok)
            if redirect_match and redirect_match.group(1):
                remainder = redirect_match.group(2)
                if remainder:
                    targets.append(remainder)
                elif i + 1 < len(tokens):
                    targets.append(tokens[i + 1])
            elif tok == "tee":
                # WHY every remaining non-flag token, not just the first:
                # `tee a.txt b.txt` writes to BOTH -- matches the original
                # regex's behavior of capturing every following argument up
                # to the statement's own end (which per-statement splitting
                # now provides directly, no metachar-boundary check needed).
                for later in tokens[i + 1 :]:
                    if not later.startswith("-"):
                        targets.append(later)
            elif tok.startswith("of="):
                targets.append(tok[len("of=") :])
    return targets


def main() -> None:
    """Entry point: parse hook data and emit warning for sensitive files."""
    # WHY strict=True + explicit ask, not silent exit (issue #195 follow-up,
    # external audit 2026-07-15): parse_stdin()'s default {} on malformed
    # JSON was indistinguishable from "hook invoked outside normal flow",
    # silently skipping the sensitive-file check entirely. "ask" (not
    # "deny") matches this hook's own established response to a genuine
    # sensitive-file match below -- a parse failure means "could not check
    # whether this touches a sensitive file", which deserves the same
    # user-confirmation escalation, not silent pass-through.
    try:
        data = parse_stdin(strict=True)
    except HookInputError:
        emit_permission_decision(
            decision="ask",
            reason="[sec-verify] Malformed tool_input JSON — could not check whether this "
            "touches a sensitive file (auth/payment/secrets). Please confirm this edit "
            "is safe.",
        )
        return
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
    from lib.runtime import hook_main

    # WHY hook_main + fail_closed=True (issue #195 follow-up, external audit
    # 2026-07-15): this hook previously ran main() bare -- no timeout
    # protection, and a crash/hang would silently let a sensitive-file edit
    # through unflagged. Genuinely fail-closed here means "ask" territory --
    # hook_main's fail_closed always emits "deny" on timeout/crash, which is
    # a stricter escalation than this hook's normal "ask", but consistent
    # with fail_closed's own design: a crash/timeout means the process lost
    # control entirely, so there is no interactive channel left to ask
    # through -- deny is the only meaningful safe fallback at that point.
    hook_main(main, fail_closed=True)
