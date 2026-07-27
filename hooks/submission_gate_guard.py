#!/usr/bin/env python3
"""UserPromptSubmit + PostToolUse(Write|Edit) hook: mechanically enforce
rules/integrity.md's Submission Gate instead of relying on prose recall.

WHY: integrity.md already documents a Submission Gate (skeptic run,
Pre-Submission Checklist, Text<->Figures consistency, 24h cooling-off) with an
explicit trigger-word and file-pattern list. It still failed in practice
(patterns.md 2026-07-11 [AVOID x4]): a preprint was sent for external review
without the gate firing, because the gate lived only as text a model has to
remember to apply -- not a mechanism. Two independent external reviewers
caught the gaps the gate would have caught, not our own process.

This hook does not invent new triggers -- it fires on the exact keyword list
and file-pattern list integrity.md already specifies, so there is one source
of truth (integrity.md) and one enforcement point (this file).

Design note (scope): a second, harder failure mode from the same incident
class -- a project-specific "gate skill" (dispatcher) whose safety text is
bypassed by an alternate routing path (routing-policy on HIGH confidence,
PR #178) -- is intentionally NOT covered here. That failure is structural to
a specific skill graph, not a generic prompt/file pattern; generalizing it
would require parsing skills/registry.yaml dependency edges, a different and
heavier mechanism. Folding it into this hook would violate the Structure-Bias
Guard (one mechanism per problem shape). See rules/research-methodology.md.

Fires on:
  - UserPromptSubmit: prompt has BOTH an action verb (send/publish/ready/...)
    AND a claim-noun (paper/manuscript/reviewer/...). Requiring both avoids
    firing on ordinary dev talk ("npm publish", "ready to commit").
  - PostToolUse(Write|Edit): file path matches a manuscript-shaped glob
    (manuscript*, *.docx, paper*, cover_letter*, submission*). A filename
    match alone is a strong enough signal -- no co-occurrence needed.

Soft nudge only (additionalContext) -- mirrors reject_gate_guard.py /
null_results_pre_check.py: never blocks, just makes the existing rule
impossible to silently skip.
"""

import os
import re
import sys
from pathlib import Path

from utils import emit_hook_result, parse_stdin

# WHY co-occurrence, not a single keyword list: null_results_pre_check.py
# already showed a bare verb list fires on unrelated dev talk. "publish" alone
# matches "npm publish" (a release, not a scientific/external claim). Verb +
# claim-noun both present is what integrity.md actually means by "submission".
ACTION_VERBS = {
    "подаём",
    "подаем",
    "отправить",
    "отправляю",
    "опубликовать",
    "публикуем",
    "готово",
    "submit",
    "send",
    "publish",
    "ready",
    "complete",
}

CLAIM_NOUNS = {
    "статья",
    "статью",
    "препринт",
    "рецензент",
    "рецензенту",
    "доктору",
    "manuscript",
    "paper",
    "preprint",
    "findings",
    "editor",
    "reviewer",
    "cover letter",
    "cover_letter",
}

# WHY these exact globs: copied verbatim from rules/integrity.md's Submission
# Gate "File modifications" trigger list -- one source of truth, not a
# re-derived guess.
FILE_PATTERNS = ("manuscript*", "*.docx", "paper*", "cover_letter*", "submission*")

GATE_MESSAGE = (
    "[submission-gate] ⚠️ External-facing artifact detected "
    "-- rules/integrity.md Submission Gate applies.\n"
    "Mandatory BEFORE claiming ready/sending: "
    "(1) skeptic agent run (context-blind), "
    "(2) Pre-Submission Checklist (≥9 [VERIFIED] items), "
    "(3) Text↔Figures consistency check, "
    "(4) 24h cooling-off after 'READY'.\n"
    "'Core already verified' ≠ 'artifact ready for the world' -- "
    "verified subset ≠ claimed whole (CLAUDE.md Claim Scope Discipline)."
)


def _contains_word(low_text: str, words: set[str]) -> bool:
    """True if any word/phrase appears as a whole-word match, not a substring.

    WHY \\b, not `word in text`: plain substring containment false-positives
    on common words -- "ready" matches inside "already", "complete" matches
    inside "incomplete", "paper" matches inside "newspaper". A hook that
    fires on "I already fixed the bug, saw it in today's newspaper" trains
    the user to ignore it. \\b works on Cyrillic too (re's default is Unicode
    word chars), so this covers both the RU and EN term lists.
    """
    return any(re.search(rf"\b{re.escape(w)}\b", low_text) for w in words)


def _is_prompt_triggered(prompt: str) -> bool:
    """Return True only if BOTH an action verb and a claim-noun are present."""
    low = prompt.lower()
    return _contains_word(low, ACTION_VERBS) and _contains_word(low, CLAIM_NOUNS)


def _is_submission_shaped_path(file_path: str) -> bool:
    """Return True if the file basename matches a manuscript-shaped glob."""
    name = Path(file_path).name.lower()
    return any(Path(name).match(pat) for pat in FILE_PATTERNS)


def main() -> None:
    # WHY: recursion guard -- avoid loops inside Agent SDK sub-invocations.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    data = parse_stdin()
    if not data:
        sys.exit(0)

    if "tool_name" in data:
        # PostToolUse(Write|Edit) path.
        if data.get("tool_name") not in ("Write", "Edit"):
            sys.exit(0)
        tool_input = data.get("tool_input", {})
        file_path = tool_input.get("file_path", "")
        if not file_path or not _is_submission_shaped_path(file_path):
            sys.exit(0)
        emit_hook_result("PostToolUse", GATE_MESSAGE)
        return

    # UserPromptSubmit path.
    prompt: str = data.get("prompt", "")
    if not isinstance(prompt, str) or not prompt.strip():
        sys.exit(0)
    if not _is_prompt_triggered(prompt):
        sys.exit(0)
    emit_hook_result("UserPromptSubmit", GATE_MESSAGE)


if __name__ == "__main__":
    main()
