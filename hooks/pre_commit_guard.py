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
import shlex
import subprocess
import sys

from utils import (
    HookInputError,
    emit_hook_result,
    emit_permission_decision,
    get_tool_input,
    parse_stdin,
    run_git,
)

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
# session. Requires a trailing `&&`/`;` so a bare `cd X` (nothing chained after)
# doesn't false-match.
_CD_PREFIX_RE = re.compile(r'^\s*cd\s+(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*(?:&&|;)')


def extract_command_cwd(command: str) -> str | None:
    """Extract the target directory from a leading `cd <dir> &&`/`cd <dir>;`."""
    match = _CD_PREFIX_RE.match(command)
    if not match:
        return None
    return next((g for g in match.groups() if g is not None), None)


# WHY (cross-model audit, hooks-02): a bare `"git commit" not in command`
# substring check is bypassed by `git -C <repo> commit ...` or `git -c
# user.name=x commit ...` -- the literal substring "git commit" never
# appears even though `commit` IS the subcommand being run. Global options
# that take a separate value (space-delimited) must be skipped explicitly;
# `--opt=value` and bare flags (`-p`, `--no-pager`) are single tokens.
_GIT_GLOBAL_OPTS_WITH_VALUE = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
)
# WHY split on chain operators first, then shlex.split each statement: a
# `cd X && git push ...` or a push buried on line 2 of a multi-line command
# was invisible to a check that only inspected `command.split("\n")[0]`.
_CHAIN_SPLIT_RE = re.compile(r"\|\||&&|;|[&|]")
# WHY heredoc-aware (P2, cross-model review of this same fix): splitting on
# bare `\n` treats a heredoc BODY line as its own statement, so `cat <<EOF\n
# git commit -m test\nEOF` false-positived as a real commit -- the "git
# commit" text there is payload for `cat`, never executed. Mirrors the
# heredoc buffering already proven correct in commit_test_gate.py.
_HEREDOC_START_RE = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")


def _split_statements(command: str) -> list[str]:
    """Split a shell command into independent statements at &&, ||, ;, |, and
    newline. A heredoc BODY is discarded entirely, never scanned as a
    statement -- WHY not bundle marker+body+terminator into one statement
    (tried first, still wrong): shlex treats newlines as whitespace, so a
    bundled multi-line statement flattens into ONE token stream where
    _git_subcommand_and_args's "find git anywhere in tokens" search still
    matches a "git commit" token sequence sitting inside the heredoc BODY
    text, exactly as if it were the real invocation. Only the heredoc's own
    marker line (e.g. "cat <<EOF > file.txt") is ever added as a statement;
    the body between marker and terminator is pure opaque data."""
    statements: list[str] = []
    heredoc_terminator: str | None = None
    for line in command.split("\n"):
        if heredoc_terminator is not None:
            # WHY .strip(), not exact match: `<<-` allows the terminator
            # line to be indented with tabs.
            if line.strip() == heredoc_terminator:
                heredoc_terminator = None
            continue  # heredoc body/terminator lines are never scanned
        heredoc_match = _HEREDOC_START_RE.search(line)
        if heredoc_match:
            heredoc_terminator = heredoc_match.group(1)
        statements.extend(s for s in _CHAIN_SPLIT_RE.split(line) if s.strip())
    return statements


def _statement_tokens(statement: str) -> list[str]:
    try:
        return shlex.split(statement, posix=True)
    except ValueError:
        # WHY fall back to a naive split, not "no tokens": malformed quoting
        # in the inspected command must not silently disable a security gate.
        return statement.split()


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
    cmd_cwd = extract_command_cwd(command)

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
            ruff_result = subprocess.run(  # noqa: S603
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
    from utils import hook_main

    # WHY hook_main + fail_closed=True (issue #195 follow-up, external audit
    # 2026-07-15): this hook previously ran main() bare -- no timeout
    # protection, and any unhandled exception would crash silently (exit
    # via Python's default traceback-to-stderr-then-exit-1 path, which the
    # PreToolUse protocol treats as non-blocking). This hook can genuinely
    # deny (secrets, branch protection, ruff errors), so a crash/timeout
    # must fail closed, not silently let the commit through.
    hook_main(main, fail_closed=True)
