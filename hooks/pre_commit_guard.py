#!/usr/bin/env python3
"""PreToolUse hook for Bash: guard git commit operations.

WHY: Direct commit to main/master is a common mistake that breaks workflow.
Staged .env or debug statements are a security/quality risk. The hook catches this
BEFORE command execution, not after.

Checks:
1. git commit in main/master → BLOCK
2. Staged high-confidence secret files (.env, .pem, id_rsa, ...) → BLOCK
   (medium-confidence patterns like generic "credentials"/"secret" → WARNING)
   WHY hard-block, not just warn (external security audit 2026-07-07,
   user-confirmed decision): a warning can be ignored; once a real secret
   reaches git history, removing it requires a history rewrite. The cost
   asymmetry favors blocking by default, with an explicit, logged override
   (ALLOW_SECRET_COMMIT=1 + ALLOW_SECRET_COMMIT_REASON="...") for real
   false positives like test fixtures.
3. Debug statements in diff → WARNING
4. ruff check on staged .py files → BLOCK if lint errors found
   WHY: enforcement, not reminder — bugs are always found in post-hoc review,
   so gate them before the commit lands. ruff is fast (<1s), zero false positives.
5. README test-count badge freshness reminder (only when tests/ or skills/
   staged) → WARNING
   WHY (retrospective, 2026-07-07): the README badge drift documented as
   [AVOID x4] in memory (PR #115/#124/#125) recurred TWICE MORE in a single
   session despite the rule already being known -- a reactive "fix it when
   CI complains" sync is not enough; the drift needs to be surfaced at the
   moment the count-changing commit is staged, not discovered later.

   WHY a plain reminder, not a local-vs-badge count comparison (reviewer P1,
   caught before merge): the first version of this check ran a local
   `pytest --collect-only` and compared it against README's badge number.
   But scripts/sync_readme_from_ci.py's OWN docstring documents that local
   pytest counts more tests than CI (env-dependent tests --
   test_artifact_schema_validator needs the global ~/.claude hook,
   test_registry_matches_disk needs PyYAML absent from CI's minimal deps).
   Measured directly: local --collect-only reported 2034 against a
   README badge of 2009 that CI had ALREADY correctly synced moments
   earlier -- a 25-test gap with zero real staleness. A check that fires on
   every relevant commit regardless of whether anything is actually wrong is
   the exact "cried wolf" failure mode this whole exercise was meant to
   fix, and CI is the only environment that can authoritatively answer "is
   the badge correct" (see sync_readme_from_ci.py) -- a local pre-commit
   hook fundamentally cannot verify that without either running the full
   suite in a matching environment (defeats the point: cheap and fast) or
   reproducing CI's exact dependency set locally (fragile, drifts on its
   own). So: warn unconditionally when the trigger fires, pointing at the
   one command that IS authoritative, instead of guessing with a number
   this hook cannot trust.
"""

import os
import re
import subprocess
import sys

from lib.discovery import extract_command_cwd, normalize_gitbash_drive_path, run_git
from lib.runtime import (
    HookInputError,
    emit_hook_result,
    emit_permission_decision,
    get_tool_input,
    parse_stdin,
)
from lib.security import shell_statement_tokens, split_shell_statements

# WHY these two prefixes specifically: they are exactly the inputs to the
# README Tests badge and CI's "Verify README metrics match reality" step --
# a commit touching anything else can't have changed the test count.
_DOC_COUNT_TRIGGER_PREFIXES: tuple[str, ...] = ("tests/", "skills/")


def _staged_files_touch_doc_count_inputs(staged_files: list[str]) -> bool:
    return any(f.startswith(_DOC_COUNT_TRIGGER_PREFIXES) for f in staged_files)


# WHY regex-anchored, not a bare substring list (P1, reviewer-agent pass,
# 2026-07-07): ".key" as a plain substring matched "keychain.py",
# "config.keystore.py", "hot.keys.json" -- none of them secrets, all
# reproduced concretely. A WARNING tolerates that false-positive rate; a
# HARD BLOCK does not, since it stops a commit outright rather than just
# annotating it. Anchoring each extension-shaped pattern to "immediately
# followed by another dot or end-of-string" (\.ext(\.|$)) keeps it matching
# a real secret-file suffix (.env, .env.local, api.key, api.key.ts) while
# rejecting the same substring mid-word (keychain, keystore, keys.json).
_HIGH_CONFIDENCE_EXTENSION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\.env(\.|$)"),
    re.compile(r"\.pem(\.|$)"),
    re.compile(r"\.key(\.|$)"),
    re.compile(r"\.pypirc(\.|$)"),
    re.compile(r"\.npmrc(\.|$)"),
    re.compile(r"\.netrc(\.|$)"),
)

# WHY plain substrings, not anchored like the extensions above: these are
# specific filename fragments (an SSH key basename, a literal path
# fragment), not generic word-fragments that collide with unrelated compound
# words -- "id_rsa" or "gh/hosts.yml" appearing anywhere in a path is
# essentially always the real thing, unlike ".key" which collides with
# "keychain"/"keystore"/"keys".
_HIGH_CONFIDENCE_SUBSTRING_PATTERNS: tuple[str, ...] = (
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    ".git-credentials",
    "gh/hosts.yml",
)

# WHY excluded even though they'd otherwise match a pattern above: these are
# recognized safe/example naming conventions, not real secrets -- e.g.
# ".env.example" or "fixtures/fake_id_rsa" should never block a commit.
_SAFE_SECRET_LOOKALIKE_MARKERS: tuple[str, ...] = (
    ".example",
    ".template",
    ".sample",
    "dummy",
    "fixture",
    "fake",
)

# WHY these stay WARNING-only, not BLOCK: generic words like "credentials"/
# "secret"/"token" appear in plenty of legitimate filenames (e.g.
# "test_credentials.py", "token_refresh.py") -- high false-positive risk if
# hard-blocked, so they keep the pre-existing advisory behavior.
_MEDIUM_CONFIDENCE_SECRET_PATTERNS: tuple[str, ...] = ("credentials", "secret", "token")

# WHY a separate, narrower list from utils.redact_secrets()'s full pattern
# table (F-09, external audit 2026-07-15): that table also matches PII
# (email/phone/card/passport) -- appropriate for redacting a log line, far
# too false-positive-prone for a hard commit BLOCK (an email address in a
# commit is not a leaked credential). This subset is exactly the gap the
# audit found: Check 2 above only ever scanned staged FILE NAMES via `git
# diff --cached --name-only` -- a real API key pasted into an innocuously
# named file (e.g. config.py, notes.md) was invisible to it regardless of
# filename. Each pattern here is a vendor-specific token SHAPE (not a generic
# word), so the false-positive rate matches the existing high-confidence
# filename patterns above, not the medium-confidence ones.
_HIGH_CONFIDENCE_CONTENT_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{82}"),
    re.compile(r"xox[abprs]-[A-Za-z0-9\-]{10,}"),
)


def _staged_content_secret_hits(diff_text: str) -> list[str]:
    """Scan only ADDED lines of a `git diff --cached` for known secret-token
    shapes. Returns the list of matched substrings (empty if none)."""
    hits: list[str] = []
    for line in diff_text.split("\n"):
        # WHY: only added lines (starting with +), not removed/context ones —
        # same convention as the existing debug-statement scan (Check 3).
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for pattern in _HIGH_CONFIDENCE_CONTENT_SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                hits.append(match.group(0))
    return hits


def _is_safe_secret_lookalike(f_lower: str) -> bool:
    return any(marker in f_lower for marker in _SAFE_SECRET_LOOKALIKE_MARKERS)


def _is_high_confidence_secret(f_lower: str) -> bool:
    if any(p.search(f_lower) for p in _HIGH_CONFIDENCE_EXTENSION_PATTERNS):
        return True
    return any(p in f_lower for p in _HIGH_CONFIDENCE_SUBSTRING_PATTERNS)


# WHY: the hook process's own cwd is fixed per session (the harness's project
# root) — it does NOT follow a `cd <other-repo> && git commit ...` inside the
# command being inspected. Without this, Check 1 always reports the SESSION's
# repo/branch, not the one the command actually targets, in any multi-repo
# session. `extract_command_cwd` now lives in utils.py (2026-07-21) — a second
# hook (gitnexus_reindex.py) needs the identical cwd-extraction and importing
# this file directly isn't safe (see utils.py's comment on the move for why).

# WHY (cross-model audit, hooks-02): a bare `"git commit" not in command`
# substring check is bypassed by `git -C <repo> commit ...` or `git -c
# user.name=x commit ...` -- the literal substring "git commit" never
# appears even though `commit` IS the subcommand being run. Global options
# that take a separate value (space-delimited) must be skipped explicitly;
# `--opt=value` and bare flags (`-p`, `--no-pager`) are single tokens.
_GIT_GLOBAL_OPTS_WITH_VALUE = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
)

# WHY imported, not defined here anymore (refactored 2026-08-24,
# falsification-pilot follow-up sweep): this hook's own statement-splitting
# (chain operators + heredoc-aware) and shlex tokenization (with a naive
# fallback on malformed quoting) were the FIRST correct implementation of
# this pattern in the repo -- three OTHER hooks each independently patched
# a narrower, less robust version of the same problem on the same day
# before this was noticed and extracted into `hooks/lib/security.py` as
# `split_shell_statements`/`shell_statement_tokens`. Using the shared
# version here too (instead of keeping this file's own copy) means a future
# fix to either function (e.g. the `>|` force-redirect chain-split bug
# found while migrating security_verify.py onto it) benefits this hook
# automatically instead of silently drifting out of sync.
_split_statements = split_shell_statements
_statement_tokens = shell_statement_tokens


def _git_subcommand_and_args(tokens: list[str]) -> tuple[str, list[str]] | None:
    """If tokens contain a `git <subcommand> ...` invocation (skipping global
    options like -C/-c/--git-dir), return (subcommand, remaining_args)."""
    for i, tok in enumerate(tokens):
        if tok != "git":
            continue
        j = i + 1
        while j < len(tokens):
            t = tokens[j]
            if t in _GIT_GLOBAL_OPTS_WITH_VALUE:
                j += 2
                continue
            if t.startswith("-"):
                j += 1
                continue
            break
        if j < len(tokens):
            return tokens[j], tokens[j + 1 :]
        return None
    return None


def _git_commit_dash_c_dirs(tokens: list[str]) -> list[str] | None:
    """If tokens contain `git [global opts] commit ...`, return the `-C <dir>`
    values in order (empty list if none); None if the subcommand is not commit.

    Mirrors `_git_subcommand_and_args`' option skipping (first `git` token only)
    so both functions agree on which statement is "the commit"."""
    for i, tok in enumerate(tokens):
        if tok != "git":
            continue
        dirs: list[str] = []
        j = i + 1
        while j < len(tokens):
            t = tokens[j]
            if t in _GIT_GLOBAL_OPTS_WITH_VALUE:
                if t == "-C" and j + 1 < len(tokens):
                    dirs.append(tokens[j + 1])
                j += 2
                continue
            if t.startswith("-"):
                j += 1
                continue
            break
        if j < len(tokens) and tokens[j] == "commit":
            return dirs
        return None
    return None


def _resolve_commit_cwd(command: str) -> str | None:
    """Directory the commit in `command` really runs in, or None for the hook's own cwd.

    WHY: `cd B && git commit` was handled (extract_command_cwd), but
    `git -C B commit` was only DETECTED as a commit (hooks-02) -- its target
    was never used, so branch protection, the staged-file secret scan and the
    ruff check all ran against the SESSION's repo instead of B. `-C` values are
    cumulative like git itself (`-C a -C sub` -> a/sub) and a relative value
    resolves against the `cd` target if there is one, else the hook's cwd.

    Returns the target of the FIRST commit statement. That is only sound because
    `_commit_chain_problem` denies a command whose commits point at more than one
    directory; call it first. `--git-dir`, `--work-tree` and `GIT_DIR=` are skipped,
    not used as the target (same as before this fix), except in combination with
    `-C`, which `_commit_chain_problem` denies as ambiguous."""
    base = extract_command_cwd(command)
    for statement in _split_statements(command):
        dirs = _git_commit_dash_c_dirs(_statement_tokens(statement))
        if dirs is None:
            continue
        return _apply_dash_c(dirs, base)
    return base


def _apply_dash_c(dirs: list[str], base: str | None) -> str | None:
    """Fold `-C` values onto `base` (the `cd` target or None) the way git does."""
    target = base
    for d in dirs:
        # WHY strip quotes: when a statement has an unclosed quote (e.g. a heredoc commit
        # message), the tokenizer falls back to a whitespace split and the value keeps
        # its literal quotes; joined onto the cwd that became a bogus path and a false deny.
        if len(d) >= 2 and d[0] == d[-1] and d[0] in "\"'":
            d = d[1:-1]
        if not d:  # `-C ""` is a no-op for git
            continue
        d = normalize_gitbash_drive_path(os.path.expanduser(d))
        target = d if os.path.isabs(d) else os.path.join(target or os.getcwd(), d)
    return target


_REPO_REDIRECT_OPTS = ("--git-dir", "--work-tree")
_REPO_REDIRECT_ENV = ("GIT_DIR=", "GIT_WORK_TREE=")


def _commit_redirects_repo(tokens: list[str]) -> bool:
    """True if the `git ... commit` statement carries --git-dir/--work-tree (bare
    or `=` form) or a GIT_DIR=/GIT_WORK_TREE= prefix: git then uses THAT repo no
    matter what `-C` says."""
    for i, tok in enumerate(tokens):
        if tok != "git":
            continue
        if any(t.startswith(_REPO_REDIRECT_ENV) for t in tokens[:i]):
            return True
        j = i + 1
        while j < len(tokens):
            t = tokens[j]
            if t in _GIT_GLOBAL_OPTS_WITH_VALUE:
                if t in _REPO_REDIRECT_OPTS:
                    return True
                j += 2
                continue
            if t.startswith("-"):
                if t.startswith(tuple(o + "=" for o in _REPO_REDIRECT_OPTS)):
                    return True
                j += 1
                continue
            break
        return False
    return False


def _commit_chain_problem(command: str) -> str | None:
    """Reason string when the commits in `command` cannot be attributed to ONE
    repository directory, else None.

    WHY (sec-audit of a5770bb, reproduced in an isolated run): resolving only the
    first commit statement let `git -C <feat> commit && git commit` (or a second
    `-C <main-repo>`) hide the later commit from every check; before the `-C`
    fix those were all checked against the session repo. One command = one
    checked target. `-C` combined with --git-dir/--work-tree/GIT_DIR= is also
    ambiguous (git ignores `-C` for locating the repo) and is denied. A lone
    --git-dir without `-C` keeps its old behaviour (a known gap, not widened).

    A `-C` commit that shares the command with a commit-looking statement the
    tokenizer cannot parse (`bash -c '...'`, `eval`, a subshell, `git.exe`, a full
    path to git) or with an exported GIT_DIR/GIT_WORK_TREE is denied too (final
    sec re-audit): the old code checked the session repo and thereby covered such
    a hidden commit; checking only the `-C` target would not.

    Limits, stated so "one command = one target" is not over-read. This is a parser
    of command TEXT, an accident guard, not a security boundary. A second commit
    hidden next to a visible `-C` commit stays unseen when it sits after a
    heredoc-confusing line (`<<<`, a quoted `<<`), after a backslash-newline, behind a
    git alias, `source`/a script, a shell variable (`$G commit`), or a wrapper whose
    option takes a value (`sudo -u x git ...`). WITHOUT a visible `-C` commit these
    were already unseen in 7830bab. NEXT TO one, 7830bab denied them only by
    coincidence (it checked the session repo whatever `-C` said), so for these
    forms the new code is weaker; closing them needs a real Git-level control
    (pre-commit / reference-transaction hooks), not more text parsing. Several
    `cd`s in one command (the LAST `cd` is the base for every statement) are not
    tracked either; that was already so before the `-C` fix."""
    base = extract_command_cwd(command)
    targets: set[str] = set()
    has_dash_c = False
    hidden_commit = False
    env_redirect = False
    for statement in _split_statements(command):
        tokens = _statement_tokens(statement)
        dirs = _git_commit_dash_c_dirs(tokens)
        if dirs is not None and _command_word(tokens) != "git":
            # WHY: the splitter breaks a multi-line quoted message into statements, so a
            # body line like `mentions git commit hook` looks like a commit. `git` is
            # not at command position there: it is message text, not a second commit.
            dirs = None
        if dirs is None:
            hidden_commit = hidden_commit or _looks_like_unparsed_commit(statement, tokens)
            env_redirect = env_redirect or _exports_repo_env(tokens)
            continue
        if dirs:
            has_dash_c = True
        if dirs and _commit_redirects_repo(tokens):
            return (
                "`-C` is combined with --git-dir/--work-tree/GIT_DIR=, so the target is ambiguous"
            )
        target = _apply_dash_c(dirs, base) or os.getcwd()
        # realpath, not abspath: resolves symlinks/junctions/8.3 names so two spellings of
        # one directory compare equal and `link/..` is not collapsed lexically.
        targets.add(os.path.normcase(os.path.realpath(target)))
    if len(targets) > 1:
        return "this command commits in more than one repository directory"
    if has_dash_c and hidden_commit:
        return (
            "a commit this hook cannot parse (bash -c, eval, subshell, git.exe, full path to git) "
            "shares the command with a `-C` commit"
        )
    if has_dash_c and env_redirect:
        return "GIT_DIR/GIT_WORK_TREE is exported in the same command as a `-C` commit"
    return None


_COMMIT_WORD_RE = re.compile(r"\bcommit\b")
# IGNORECASE: on Windows `Git`/`GIT.EXE` run the same binary but are not the token `git`.
_GIT_WORD_RE = re.compile(r"(?:^|[\s(\"'`;&|{=/\\])git(?:\.exe)?(?=[\s\"'`)]|$)", re.IGNORECASE)
_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_COMMAND_WRAPPERS = frozenset(
    {"env", "command", "time", "nohup", "sudo", "doas", "exec", "nice", "xargs", "(", "{", "!"}
)
_SHELL_INTERPRETERS = frozenset({"bash", "sh", "zsh", "dash", "ksh", "eval", "source", "."})
_QUOTED_SPAN_RE = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'[^']*'")
_ENV_DECLARERS = frozenset({"export", "declare", "typeset", "local", "readonly"})
_REPO_ENV_NAMES = frozenset({"GIT_DIR", "GIT_WORK_TREE"})


def _command_word(tokens: list[str]) -> str:
    """The word at command position: first token that is not a VAR=val assignment,
    a wrapper (`env`, `time`, `sudo`, `xargs`, `(`...) or an option. `(git` -> `git`."""
    for t in tokens:
        if _ASSIGNMENT_RE.match(t) or t in _COMMAND_WRAPPERS or t.startswith("-"):
            continue
        return t.lstrip("({")
    return ""


def _mask_data_quotes(statement: str) -> str:
    """Blank out quoted spans that are data, not code: single-quoted spans always, and
    double-quoted spans unless they contain `$(` or a backtick (those still run)."""

    def repl(m: re.Match[str]) -> str:
        s = m.group(0)
        return s if s[0] == '"' and ("$(" in s or "`" in s) else " "

    return _QUOTED_SPAN_RE.sub(repl, statement)


def _looks_like_unparsed_commit(statement: str, tokens: list[str]) -> bool:
    """True if `statement` runs git and the word commit but is NOT a statement the
    tokenizer recognises as `git <subcommand>`: e.g. `bash -c 'git commit'`,
    `( git commit )`, `eval '...'`, `git.exe commit`, `/usr/bin/git commit`.
    A recognised other subcommand (`git log --grep commit`) is not flagged, and
    neither is quoted text that is only data (`echo "ran git commit ok"`,
    `gh pr create --body "fix git commit guard"`) -- unless the command is a shell
    interpreter (`bash -c`, `eval`, `source`), where the quoted text IS the code."""
    if _git_subcommand_and_args(tokens) is not None:
        return False
    interpreter = _command_word(tokens) in _SHELL_INTERPRETERS
    text = statement if interpreter else _mask_data_quotes(statement)
    return bool(_COMMIT_WORD_RE.search(text) and _GIT_WORD_RE.search(text))


def _exports_repo_env(tokens: list[str]) -> bool:
    """True for `export|declare|typeset|local|readonly [-x] GIT_DIR[=...]` (also
    GIT_WORK_TREE) or a bare `GIT_DIR=...` assignment statement: later git calls in
    the chain then use that repo whatever `-C` says."""
    if not tokens:
        return False
    rest = tokens[1:] if tokens[0] in _ENV_DECLARERS else tokens[:1]
    return any(t.startswith(_REPO_REDIRECT_ENV) or t in _REPO_ENV_NAMES for t in rest)


def _unusable_dash_c_target(command: str) -> str | None:
    """Reason string when a `git -C <dir> commit` target cannot be trusted, else None.

    WHY: `run_git` swallows a missing cwd (FileNotFoundError -> ""), so an
    unresolvable target would turn every check into an empty result, i.e. a
    silent pass. The shell expands `$VAR`, `$(...)` and backticks but this hook
    does not, and a missing directory means git itself will fail or hit a
    different repo. Fail closed instead of checking nothing."""
    for statement in _split_statements(command):
        dirs = _git_commit_dash_c_dirs(_statement_tokens(statement))
        if dirs is None:
            continue
        if not dirs:
            return None
        if any("$" in d or "`" in d for d in dirs):
            return (
                "a `-C` value uses shell expansion ($VAR, $(...) or backticks) "
                "that the hook cannot resolve"
            )
        target = _resolve_commit_cwd(command)
        if target is not None and not os.path.isdir(target):
            return f"the `-C` target is not an existing directory: {target}"
        # WHY: an existing directory that is not a repo (or that Python and Git Bash
        # resolve differently, e.g. /tmp) makes every run_git return "" -> silent pass.
        if target is not None and not run_git(["rev-parse", "--git-dir"], cwd=target):
            return f"the `-C` target is not a git repository: {target}"
        return None
    return None


def _command_has_git_commit(command: str) -> bool:
    """True if any statement in `command` is a `git ... commit` invocation,
    regardless of global options like `-C <repo>` between `git` and `commit`."""
    for statement in _split_statements(command):
        parsed = _git_subcommand_and_args(_statement_tokens(statement))
        if parsed and parsed[0] == "commit":
            return True
    return False


def _matches_protected_ref(arg: str) -> bool:
    """True if `arg` names main/master exactly -- as a plain branch name,
    a `refs/heads/<name>` path, or the destination side of a `src:dest`
    refspec. WHY not substring: `"main" in first_line` false-positived on
    branch names merely CONTAINING main/master, e.g. "domain-fix"."""
    dest = arg.split(":")[-1].removeprefix("refs/heads/")
    return dest in ("main", "master")


def _command_pushes_public_main(command: str) -> bool:
    """True if any statement in `command` is a `git push public <main|master>`
    -- token-wise, so it isn't fooled by a leading `cd X &&`, a chained
    command, or a push buried on a later line of a multi-line command."""
    for statement in _split_statements(command):
        parsed = _git_subcommand_and_args(_statement_tokens(statement))
        if not parsed or parsed[0] != "push":
            continue
        args = parsed[1]
        if "public" in args and any(_matches_protected_ref(a) for a in args):
            return True
    return False


def main() -> None:
    # WHY strict=True + explicit deny (issue #195 follow-up, external audit
    # 2026-07-15): parse_stdin()'s default {} on malformed JSON was
    # indistinguishable from "nothing to check" -- `if not data: return`
    # silently allowed the commit through every check in this file (branch
    # protection, secret scanning, ruff lint), which is not evidence the
    # commit is safe. Same composition-bug class already fixed in
    # input_guard.py and pre_vault_write.py.
    try:
        data = parse_stdin(strict=True)
    except HookInputError:
        emit_permission_decision(
            decision="deny",
            reason="[pre-commit-guard] Malformed tool_input JSON — cannot check for secrets, "
            "branch protection, or lint errors, failing closed.",
        )
        return
    if not data:
        return

    tool_input = get_tool_input(data)
    command = tool_input.get("command", "")

    # --- Check 0: Block direct push to public repo ---
    # WHY: Public repo (Claude-cod-top-2026) is read-only distribution.
    # Changes go to origin (private) first, then PR to public.
    # Allow pushing feature branches to public (needed for PRs), block only main/master.
    if _command_pushes_public_main(command):
        # WHY: permissionDecision "deny" replaces sys.exit(2) — proper SDK protocol.
        # Yields structured JSON that Claude Code can surface cleanly to the user
        # rather than a raw process exit which may not propagate context.
        emit_permission_decision(
            decision="deny",
            reason=(
                "Direct push to 'public' remote main/master is not allowed. "
                "Push to 'origin' first, then create a PR to the public repo."
            ),
        )
        sys.exit(0)  # WHY: exit 0 after emitting decision — JSON already handled the block

    # WHY: fast exit if not git commit — hook fires on EVERY Bash call,
    # can't slow down all commands
    if not _command_has_git_commit(command):
        return

    # Skip amend checks for now — focus on new commits
    warnings: list[str] = []
    unusable = _commit_chain_problem(command) or _unusable_dash_c_target(command)
    if unusable:
        emit_permission_decision(
            decision="deny",
            reason=(
                f"Cannot tell which repository this commit targets: {unusable}. "
                "Run one commit per command, with an absolute path in `git -C` "
                "or `cd <repo> && git commit`."
            ),
        )
        sys.exit(0)  # WHY: permissionDecision already handles the block
    cmd_cwd = _resolve_commit_cwd(command)

    # --- Check 1: Branch protection ---
    # WHY: commit to main without PR = code review bypass = potential production break
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cmd_cwd)
    if branch in ("main", "master"):
        emit_permission_decision(
            decision="deny",
            reason=(
                f"Direct commit to '{branch}' branch is not allowed. "
                "Create a feature branch first: git checkout -b feature/<name>"
            ),
        )
        sys.exit(0)  # WHY: permissionDecision already handles the block

    # --- Check 2: Sensitive files in staging ---
    # WHY: .env, credentials.json etc. — PII/secrets, should not go to git
    # WHY cwd=cmd_cwd here too (cross-model audit finding): only the branch
    # check passed the parsed target-repo cwd through -- staged-file, diff,
    # and ruff checks below still ran against the HOOK's own cwd, so a
    # `cd <other-repo> && git commit` correctly checked the right branch but
    # silently checked the WRONG repo for secrets/debug statements/lint.
    staged_files = run_git(["diff", "--cached", "--name-only"], cwd=cmd_cwd)
    # WHY fetched here, not just before Check 3 (F-09, external audit
    # 2026-07-15): Check 2 previously scanned ONLY staged file NAMES for
    # secrets -- a real API key/token pasted into an innocuously named file
    # (config.py, notes.md) was invisible regardless of filename. This same
    # diff is reused by Check 3 below, so fetching it once here costs nothing
    # extra.
    diff_content = run_git(["diff", "--cached"], cwd=cmd_cwd)
    if staged_files:
        high_flagged: list[str] = []
        medium_flagged: list[str] = []
        for f in staged_files.split("\n"):
            if not f.strip():
                continue
            f_lower = f.lower()
            if _is_safe_secret_lookalike(f_lower):
                continue
            if _is_high_confidence_secret(f_lower):
                high_flagged.append(f)
            elif any(p in f_lower for p in _MEDIUM_CONFIDENCE_SECRET_PATTERNS):
                medium_flagged.append(f)

        content_secret_hits = _staged_content_secret_hits(diff_content) if diff_content else []

        if high_flagged or content_secret_hits:
            allow_override = os.environ.get("ALLOW_SECRET_COMMIT") == "1"
            override_reason = os.environ.get("ALLOW_SECRET_COMMIT_REASON", "").strip()
            flagged_desc = list(high_flagged)
            if content_secret_hits:
                flagged_desc.append(
                    f"staged content matching {len(content_secret_hits)} secret-token shape(s)"
                )
            if allow_override and override_reason:
                # WHY logged, not silent: an override that bypasses a
                # secret-commit block must leave an audit trail.
                print(
                    f"[pre-commit-guard] OVERRIDE: committing high-confidence secret-like "
                    f"content ({', '.join(flagged_desc)}) -- reason: {override_reason}",
                    file=sys.stderr,
                )
                warnings.append(
                    f"[pre-commit-guard] WARNING: secret-like content committed via explicit "
                    f"override: {', '.join(flagged_desc)} (reason: {override_reason})"
                )
            else:
                emit_permission_decision(
                    decision="deny",
                    reason=(
                        "[pre-commit-guard] Blocked: high-confidence secret-like content "
                        f"staged: {', '.join(flagged_desc)}.\n"
                        "If this is a false positive (e.g. a test fixture with fake "
                        "credentials), set BOTH ALLOW_SECRET_COMMIT=1 and "
                        'ALLOW_SECRET_COMMIT_REASON="<why this is safe>" and retry.'
                    ),
                )
                sys.exit(0)  # WHY: permissionDecision already handles the block

        if medium_flagged:
            warnings.append(
                f"[pre-commit-guard] WARNING: Potentially sensitive files staged: "
                f"{', '.join(medium_flagged)}. Review before committing!"
            )

    # --- Check 3: Debug statements in diff (advisory only, does NOT block) ---
    # WHY: print() and console.log in production code — log noise and potential data leaks.
    # WHY advisory, not a hard block (security audit 2026-07-12, F-19): this repo's own
    # hooks/scripts legitimately use print() ~400 times for stderr diagnostics -- hard-blocking
    # on any print( addition would make routine hook development unworkable without constant
    # overrides. Unlike Checks 1/2/4 in this file (which DO emit_permission_decision(deny)),
    # this check only ever appends to `warnings` -> additionalContext, never denies the commit.
    if diff_content:
        debug_patterns = ["print(", "console.log(", "debugger", "breakpoint()", "import pdb"]
        found_debug = []
        for line in diff_content.split("\n"):
            # WHY: only added lines (starting with +), not removed ones
            if not line.startswith("+") or line.startswith("+++"):
                continue
            for pattern in debug_patterns:
                if pattern in line:
                    found_debug.append(pattern)
                    break
        if found_debug:
            unique_patterns = list(set(found_debug))
            warnings.append(
                f"[pre-commit-guard] INFO (non-blocking): debug statements found in staged "
                f"changes: {', '.join(unique_patterns)}. Consider removing before commit."
            )

    # --- Check 4: ruff lint on staged Python files → BLOCK if errors ---
    # WHY: enforcement, not reminder. Every time we skipped this, post-hoc review found
    # real bugs (F541 f-strings, F821 undefined names, I001 import order).
    # ruff is <1s, zero false positives on our codebase. Block before damage is done.
    # WHY: --diff-filter=ACM excludes Deleted files — ruff errors on missing paths (E902)
    staged_py_str = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACM"], cwd=cmd_cwd)
    staged_py = [f for f in staged_py_str.split("\n") if f.endswith(".py") and f.strip()]
    if staged_py:
        # WHY: `git diff --name-only` always returns paths relative to the repo ROOT,
        # not the hook process's cwd. When the project cwd is a subdirectory of the
        # repo (e.g. a monorepo with the .git at a parent level), running ruff with
        # the inherited cwd double-prefixes the path (cwd/repo-relative-path) and
        # every staged file 404s with E902. Anchor ruff's cwd to the repo root so
        # the paths git reported resolve correctly regardless of caller cwd.
        # cwd=cmd_cwd: same cross-repo fix as Check 2/3 above — must resolve
        # the TARGET repo's root, not the hook process's own repo's root.
        repo_root = run_git(["rev-parse", "--show-toplevel"], cwd=cmd_cwd)
        try:
            ruff_result = subprocess.run(
                [sys.executable, "-m", "ruff", "check", "--output-format=concise", *staged_py],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=repo_root or None,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            # WHY warn, not fully silent (cross-model audit finding): still
            # fail-open (never block a commit just because the lint tool
            # itself is broken/hanging) -- but the original bypass here left
            # ZERO visible signal that the "enforcement, not reminder" gate
            # above didn't actually run. Surface it instead of vanishing.
            emit_hook_result(
                "PreToolUse",
                f"[pre-commit-guard] WARNING: ruff could not run ({exc.__class__.__name__}) "
                "-- lint enforcement was SKIPPED for this commit, not confirmed clean.",
            )
            sys.exit(0)
        if ruff_result.returncode != 0:
            ruff_output = (ruff_result.stdout or ruff_result.stderr).strip()
            emit_permission_decision(
                decision="deny",
                reason=(
                    f"[pre-commit-guard] ruff found lint errors in staged files.\n"
                    f"Fix with: python -m ruff check --fix <file>\n\n"
                    f"{ruff_output}"
                ),
            )
            sys.exit(0)  # WHY: permissionDecision already handles the block

    # --- Check 4b: reviewer reminder for logic bugs ruff cannot catch ---
    # WHY: ruff catches syntax/import/style. Logic bugs (wrong dict keys, off-by-one
    # in indices, spec contradictions) only a code reviewer catches.
    # Soft reminder — not a block, but non-ignorable in the output.
    staged_py_count = len(staged_py)
    if staged_py_count >= 3:
        warnings.append(
            f"[pre-commit-guard] {staged_py_count} Python files staged. "
            "Run reviewer agent before this commit — ruff does NOT catch logic bugs. "
            "Agent(reviewer, prompt='Review staged changes for logic errors')"
        )

    # --- Check 5: README test-count badge freshness reminder ---
    # WHY a plain reminder, not a local-vs-badge count comparison: see the
    # module docstring's Check 5 entry -- local pytest counts more tests
    # than CI (env-dependent tests), so comparing them fires on nearly
    # every relevant commit regardless of whether the badge is actually
    # stale. Only CI can answer that; this just points at the command that
    # reads CI's authoritative count, on the same trigger condition, without
    # running pytest locally at all.
    staged_file_list = [f for f in staged_files.split("\n") if f.strip()] if staged_files else []
    if _staged_files_touch_doc_count_inputs(staged_file_list):
        warnings.append(
            "[pre-commit-guard] tests/ or skills/ staged -- this may change the "
            "README Tests badge count. The badge is CI-authoritative, never a "
            "local pytest count (local counts MORE than CI due to "
            "environment-dependent tests -- see scripts/sync_readme_from_ci.py). "
            "After this reaches CI, run `python scripts/sync_readme_from_ci.py` "
            "to re-sync if the badge has drifted."
        )

    # Output warnings as additional context for Claude
    if warnings:
        emit_hook_result("PreToolUse", "\n".join(warnings))


if __name__ == "__main__":
    from lib.runtime import hook_main

    # WHY hook_main + fail_closed=True (issue #195 follow-up, external audit
    # 2026-07-15): this hook previously ran main() bare -- no timeout
    # protection, and any unhandled exception would crash silently (exit
    # via Python's default traceback-to-stderr-then-exit-1 path, which the
    # PreToolUse protocol treats as non-blocking). This hook can genuinely
    # deny (secrets, branch protection, ruff errors), so a crash/timeout
    # must fail closed, not silently let the commit through.
    hook_main(main, fail_closed=True)
