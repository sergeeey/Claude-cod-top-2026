#!/usr/bin/env python3
"""PreToolUse hook for Bash: guard git commit operations.

WHY: Direct commit to main/master is a common mistake that breaks workflow.
Staged .env or debug statements are a security/quality risk. The hook catches this
BEFORE command execution, not after.

Checks:
1. git commit in main/master → BLOCK
2. Staged .env / credentials → WARNING
3. Debug statements in diff → WARNING
4. ruff check on staged .py files → BLOCK if lint errors found
   WHY: enforcement, not reminder — bugs are always found in post-hoc review,
   so gate them before the commit lands. ruff is fast (<1s), zero false positives.
"""

import re
import shlex
import sys

from utils import emit_hook_result, emit_permission_decision, get_tool_input, parse_stdin, run_git

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
    data = parse_stdin()
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
    if staged_files:
        sensitive_patterns = [".env", "credentials", "secret", ".pem", ".key", "id_rsa"]
        flagged = []
        for f in staged_files.split("\n"):
            f_lower = f.lower()
            for pattern in sensitive_patterns:
                if pattern in f_lower:
                    flagged.append(f)
                    break
        if flagged:
            warnings.append(
                f"[pre-commit-guard] WARNING: Potentially sensitive files staged: "
                f"{', '.join(flagged)}. Review before committing!"
            )

    # --- Check 3: Debug statements in diff ---
    # WHY: print() and console.log in production code — log noise and potential data leaks
    diff_content = run_git(["diff", "--cached"], cwd=cmd_cwd)
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
                f"[pre-commit-guard] WARNING: Debug statements found in staged changes: "
                f"{', '.join(unique_patterns)}. Consider removing before commit."
            )

    # --- Check 4: ruff lint on staged Python files → BLOCK if errors ---
    # WHY: enforcement, not reminder. Every time we skipped this, post-hoc review found
    # real bugs (F541 f-strings, F821 undefined names, I001 import order).
    # ruff is <1s, zero false positives on our codebase. Block before damage is done.
    # WHY: --diff-filter=ACM excludes Deleted files — ruff errors on missing paths (E902)
    staged_py_str = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACM"], cwd=cmd_cwd)
    staged_py = [f for f in staged_py_str.split("\n") if f.endswith(".py") and f.strip()]
    if staged_py:
        import subprocess  # noqa: PLC0415 — WHY: stdlib, imported late to avoid overhead on non-commit paths

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

    # Output warnings as additional context for Claude
    if warnings:
        emit_hook_result("PreToolUse", "\n".join(warnings))


if __name__ == "__main__":
    main()
