#!/usr/bin/env python3
"""PostToolUse hook: auto-detect patterns requiring skeptic falsification.

WHY: Perfect scores (F1=1.000), "all passed" claims, and synthetic evidence
often indicate validation theater. Skeptic agent can falsify these claims
BEFORE they reach production or user-facing reports.

Real incident: ТОП-10 ArgosArb validation declared 100% SUCCESS on synthetic
data. Manual skeptic invocation revealed 50-100% failure rates on real data.

Triggers on: Agent, Bash responses that contain high-confidence claims.
Does NOT block — suggests /skeptic invocation for independent verification.

Based on: skeptic-triggers.md (5 auto-invoke triggers)
Related: validation_theater_guard.py (detects theater, this suggests action)
"""

import os
import re
import sys

from utils import emit_hook_result, extract_tool_response, log_hook_trigger, parse_stdin

HOOK_NAME = "skeptic_auto_trigger"

# WHY: Trigger definitions from skeptic-triggers.md:116-121
# These patterns indicate claims with high risk of confirmation bias.

# Trigger 1: High-confidence claims (100%, all, zero, perfect)
# Pattern: Any statement with ≥90% confidence language
# WHY: DOTALL allows .* to match newlines between "all" and "validated"
# Second part (action word) is optional — "100%" alone triggers
# WHY: no trailing \b after % — word boundaries don't work with symbols
# WHY: (?<!-) negative lookbehind prevents "Near-perfect" false positive
_TRIGGER_1_PATTERN = re.compile(
    r"\b(100%|all\s+\d+|zero\s+(?:failures?|errors?|bugs?)|(?<!-)perfect\s+\w+)"
    r"(?:.*\b(passed|validated|success|correct|accurate))?",
    re.IGNORECASE | re.DOTALL,
)

# Trigger 2: Perfect metrics (F1=1.000, precision=1.0, recall=1.000)
# WHY: Real-world noisy tasks rarely achieve perfect decimals
# Pattern: metric = 1.0 or 1.00 or 1.000 (1-3 zeros after decimal)
_TRIGGER_2_PATTERN = re.compile(
    r"(F1|precision|recall|accuracy)\s*[=:]\s*1\.0{1,3}\b",
    re.IGNORECASE,
)

# Trigger 3: Synthetic evidence marker
# WHY: [VERIFIED-SYNTHETIC] is valid for unit tests but INVALID for validation
_TRIGGER_3_PATTERN = re.compile(r"\[VERIFIED-SYNTHETIC\]", re.IGNORECASE)

# Trigger 4: Round numbers (suspiciously perfect decimals)
# Pattern: Metric ending in .000 or .00 (e.g., 1.000, 0.990, 0.9900)
# WHY: Real metrics are messy. Perfect decimals suggest rounding/cherry-picking.
# Matches: X.YY0, X.YYY0, X.YYYY0 where last digit is 0
_TRIGGER_4_PATTERN = re.compile(
    r"\b\d\.\d{2,}0\b",  # Matches 1.000, 0.990, 0.9900 (≥3 decimals, last=0)
)

# Trigger 5: Inline synthetic data (from skeptic-triggers.md:56-65)
# WHY: Hardest to detect — no create_synthetic_dataset() function name,
# just embedded tuples/dicts in validation code that prove nothing about real data.
# abstracts = [("text", "LABEL"), ...] OR test_cases = [...] OR {"expected": "VAL"}
_TRIGGER_5_PATTERN = re.compile(
    r"(?:"
    r'\w+\s*=\s*\[\s*\(["\'][^"\']{1,100}["\'],\s*["\'][A-Z_]{2,}["\']'  # ("text", "LABEL")
    r'|"expected"\s*:\s*["\']'  # {"expected": "value"}
    r"|(?:test_?cases?|test_?examples?)\s*=\s*\["  # test_cases = [
    r")",
    re.IGNORECASE,
)

# WHY: Lambda functions from skeptic-triggers.md:116-121 converted to compiled regex
# for performance. Lambdas re-compile regex on every call; pre-compiled = 10x faster.
SKEPTIC_TRIGGERS: list[re.Pattern] = [
    _TRIGGER_1_PATTERN,  # 100% / all / zero / perfect
    _TRIGGER_2_PATTERN,  # F1=1.000 / precision=1.0
    _TRIGGER_3_PATTERN,  # [VERIFIED-SYNTHETIC]
    _TRIGGER_4_PATTERN,  # Round numbers
    _TRIGGER_5_PATTERN,  # Inline synthetic data (embedded tuples/dicts)
]

# WHY: if real-world data markers present, relax the hard block.
# Agent is doing the right thing — it cites real sources.
_REAL_DATA_MARKERS: tuple[re.Pattern, ...] = (
    re.compile(r"\[VERIFIED-REAL\]", re.IGNORECASE),
    re.compile(r"(?:https?://|s3://|gs://)", re.IGNORECASE),
    re.compile(r"production\s+(?:logs?|data|dataset)\b", re.IGNORECASE),
    re.compile(r"external\s+(?:benchmark|dataset)\b", re.IGNORECASE),
)

# WHY: these tool names produce responses that can contain validation claims
VALIDATION_TOOL_NAMES = {"Agent", "Bash", "Skill"}

# Escape hatches from skeptic-triggers.md:150-160
_ESCAPE_HATCHES = [
    re.compile(r"\[PILOT-ONLY\]", re.IGNORECASE),
    re.compile(r"\[SYNTHETIC-ACKNOWLEDGED\]", re.IGNORECASE),
    re.compile(r"\[DEFER-SKEPTIC\]", re.IGNORECASE),
]


def check_response_for_skeptic_triggers(text: str) -> list[int]:
    """Scan text for skeptic trigger patterns.

    Returns:
        List of trigger indices that fired (0-3). Empty if no triggers.

    WHY: Separated from main() for testability and reuse.
    """
    if not text:
        return []

    # WHY: Minimum length filter only in production (main()), not in tests.
    # Allows unit tests to use short strings like "F1=1.000"

    # WHY: Check escape hatches first — they suppress all triggers
    for escape in _ESCAPE_HATCHES:
        if escape.search(text):
            return []

    triggered = []
    for i, pattern in enumerate(SKEPTIC_TRIGGERS):
        if pattern.search(text):
            triggered.append(i)

    return triggered


def main() -> None:
    # WHY: recursion guard — don't trigger inside subagent calls
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    data = parse_stdin()
    if not data:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name not in VALIDATION_TOOL_NAMES:
        sys.exit(0)

    response = extract_tool_response(data)
    if not response or len(response) < 50:
        # WHY: Skip very short responses (likely not validation claims)
        sys.exit(0)

    triggered = check_response_for_skeptic_triggers(response)
    if not triggered:
        sys.exit(0)

    # WHY: Map trigger indices to human-readable names for telemetry
    trigger_names = [
        "high_confidence_claim",  # 100%, all, zero, perfect
        "perfect_metric",  # F1=1.000, precision=1.0
        "synthetic_evidence",  # [VERIFIED-SYNTHETIC]
        "round_number",  # 1.000, 0.990
        "inline_synthetic",  # embedded tuples/dicts as test data
    ]
    trigger_type = trigger_names[triggered[0]]  # Report first trigger

    # WHY: Hard block when T1 + T2 fire together WITHOUT real-data markers.
    # This is the ArgosArb signature: "100% SUCCESS" + "F1=1.000" together.
    # A warning is insufficient — the claim must be quarantined before user sees it.
    # exit(2) vs exit(1) distinguishes skeptic block from validation_theater_guard block.
    is_critical = (
        0 in triggered  # T1: high confidence claim
        and 1 in triggered  # T2: perfect metric
        and not any(m.search(response) for m in _REAL_DATA_MARKERS)
    )

    session_id = data.get("session_id", "")
    sample = response[:200]  # log_hook_trigger truncates anyway

    # WHY: telemetry before output — if emit fails for any reason,
    # we still have a record that the guard fired.
    log_hook_trigger(
        hook_name=HOOK_NAME,
        trigger_type=trigger_type,
        action="block" if is_critical else "warning",
        sample=sample,
        session_id=session_id,
    )

    if is_critical:
        # Hard block: ArgosArb pattern — T1 + T2 without real data.
        print(
            "[skeptic-auto-trigger] 🚫 BLOCKED: ArgosArb pattern detected.\n"
            f"Triggers fired: {', '.join(trigger_names[i] for i in triggered)}\n"
            "Per skeptic-triggers.md: high_confidence_claim + perfect_metric "
            "together = validation theater red flag.\n"
            "MANDATORY: invoke Agent(subagent_type='skeptic') before presenting this result.\n"
            "Override: add [VERIFIED-REAL] with ≥3 real sources, or [PILOT-ONLY] for prototypes.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Soft warning for single triggers or non-critical combos.
    trigger_labels = [trigger_names[i] for i in triggered]
    warning = (
        f"[skeptic-auto-trigger] ⚠️ Skeptic triggers detected: {', '.join(trigger_labels)}\n"
        "Per skeptic-triggers.md: these patterns REQUIRE falsification testing.\n"
        "MANDATORY: invoke Agent(subagent_type='skeptic') or `skeptic:` inline "
        "before presenting this result to the user.\n"
        f"Triggered: {len(triggered)}/5 patterns (see skeptic-triggers.md for details).\n"
        "Override with [PILOT-ONLY] (prototypes) or [DEFER-SKEPTIC] (production incidents)."
    )

    emit_hook_result("PostToolUse", warning)


if __name__ == "__main__":
    main()
