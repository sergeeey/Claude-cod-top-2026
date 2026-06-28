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

import sys

from utils import emit_hook_result, emit_permission_decision, get_tool_input, parse_stdin, run_git


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    tool_input = get_tool_input(data)
    command = tool_input.get("command", "")

    # --- Check 0: Block direct push to public repo ---
    # WHY: Public repo (Claude-cod-top-2026) is read-only distribution.
    # Changes go to origin (private) first, then PR to public.
    # WHY: check only the actual command, not heredoc/string content inside it
    # Allow pushing feature branches to public (needed for PRs), block only main/master
    first_line = command.split("\n")[0].strip()
    if (
        first_line.startswith("git push")
        and "public" in first_line
        and ("main" in first_line or "master" in first_line)
    ):
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
    if "git commit" not in command:
        return

    # Skip amend checks for now — focus on new commits
    warnings: list[str] = []

    # --- Check 1: Branch protection ---
    # WHY: commit to main without PR = code review bypass = potential production break
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
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
    staged_files = run_git(["diff", "--cached", "--name-only"])
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
    diff_content = run_git(["diff", "--cached"])
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
    staged_py_str = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACM"])
    staged_py = [f for f in staged_py_str.split("\n") if f.endswith(".py") and f.strip()]
    if staged_py:
        import subprocess  # noqa: PLC0415 — WHY: stdlib, imported late to avoid overhead on non-commit paths

        try:
            ruff_result = subprocess.run(  # noqa: S603
                [sys.executable, "-m", "ruff", "check", "--output-format=concise", *staged_py],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # WHY: ruff not installed or hung — skip lint, never block commit silently
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
