#!/usr/bin/env python3
"""PreToolUse hook for Bash: guard git commit operations.

ПОЧЕМУ: Прямой коммит в main/master — частая ошибка, которая ломает workflow.
Staged .env или debug statements — security/quality risk. Hook ловит это
ДО выполнения команды, а не после.

Проверки:
1. git commit в main/master → БЛОКИРОВКА (exit 2)
2. Staged .env / credentials → ПРЕДУПРЕЖДЕНИЕ
3. Debug statements в diff → ПРЕДУПРЕЖДЕНИЕ
"""

import json
import subprocess
import sys
from pathlib import Path


def run_git(args: list[str], timeout: int = 10) -> str:
    """Run git command and return stdout."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_input = data.get("tool_input", data)
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
        print(
            "[pre-commit-guard] BLOCKED: Direct push to 'public' remote is not allowed. "
            "Push to 'origin' first, then create a PR to the public repo.",
            file=sys.stderr,
        )
        sys.exit(2)

    # WHY: fast exit if not git commit — hook fires on EVERY Bash call,
    # can't slow down all commands
    if "git commit" not in command:
        return

    # Skip amend checks for now — focus on new commits
    warnings: list[str] = []

    # --- Check 1: Branch protection ---
    # ПОЧЕМУ: коммит в main без PR = обход code review = потенциальный production break
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if branch in ("main", "master"):
        # БЛОКИРОВКА — exit 2 отменяет выполнение команды
        print(
            f"[pre-commit-guard] BLOCKED: Direct commit to '{branch}' branch is not allowed. "
            "Create a feature branch first: git checkout -b feature/<name>",
            file=sys.stderr,
        )
        sys.exit(2)

    # --- Check 2: Sensitive files in staging ---
    # ПОЧЕМУ: .env, credentials.json и подобные — PII/secrets, не должны попадать в git
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
    # ПОЧЕМУ: print() и console.log в production коде — noise в логах и возможная утечка данных
    diff_content = run_git(["diff", "--cached"])
    if diff_content:
        debug_patterns = ["print(", "console.log(", "debugger", "breakpoint()", "import pdb"]
        found_debug = []
        for line in diff_content.split("\n"):
            # ПОЧЕМУ: только добавленные строки (начинаются с +), не удалённые
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

    # --- Check 4: 2-stage review reminder ---
    # ПОЧЕМУ: reviewer agent теперь делает 2-stage review (spec + quality).
    # Мягкое напоминание перед коммитом — не блокировка, только awareness.
    warnings.append(
        "[pre-commit-guard] REMINDER: Consider running 2-stage review before commit "
        "(Task reviewer). Pass 1: spec compliance, Pass 2: code quality."
    )

    # Output warnings as additional context for Claude
    if warnings:
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": "\n".join(warnings),
            }
        }
        print(json.dumps(result))


if __name__ == "__main__":
    main()
