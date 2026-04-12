#!/usr/bin/env python3
"""PostToolUse hook: auto-capture knowledge from git commits and test failures.

WHY: session_save.py only runs at session END. If a commit happens mid-session
or the session crashes, the knowledge is lost. This hook captures every
git commit and pytest failure immediately as a raw note — zero manual effort.

ACE paper role: passive Generator input — captures facts as they happen
so the Curator (session_save.py) has richer material to work with.
"""

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from utils import hook_main, parse_stdin

RAW_DIR = Path.home() / ".claude" / "memory" / "raw"


def _write_raw(slug: str, content: str) -> bool:
    """Write to raw/ if not already exists. Returns True if written."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w\-]", "_", slug)[:60]
    dest = RAW_DIR / f"{safe}.md"
    if dest.exists():
        return False  # idempotent
    dest.write_text(content, encoding="utf-8")
    return True


def _capture_git_commit(tool_input: dict, tool_output: dict) -> bool:
    """Capture git commit → raw note with subject + files changed."""
    # Only interested in successful commits
    if tool_output.get("exit_code", 1) != 0:
        return False

    command = tool_input.get("command", "")
    if "git commit" not in command:
        return False

    stdout = tool_output.get("stdout", "")

    # Extract commit hash and subject from output like:
    # [feat/branch abc1234] feat: something cool
    match = re.search(r"\[[\w/\-]+ ([a-f0-9]+)\] (.+)", stdout)
    if not match:
        return False

    sha = match.group(1)
    subject = match.group(2).strip()
    date = datetime.now(UTC).strftime("%Y-%m-%d")

    # Determine type
    commit_type = "feat"
    emoji = "✅"
    sentiment = "positive-example"
    if subject.startswith("fix"):
        commit_type = "fix"
        emoji = "🐛"
        sentiment = "negative-example fix"
    elif subject.startswith("refactor"):
        commit_type = "refactor"
        emoji = "♻️"
        sentiment = "refactor"
    elif subject.startswith("chore") or subject.startswith("docs"):
        return False  # not knowledge-worthy

    slug = f"auto-git-{commit_type}-{sha}"
    content = (
        f"# {emoji} {subject}\n\n"
        f"#raw #{commit_type} #git #auto-capture #{sentiment.replace(' ', ' #')}\n\n"
        f"**Date:** {date}  \n"
        f"**Commit:** `{sha}`  \n\n"
        f"---\n\n"
        f"{subject}\n"
    )

    written = _write_raw(slug, content)
    if written:
        print(f"[auto-capture] git {commit_type} → raw/{slug}.md", file=sys.stderr)
    return written


def _capture_test_failure(tool_input: dict, tool_output: dict) -> bool:
    """Capture pytest failures → raw note with error details."""
    command = tool_input.get("command", "")
    if "pytest" not in command and "python -m pytest" not in command:
        return False

    exit_code = tool_output.get("exit_code", 0)
    if exit_code == 0:
        return False  # tests passed, nothing to capture

    stdout = tool_output.get("stdout", "")
    stderr = tool_output.get("stderr", "")
    output = stdout + stderr

    # Extract FAILED lines
    failures = re.findall(r"FAILED (.+?) - (.+)", output)
    if not failures:
        # Try short format
        failures = [(m, "see output") for m in re.findall(r"FAILED (.+)", output)]

    if not failures:
        return False

    date = datetime.now(UTC).strftime("%Y-%m-%d")
    slug = f"auto-test-failure-{date}-{abs(hash(output[:100])) % 9999:04d}"

    failure_lines = "\n".join(f"- `{f[0]}`: {f[1][:100]}" for f in failures[:5])

    content = (
        f"# 🔴 Test Failure {date}\n\n"
        f"#raw #test-failure #negative-example #auto-capture\n\n"
        f"**Command:** `{command[:80]}`  \n"
        f"**Date:** {date}  \n\n"
        f"---\n\n"
        f"## Failed tests\n\n"
        f"{failure_lines}\n\n"
        f"## Output (truncated)\n\n"
        f"```\n{output[-800:]}\n```\n"
    )

    written = _write_raw(slug, content)
    if written:
        print(f"[auto-capture] test failure → raw/{slug}.md", file=sys.stderr)
    return written


def main() -> None:
    data = parse_stdin()
    if not data:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    tool_response = data.get("tool_response", {})

    # PostToolUse sends tool_response with stdout/stderr/exit_code
    tool_output = {
        "exit_code": tool_response.get("exit_code", tool_response.get("returncode", 0)),
        "stdout": tool_response.get("stdout", tool_response.get("output", "")),
        "stderr": tool_response.get("stderr", ""),
    }

    if tool_name == "Bash":
        _capture_git_commit(tool_input, tool_output)
        _capture_test_failure(tool_input, tool_output)


if __name__ == "__main__":
    hook_main(main)
