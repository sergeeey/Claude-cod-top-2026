#!/usr/bin/env python3
"""PostToolUse hook: enforce Evidence Policy markers in responses.

WHY: Evidence Policy is documented in CLAUDE.md and integrity.md but has
NO deterministic enforcement. Claude can ignore markers and nothing happens.
This hook nudges Claude when factual claims lack evidence markers,
making the policy shift from "educational" to "enforced".

Triggers on: Agent and Bash (post-commit) responses that contain factual claims.
Does NOT block — emits a reminder context to prompt self-correction.
"""

import re

from utils import emit_hook_result, extract_tool_response, parse_stdin

# WHY: these markers are the Evidence Policy vocabulary from integrity.md.
# If a response contains factual claims but NONE of these, it's unmarked.
EVIDENCE_MARKERS: tuple[str, ...] = (
    "[VERIFIED]",
    "[DOCS]",
    "[CODE]",
    "[INFERRED]",
    "[WEAK]",
    "[CONFLICTING]",
    "[UNKNOWN]",
    "[MEMORY]",
    "[VERIFIED-HIGH]",
    "[VERIFIED-MEDIUM]",
    "[VERIFIED-LOW]",
)

# WHY: heuristic for "this response contains factual claims that need marking".
# Numbers, versions, URLs, config values, commands — all need evidence markers.
FACTUAL_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"version\s+\d+\.\d+", re.IGNORECASE),
    re.compile(r"python\s+3\.\d+", re.IGNORECASE),
    re.compile(r"requires?\s+\w+\s+\d+", re.IGNORECASE),
    re.compile(r"default(?:s|\s+is)\s+\w+", re.IGNORECASE),
    re.compile(r"always|never|must|guaranteed", re.IGNORECASE),
    re.compile(r"best practice", re.IGNORECASE),
    re.compile(r"recommended\s+(?:to|approach|way)", re.IGNORECASE),
    re.compile(r"\d+%\s+(?:of|coverage|faster|slower)", re.IGNORECASE),
    re.compile(r"up to \d+", re.IGNORECASE),
    re.compile(r"(?:max|min|limit)\s+(?:is|of)\s+\d+", re.IGNORECASE),
)

# WHY: short responses or code-only responses don't need evidence markers.
MIN_RESPONSE_LENGTH = 200
MIN_FACTUAL_CLAIMS = 2


def has_evidence_markers(text: str) -> bool:
    """Check if text contains any Evidence Policy marker."""
    return any(marker in text for marker in EVIDENCE_MARKERS)


def count_factual_claims(text: str) -> int:
    """Count heuristic factual claims in text."""
    count = 0
    for pattern in FACTUAL_CLAIM_PATTERNS:
        count += len(pattern.findall(text))
    return count


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    response = extract_tool_response(data)
    if not response or len(response) < MIN_RESPONSE_LENGTH:
        return

    # WHY: only check responses that contain factual claims
    claim_count = count_factual_claims(response)
    if claim_count < MIN_FACTUAL_CLAIMS:
        return

    # WHY: if markers are already present, Evidence Policy is being followed
    if has_evidence_markers(response):
        return

    # WHY: soft nudge — don't block, but remind Claude to add markers.
    # This shifts Evidence Policy from "instruction" to "enforced nudge".
    emit_hook_result(
        "PostToolUse",
        f"[evidence-guard] Response contains ~{claim_count} factual claims "
        "but NO Evidence Policy markers ([VERIFIED], [INFERRED], [UNKNOWN], etc.). "
        "Per integrity.md: mark every factual claim with an evidence level. "
        "[UNKNOWN] is better than a false [INFERRED]. "
        "Consider adding markers before presenting to the user.",
    )


if __name__ == "__main__":
    main()
