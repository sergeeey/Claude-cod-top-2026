#!/usr/bin/env python3
"""PostToolUse hook: detect Validation Theater patterns.

WHY: Agents create validator scripts AND run them in the same session,
then mark results [VERIFIED]. When test data is synthetic (embedded answers,
create_synthetic_dataset, mock_data), F1=1.000 is a tautology, not evidence.

Real incident: ArgosArb ТОП-10 validation — all 10 niches marked SUCCESS
on synthetic data. User had to ask twice before real validation happened.
Cost of near-miss: $1.4M in wasted effort avoided only by user intervention.

Triggers on: Write (creating validator/test files) and Bash (running them).
Blocking mode: sys.exit(1) when perfect score + synthetic data simultaneously.
Otherwise: emits warning context.
"""

import os
import re
import sys

from utils import emit_hook_result, log_hook_trigger, parse_stdin

HOOK_NAME = "validation_theater_guard"

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
    # WHY: Inline synthetic patterns from skeptic-triggers.md:56-65
    # Embedded tuple lists with labels: abstracts = [("text", "LABEL"), ...]
    re.compile(r'\w+\s*=\s*\[\s*\(["\'][^"\']+["\'],\s*["\'][A-Z_]+["\']', re.IGNORECASE),
    # WHY: bare `"expected":` matches legit pytest assertion JSON like
    # {"expected": 200, "actual": 404}, schema validators, and API contract
    # tests. Narrow to the compound pattern that signals a synthetic case
    # bank — "input" key paired with "expected" key in the same object.
    # See review feedback 2026-05-03: false-positive on every pytest result.
    re.compile(r'"input"\s*:\s*[^}]*?"expected"\s*:', re.IGNORECASE | re.DOTALL),
    # Test/example lists (only if contains "test" or "example" in variable name)
    re.compile(r"(?:test_?cases?|examples?)\s*=\s*\[", re.IGNORECASE),
)

# WHY: perfect scores on noisy real-world tasks are statistically suspicious.
# These patterns in a Bash output signal potential theater.
PERFECT_SCORE_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"F1\s*[=:]\s*1\.0{1,3}\b", re.IGNORECASE),  # F1=1.0 or 1.000
    re.compile(r"precision\s*[=:]\s*1\.0{1,3}\b", re.IGNORECASE),
    re.compile(r"recall\s*[=:]\s*1\.0{1,3}\b", re.IGNORECASE),
    re.compile(r"accuracy\s*[=:]\s*100%", re.IGNORECASE),
    re.compile(
        r"all\s+\d+\s+(?:tests?|cases?|niches?)\s+(?:passed|validated|success)", re.IGNORECASE
    ),
    re.compile(r"\d+/\d+\s+(?:VALIDATED|SUCCESS|PASSED).*100%", re.IGNORECASE),
    # WHY: standalone "100%" in validation context (not "100% of X" which is vague)
    re.compile(r"\b100%\s+(?:success|passed|validated|correct|accurate)", re.IGNORECASE),
)

# WHY: these tool names signal we're looking at test/validation activity.
VALIDATION_TOOL_NAMES = {"Write", "Bash"}

# WHY: markers that indicate real-world data (NOT synthetic)
REAL_DATA_MARKERS = [
    re.compile(r"\[VERIFIED-REAL\]", re.IGNORECASE),
    re.compile(r"production\s+(logs|data|dataset)", re.IGNORECASE),
    re.compile(r"real\s+(customer|user|world)\s+data", re.IGNORECASE),
    re.compile(r"external\s+(?:benchmark|dataset)", re.IGNORECASE),
    re.compile(r"(?:https?://|s3://|gs://)", re.IGNORECASE),  # URL = external data
]

# WHY: markers that indicate synthetic data
SYNTHETIC_MARKERS = [
    re.compile(r"\[VERIFIED-SYNTHETIC\]", re.IGNORECASE),
    re.compile(r"synthetic|mock_data|create_synthetic|SYNTHETIC_", re.IGNORECASE),
    re.compile(r"fake|generate_fake|dummy", re.IGNORECASE),
]


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
        "NOT [VERIFIED-REAL]. Hypothesis validation requires [VERIFIED-REAL] "
        "with ≥3 real sources.\n"
        "Action: use real-world data (URLs, datasets, files) before claiming validation."
    )


def should_block_validation(output: str) -> bool:
    """Check if validation should be blocked (critical theater case).

    Returns True if:
    - Perfect score detected (F1=1.000, 100%, all passed) AND
    - Synthetic data markers present AND
    - NO real-data markers

    WHY: Perfect score on synthetic data = highest-risk validation theater.
    ArgosArb incident would have been prevented by blocking this case.

    Note: No minimum length filter — blocking is critical even for short outputs.
    """
    if not output:
        return False

    # Check for perfect score
    has_perfect_score = any(p.search(output) for p in PERFECT_SCORE_PATTERNS)
    if not has_perfect_score:
        return False

    # Check for real data markers (if present, don't block)
    has_real_data = any(m.search(output) for m in REAL_DATA_MARKERS)
    if has_real_data:
        return False

    # Check for synthetic markers (if absent, don't block)
    has_synthetic = any(m.search(output) for m in SYNTHETIC_MARKERS)
    if not has_synthetic:
        return False

    # All conditions met: perfect score + synthetic + no real data → BLOCK
    return True


def check_bash_for_perfect_scores(tool_response: str) -> str | None:
    """Check Bash output for suspiciously perfect validation scores."""
    matches = [p.pattern for p in PERFECT_SCORE_PATTERNS if p.search(tool_response)]
    if not matches:
        return None

    return (
        "[validation-theater-guard] 🔴 Perfect score detected in output.\n"
        f"Triggered by: {', '.join(matches[:2])}\n"
        "Per audit-verification-gate.md: F1=1.000 / 100% on noisy real-world tasks "
        "is statistically suspicious.\n"
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

        if not output:
            sys.exit(0)

        # WHY: Check blocking condition FIRST (critical case) — no length filter
        # Blocking is critical even for short outputs (e.g., "F1=1.000 synthetic")
        if should_block_validation(output):
            # BLOCK: perfect score + synthetic data = validation theater
            session_id = data.get("session_id", "")
            log_hook_trigger(
                hook_name=HOOK_NAME,
                trigger_type="perfect_score_synthetic",
                action="block",
                sample=output[:200],
                session_id=session_id,
            )
            # Print error to stderr so user sees it
            print(
                "[validation-theater-guard] 🚫 BLOCKED: Perfect score on synthetic data detected.\n"
                "Per audit-verification-gate.md: F1=1.000 / 100% on synthetic/mock data "
                "is validation theater (tautology).\n"
                "Action required: Use [VERIFIED-REAL] with ≥3 real sources, or invoke /skeptic.\n"
                "If this is a unit test, mark with [PILOT-ONLY] to bypass.",
                file=sys.stderr,
            )
            sys.exit(1)  # Hard block

        # Non-critical: warn if length sufficient
        if len(output) > 50:
            warning = check_bash_for_perfect_scores(output)

    if warning:
        # WHY: telemetry call BEFORE emit_hook_result — if context output fails
        # for any reason (unrelated bug), we still have a record that the
        # guard fired. Action="warning" because VTG is advisory, not blocking.
        # session_id pulled from hook payload when Claude Code provides it.
        session_id = data.get("session_id", "")
        # Pick first synthetic OR perfect-score pattern as the trigger label
        # so dashboard counts roll up by category, not by individual regex.
        trigger_type = "perfect_score" if "Perfect score" in warning else "synthetic_data"
        # Pull the matched-patterns line from the warning for the sample —
        # already trimmed by the check_* helpers. sanitize_text() in
        # log_hook_trigger truncates to 200 chars regardless.
        sample = warning.split("\n", 2)[1] if "\n" in warning else warning[:200]
        log_hook_trigger(
            hook_name=HOOK_NAME,
            trigger_type=trigger_type,
            action="warning",
            sample=sample,
            session_id=session_id,
        )
        emit_hook_result("PostToolUse", warning)


if __name__ == "__main__":
    main()
