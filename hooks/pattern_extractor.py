#!/usr/bin/env python3
"""PostToolUse hook for Bash: reminds to extract a pattern after a fix: commit.

WHY: fix commits are the most valuable source of learning patterns. Bug found,
fixed, and 10 minutes later the knowledge is lost. This hook forcefully stops
Claude after a fix commit and requires documenting Symptom->Cause->Fix->Lesson
in patterns.md. The [AVOID] pattern with counter allows tracking recurrences
of the same mistakes.

Difference from post_commit_memory: post_commit_memory maintains an operational commit log
in activeContext.md (what was done). pattern_extractor does NOT write patterns.md. It emits a
reminder (on stdout, so it must not run behind async_wrapper.py) asking Claude to write the
structured pattern (why it broke and how to prevent recurrence). The write is Claude's action.

Pearl Card fields (Prediction + Falsification) added 2026-06-13:
Each pattern now requires a testable prediction and a falsification condition,
turning passive notes into actionable Pearl Registry entries.
"""

import os
import re
import sys
from datetime import date
from pathlib import Path

from lib.runtime import (
    emit_hook_result,
    extract_tool_response,
    get_tool_input,
    is_failed_commit,
    parse_stdin,
)
from lib.security import sanitize_text

# WHY: commit messages can contain prompt injection attempts.
# Limit length and strip newlines before passing to additionalContext.
MAX_COMMIT_MSG_LEN = 200


# WHY: global patterns.md in ~/.claude/memory/ — not project-specific.
# Bugs recur ACROSS projects, so patterns are stored globally.
#
# WHY canonical, not _auto/ (fixed 2026-07-29): this used to point at
# _auto/patterns.md, the legacy write location. rules/memory-protocol.md
# documents ~/.claude/memory/patterns.md (no _auto/) as canonical, and
# decisions.md was already migrated there on 2026-07-06 -- patterns.md,
# playbook.md and learning_log.md still pointed at the stale legacy path.
# knowledge_librarian._resolve_memory_file() and pattern_escalation_review's
# own _resolve_patterns_path() both already check canonical first and fall
# back to _auto/ -- this constant did neither, it read ONLY _auto/, so once
# content moves to canonical this reminder hook would have silently gone
# blind to the real, current pattern history.
GLOBAL_PATTERNS_PATH = Path.home() / ".claude" / "memory" / "patterns.md"

# WHY: the "Debugging and Fixes" section is — the target place for bugfix patterns.
# Its header is stable (visible in patterns.md), so we use it as an anchor.
TARGET_SECTION = "## Debugging and Fixes"

# Unicode multiplication sign used in pattern counters: [\xd7N]
_COUNTER_RE = re.compile(r"\[\xd7(\d+)\]")


def extract_fix_subject(commit_msg: str) -> str | None:
    """Extracts a short description from a fix: commit.

    Supports formats:
    - "fix: something broken"
    - "fix(scope): something broken"
    Returns None if the commit is not fix:.
    """
    # WHY: re.match with IGNORECASE — commits vary in case (Fix:, FIX:, fix:)
    m = re.match(r"^fix(?:\([^)]+\))?:\s*(.+)", commit_msg, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def load_patterns_text() -> str:
    """Reads patterns.md content. Returns empty string if file not found.

    WHY: try/except instead of exists()+read — avoids TOCTOU race condition.
    """
    try:
        return GLOBAL_PATTERNS_PATH.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""


def find_matching_patterns(subject: str, patterns_text: str) -> list[tuple[str, int]]:
    """Searches for existing patterns in the section 'Debugging and Fixes', whose headers
    contain keywords from the commit subject.

    Returns a list of (pattern_header, current_counter).
    WHY: simple keyword overlap without NLP — sufficient for 80% of cases.
    Complex semantic matching is overkill at the hook level.
    """
    if not patterns_text:
        return []

    # WHY the whole file (found 2026-11-26): the section was looked up by the English name
    # "## Debugging and Fixes", but patterns.md's section is "## Отладка и фиксы". The lookup
    # never matched, so no reminder could show a known pattern. Headers are matched on their
    # words, so scanning all `### ` headers keeps the overlap rule that limits false matches.
    section_text = patterns_text

    # Normalize subject: strip punctuation, convert to lower
    # WHY: short technical terms (SQL, IN, API, PII) are also important,
    # and mixed languages require flexibility — threshold 3 chars + 1 match
    subject_words = set(re.findall(r"\b\w{3,}\b", subject.lower()))

    matches: list[tuple[str, int]] = []

    # Search for pattern headers ### [DATE] Name
    for header_match in re.finditer(r"^### (.+)$", section_text, re.MULTILINE):
        header = header_match.group(1)
        header_words = set(re.findall(r"\b\w{3,}\b", header.lower()))

        # Word intersection — 2+ matches for long words, 1 for short technical ones
        overlap = subject_words & header_words
        # WHY: technical terms (SQL, API) are short but precise.
        # 2+ matches for regular words, but if overlap contains
        # a word from subject with length >= 5 — 1 match is enough
        has_strong = any(len(w) >= 5 for w in overlap)
        if len(overlap) >= 2 or (len(overlap) == 1 and has_strong):
            # Extract current counter from header or block lines
            counter = _extract_counter(header_match.group(0), section_text, header_match.start())
            matches.append((header, counter))

    return matches


def _extract_counter(header_line: str, section_text: str, header_pos: int) -> int:
    """Extracts the numeric counter from a pattern header or its first lines.

    WHY: counter may be in header ### [2026-01-01] Name [\xd7N]
    or on a separate line below. We check both places.
    """
    # First search in the header line itself
    m = _COUNTER_RE.search(header_line)
    if m:
        return int(m.group(1))

    # Search in the pattern block (from header to next ###)
    tail = section_text[header_pos:]
    # WHY: skip 4 chars ("### ") to avoid matching current header's "###" prefix
    block_end = re.search(r"\n###", tail[4:])
    block = tail[: block_end.start() + 4] if block_end else tail
    m = _COUNTER_RE.search(block)
    if m:
        return int(m.group(1))

    return 1  # first occurrence, not yet tagged


def sanitize_commit_msg(msg: str) -> str:
    """Strip newlines and limit length to prevent prompt injection.

    WHY: commit messages are attacker-controlled input that flows into
    additionalContext (seen by LLM). Newlines could break JSON or inject prompts.
    """
    return sanitize_text(msg, MAX_COMMIT_MSG_LEN)


# Unicode multiplication sign for pattern counter notation: [\xd7N]
_MULT = "\xd7"


def build_reminder_message(
    commit_hash: str,
    commit_msg: str,
    subject: str,
    matching: list[tuple[str, int]],
) -> str:
    """Builds the reminder text for Claude in additionalContext.

    Template includes Pearl Card fields (Prediction + Falsification) so each
    pattern entry is testable and falsifiable, not just a passive note.
    """
    safe_msg = sanitize_commit_msg(commit_msg)
    today = date.today().isoformat()
    lines: list[str] = [
        f"[pattern-extractor] fix: commit detected: `{commit_hash}` — '{safe_msg}'",
        "",
        "Please extract the pattern and add it to ~/.claude/memory/patterns.md",
        f"under section '{TARGET_SECTION}'",
        "",
    ]

    if matching:
        lines.append("WARNING: similar existing patterns found:")
        for header, counter in matching:
            # Strip existing [\xd7N] from header to avoid duplicate when counter is in header text
            header_display = _COUNTER_RE.sub("", header).strip()
            lines.append(f"  • {header_display} [{_MULT}{counter}]")
            lines.append(f"    → Same bug? Increment: [{_MULT}{counter}] → [{_MULT}{counter + 1}]")
            lines.append("      instead of creating a new block.")
        lines.append("")
        lines.append("If this is a new bug — create a new entry using the template below.")
    else:
        lines.append("No similar patterns found — create a new block:")

    lines += [
        "",
        "Template:",
        f"### [{today}] [AVOID] {sanitize_commit_msg(subject)} [{_MULT}1]",
        "- Symptom: what was observed",
        "- Root cause: why it happened",
        "- Fix: what was changed",
        "- Lesson: how to prevent in the future",
        "- Prediction: if similar case occurs, I expect X to happen",
        "- Falsification: this pattern is WRONG if Y is observed",
        "",
        f'Tag [AVOID] = "do not repeat". [{_MULT}1] = first occurrence.',
        f"On recurrence change [{_MULT}1] → [{_MULT}2] and add a line '- Recurrence [date]: ...'",
    ]

    return "\n".join(lines)


def main() -> None:
    # WHY: prevent recursion when this hook fires inside a subagent's
    # SessionStart/etc — see hooks/CLAUDE.md "Recursion guard" section.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    data = parse_stdin()
    if not data:
        return

    tool_input = get_tool_input(data)
    command = tool_input.get("command", "")

    if "git commit" not in command:
        return

    response_text = extract_tool_response(data)
    if is_failed_commit(response_text):
        return

    # WHY the commit is read from git's own output, not from HEAD (found 2026-11-26): HEAD is the
    # last commit in the repo, not necessarily the one this command made. A `feat:` commit made
    # while HEAD is a `fix:` commit would otherwise repeat that old fix reminder.
    commit_hash, commit_msg = _commit_from_output(response_text)
    if not commit_hash or not commit_msg:
        return

    # Only activate on fix: commits
    subject = extract_fix_subject(commit_msg)
    if subject is None:
        return

    # Search for matches with existing patterns
    patterns_text = load_patterns_text()
    matching = find_matching_patterns(subject, patterns_text)

    reminder = build_reminder_message(commit_hash, commit_msg, subject, matching)

    emit_hook_result("PostToolUse", reminder)


_COMMIT_LINE_RE = re.compile(r"^\[[^\]]*?\s([0-9a-f]{7,40})\]\s+(.+)$")


def _commit_from_output(response_text: str) -> tuple[str, str]:
    """Hash and subject of the commit that `git commit` reports on its first output line.

    git prints `[branch abc1234] subject`. Returns ("", "") when that line is absent (for example
    `--dry-run`, or a commit that did not run), so no reminder is made from a different commit.
    """
    for line in response_text.splitlines():
        match = _COMMIT_LINE_RE.match(line.strip())
        if match:
            return match.group(1), match.group(2).strip()
    return "", ""


if __name__ == "__main__":
    main()
