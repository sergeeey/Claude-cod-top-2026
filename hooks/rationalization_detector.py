#!/usr/bin/env python3
"""UserPromptSubmit hook: detect rationalization excuses before Claude responds.

WHY: 12 из 14 rationalization patterns (integrity.md:59-74) не покрыты хуками.
Claude может сказать "I'm 90% sure, no need to re-check" и пропустить verification.

This hook fires BEFORE Claude generates response — early intervention prevents
rationalization from reaching code/commit stage.

Based on: integrity.md Rationalization Prevention table
"""

import os
import re
import sys

from utils import emit_hook_result, log_hook_trigger, parse_stdin

HOOK_NAME = "rationalization_detector"

# WHY: Rationalization patterns from integrity.md:59-74
# These are excuses Claude uses to skip verification, testing, or review.
# Format: (pattern, what_to_do, why_wrong)
RATIONALIZATION_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (
        re.compile(r"I\s+(?:already\s+)?know\s+this\s+(?:API|interface|pattern)", re.IGNORECASE),
        "Read the file. Always.",
        "[MEMORY] does not replace [VERIFIED]. The API may have changed.",
    ),
    (
        re.compile(
            r"tests?\s+(?:for\s+)?this\s+(?:change|feature)?\s+(?:are\s+)?excessive", re.IGNORECASE
        ),
        "At least 1 test (happy path).",
        "Simple changes break production most often.",
    ),
    (
        re.compile(r"I\s+checked\s+this\s+in\s+a\s+previous\s+message", re.IGNORECASE),
        "Re-verify with a tool.",
        "Context may have changed after compaction.",
    ),
    (
        re.compile(r"user\s+(?:is\s+)?in\s+a\s+hurry", re.IGNORECASE),
        "Run the reviewer agent.",
        "Skipping review = tech debt. Reviewer runs in 30 sec.",
    ),
    (
        re.compile(r"no\s+plan\s+needed\s+for\s+(?:2|two)\s+files", re.IGNORECASE),
        "Count files. Follow the threshold.",
        "Threshold is 3 files. Optional for 2, required for 3+.",
    ),
    (
        re.compile(r"I'll\s+write\s+tests\s+after\s+(?:the\s+)?implementation", re.IGNORECASE),
        "Load tdd-workflow. RED first.",
        "Tests written after code test the implementation, not the requirements.",
    ),
    (
        re.compile(r"security\s+check\s+(?:is\s+)?not\s+needed.*internal\s+API", re.IGNORECASE),
        "Load security-audit skill.",
        "Internal APIs are also vulnerable (lateral movement).",
    ),
    (
        re.compile(r"this\s+change\s+(?:is\s+)?too\s+simple\s+for\s+Evidence", re.IGNORECASE),
        "Mark it. [VERIFIED] takes 1 sec.",
        "Simple claims can also be wrong.",
    ),
    (
        re.compile(r"I'm\s+\d{2,3}%\s+sure.*no\s+need\s+to\s+(?:re-?)?check", re.IGNORECASE),
        "[UNKNOWN] is better than a false [INFERRED].",
        "10% errors = hundreds of bugs per year.",
    ),
    (
        re.compile(r"sub-?agents\s+already\s+verified\s+this", re.IGNORECASE),
        "Re-verify agent claims with grep/bash. Always.",
        "Agents read docs/READMEs, not code. Their [VERIFIED] is actually [DOCS].",
    ),
]

# WHY: Additional context-aware patterns that need full prompt analysis
CONTEXT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"MCP\s+will\s+answer\s+faster", re.IGNORECASE),
        "Require local search first — 0 tokens, 0 latency.",
    ),
    (
        re.compile(r"(?:just|simply)\s+(?:do|run|execute)", re.IGNORECASE),
        "Speed mode detected — but still need verification.",
    ),
]


def check_for_rationalizations(prompt: str) -> list[tuple[str, str, str]]:
    """Scan user prompt for rationalization patterns.

    Returns:
        List of (pattern_desc, what_to_do, why_wrong) for detected excuses.
    """
    if not prompt or len(prompt) < 20:
        return []

    detected = []
    for pattern, what_to_do, why_wrong in RATIONALIZATION_PATTERNS:
        if pattern.search(prompt):
            detected.append((pattern.pattern[:60], what_to_do, why_wrong))

    return detected


def main() -> None:
    # WHY: recursion guard — don't trigger inside subagent calls
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    data = parse_stdin()
    if not data:
        sys.exit(0)

    # WHY: UserPromptSubmit event has 'prompt' field
    user_prompt = data.get("prompt", "")
    if not user_prompt:
        sys.exit(0)

    detected = check_for_rationalizations(user_prompt)
    if not detected:
        sys.exit(0)

    # WHY: Log first detected rationalization to telemetry
    session_id = data.get("session_id", "")
    first_pattern = detected[0][0] if detected else "unknown"
    log_hook_trigger(
        hook_name=HOOK_NAME,
        trigger_type="rationalization",
        action="warning",
        sample=first_pattern,
        session_id=session_id,
    )

    # Build warning message
    warnings = []
    for pattern_desc, what_to_do, why_wrong in detected[:3]:  # Show max 3
        warnings.append(
            f"  • Pattern: {pattern_desc}\n"
            f"    What to do: {what_to_do}\n"
            f"    Why wrong: {why_wrong}"
        )

    warning_text = (
        f"[rationalization-detector] ⚠️ {len(detected)} rationalization pattern(s) detected.\n"
        f"Per integrity.md: these are excuses to skip verification.\n\n"
        + "\n\n".join(warnings)
        + f"\n\nTotal detected: {len(detected)} of 12 monitored patterns."
    )

    emit_hook_result("UserPromptSubmit", warning_text)


if __name__ == "__main__":
    main()
