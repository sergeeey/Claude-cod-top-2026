#!/usr/bin/env python3
"""PostToolUse hook: detect Validation Theater patterns.

WHY: Agents create validator scripts AND run them in the same session,
then mark results [VERIFIED]. When test data is synthetic (embedded answers,
create_synthetic_dataset, mock_data), F1=1.000 is a tautology, not evidence.

Real incident: ArgosArb ТОП-10 validation — all 10 niches marked SUCCESS
on synthetic data. User had to ask twice before real validation happened.
Cost of near-miss: $1.4M in wasted effort avoided only by user intervention.

Triggers on: Write (creating validator/test files) and Bash (running them).
Does NOT block — emits a context warning that reminds Claude to use
[VERIFIED-REAL] vs [VERIFIED-SYNTHETIC] and invoke skeptic for perfect scores.
"""

import re
import sys
import os

from utils import emit_hook_result, parse_stdin

# WHY: these strings in a newly created file signal synthetic data theater.
SYNTHETIC_DATA_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"create_synthetic_dataset", re.IGNORECASE),
    re.compile(r"mock_data\s*=", re.IGNORECASE),
    re.compile(r"generate_fake_", re.IGNORECASE),
    re.compile(r"synthetic_cases\s*=", re.IGNORECASE),
    re.compile(r"SYNTHETIC_", re.IGNORECASE),
    re.compile(
        r'label\s*=\s*["\']?(FRAUD|SMOKING_GUN|ANOMALY|NOVEL)["\']?\s*#.*embedded', re.IGNORECASE
    ),
)

# WHY: perfect scores on noisy real-world tasks are statistically suspicious.
# These patterns in a Bash output signal potential theater.
PERFECT_SCORE_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"F1\s*=\s*1\.000", re.IGNORECASE),
    re.compile(r"precision\s*=\s*1\.000", re.IGNORECASE),
    re.compile(r"recall\s*=\s*1\.000", re.IGNORECASE),
    re.compile(r"accuracy\s*=\s*100%", re.IGNORECASE),
    re.compile(
        r"all\s+\d+\s+(?:tests?|cases?|niches?)\s+(?:passed|validated|success)", re.IGNORECASE
    ),
    re.compile(r"\d+/\d+\s+(?:VALIDATED|SUCCESS|PASSED).*100%", re.IGNORECASE),
)

# WHY: these tool names signal we're looking at test/validation activity.
VALIDATION_TOOL_NAMES = {"Write", "Bash"}


def check_write_for_synthetic(tool_input: dict) -> str | None:
    """Check if a newly written file contains synthetic data patterns."""
    file_path = tool_input.get("file_path", "")
    content = tool_input.get("content", "")

    # Only flag files that look like validators/tests
    is_validator = any(
        kw in file_path.lower() for kw in ("validator", "test_", "_test", "validate", "classifier")
    )
    if not is_validator:
        return None

    matches = [p.pattern for p in SYNTHETIC_DATA_PATTERNS if p.search(content)]
    if not matches:
        return None

    return (
        f"[validation-theater-guard] ⚠️ Synthetic data detected in validator: {file_path}\n"
        f"Patterns found: {', '.join(matches)}\n"
        "Per audit-verification-gate.md: synthetic tests = [VERIFIED-SYNTHETIC], "
        "NOT [VERIFIED-REAL]. Hypothesis validation requires [VERIFIED-REAL] with ≥3 real sources.\n"
        "Action: use real-world data (URLs, datasets, files) before claiming validation."
    )


def check_bash_for_perfect_scores(tool_response: str) -> str | None:
    """Check Bash output for suspiciously perfect validation scores."""
    matches = [p.pattern for p in PERFECT_SCORE_PATTERNS if p.search(tool_response)]
    if not matches:
        return None

    return (
        "[validation-theater-guard] 🔴 Perfect score detected in output.\n"
        f"Triggered by: {', '.join(matches[:2])}\n"
        "Per audit-verification-gate.md: F1=1.000 / 100% on noisy real-world tasks is statistically suspicious.\n"
        "Required checks before accepting:\n"
        "  1. Were test cases from real-world data (not synthetic)?\n"
        "  2. Can this score be reproduced with a DIFFERENT dataset?\n"
        "  3. Zero-Based: 'Would I bet $1000 this holds on new data?'\n"
        "If ANY answer is NO → use [VERIFIED-SYNTHETIC], invoke /skeptic before declaring success."
    )


def main() -> None:
    # WHY: recursion guard — don't trigger inside subagent calls.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    data = parse_stdin()
    if not data:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name not in VALIDATION_TOOL_NAMES:
        sys.exit(0)

    warning = None

    if tool_name == "Write":
        tool_input = data.get("tool_input", {})
        warning = check_write_for_synthetic(tool_input)

    elif tool_name == "Bash":
        # Check both the command output and the response
        tool_response = data.get("tool_response", {})
        output = ""
        if isinstance(tool_response, dict):
            output = tool_response.get("output", "") or tool_response.get("stderr", "")
        elif isinstance(tool_response, str):
            output = tool_response

        if len(output) > 50:  # Skip empty/tiny responses
            warning = check_bash_for_perfect_scores(output)

    if warning:
        emit_hook_result("PostToolUse", warning)


if __name__ == "__main__":
    main()
