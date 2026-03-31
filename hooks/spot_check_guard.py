#!/usr/bin/env python3
"""PostToolUse hook: enforce Spot-Check Rule for large analyses.

WHY: integrity.md states: "After any analysis with 10+ factual claims,
randomly pick 3 and verify them with a tool." This hook detects when
Claude has made many claims and reminds to spot-check before presenting.

Without this hook, the Spot-Check Rule is purely instructional and
easily forgotten during long analytical responses.
"""

import re

from utils import emit_hook_result, extract_tool_response, parse_stdin

# WHY: same patterns as evidence_guard.py — factual claim heuristics
CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"version\s+\d+\.\d+", re.IGNORECASE),
    re.compile(r"python\s+3\.\d+", re.IGNORECASE),
    re.compile(r"requires?\s+\w+\s+\d+", re.IGNORECASE),
    re.compile(r"default(?:s|\s+is)\s+\w+", re.IGNORECASE),
    re.compile(r"always|never|must|guaranteed", re.IGNORECASE),
    re.compile(r"best practice", re.IGNORECASE),
    re.compile(r"\d+%\s+(?:of|coverage|faster|slower)", re.IGNORECASE),
    re.compile(r"up to \d+", re.IGNORECASE),
    re.compile(r"(?:max|min|limit)\s+(?:is|of)\s+\d+", re.IGNORECASE),
    re.compile(r"(?:file|function|class|method)\s+\w+\s+(?:exists?|is\s+defined)", re.IGNORECASE),
    re.compile(r"line\s+\d+", re.IGNORECASE),
    re.compile(r"\b\d+\s+(?:tests?|files?|functions?|classes?|lines?)\b", re.IGNORECASE),
)

SPOT_CHECK_THRESHOLD = 10
MIN_RESPONSE_LENGTH = 500


def count_claims(text: str) -> int:
    """Count heuristic factual claims."""
    total = 0
    for pattern in CLAIM_PATTERNS:
        total += len(pattern.findall(text))
    return total


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    response = extract_tool_response(data)
    if not response or len(response) < MIN_RESPONSE_LENGTH:
        return

    claim_count = count_claims(response)
    if claim_count < SPOT_CHECK_THRESHOLD:
        return

    # WHY: Spot-Check Rule from integrity.md — pick 3 random claims and verify.
    # This is a REMINDER, not a blocker. Claude should self-correct.
    emit_hook_result(
        "PostToolUse",
        f"[spot-check] Analysis contains ~{claim_count} factual claims "
        f"(threshold: {SPOT_CHECK_THRESHOLD}). "
        "Per Spot-Check Rule (integrity.md): randomly pick 3 claims and verify "
        "them with a tool (Read, Grep, Bash). If any fail → re-verify ALL claims. "
        "This catches 'docs ≠ code' drift that sub-agents miss.",
    )


if __name__ == "__main__":
    main()
