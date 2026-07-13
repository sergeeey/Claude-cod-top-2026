#!/usr/bin/env python3
"""PostToolUse hook: auto-detect patterns requiring skeptic falsification.

WHY: Perfect scores (F1=1.000), "all passed" claims, and synthetic evidence
often indicate validation theater. Skeptic agent can falsify these claims
BEFORE they reach production or user-facing reports.

Real incident: ТОП-10 ArgosArb validation declared 100% SUCCESS on synthetic
data. Manual skeptic invocation revealed 50-100% failure rates on real data.

Triggers on: Agent, Bash, Skill responses that contain high-confidence claims.
Does NOT block -- suggests /skeptic invocation for independent verification.

WHY (P0.4, follow-up audit 2026-07-13): the code has always gated on
VALIDATION_TOOL_NAMES = {"Agent", "Bash", "Skill"}, but hooks/settings.json
only ever registered this hook on matcher "Skill|Agent" -- the entire Bash
branch, including the ArgosArb-critical hard-block path below, was dead code.
Same bug class as F-12 (validation_theater_guard.py, security audit
2026-07-12), just undiscovered until a systematic registry-vs-settings CI
gate existed. Fixed by adding this hook to the existing PostToolUse(Bash)
matcher group in settings.json.

WHY the "Hard block" language below is now corrected: this hook is
registered on PostToolUse, which fires AFTER the tool call already
completed -- exit code 2 here surfaces the warning as prominently as
PostToolUse allows (Claude Code docs: exit 2 on PostToolUse still cannot
undo the completed call, only makes the warning maximally visible), it does
not and cannot prevent the ArgosArb-shaped claim from having already been
produced. Same limitation established in F-03/F-12.

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
    # WHY not a bare URL-scheme match: any http(s)/s3/gs URL occurring
    # ANYWHERE in the response (an unrelated doc link, a comment) previously
    # counted as "real data" and let the ArgosArb hard-block be dodged.
    # Require the URL to appear near an explicit dataset/source word.
    re.compile(
        r"(?:https?://|s3://|gs://)\S+.{0,30}\b(dataset|data source|corpus)\b", re.IGNORECASE
    ),
    re.compile(r"\b(dataset|data source|corpus)\b.{0,30}(?:https?://|s3://|gs://)", re.IGNORECASE),
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


def is_argosarb_critical_pattern(text: str) -> bool:
    """Detect the T1+T2 ArgosArb signature independent of escape hatches.

    WHY a separate function, not reusing check_response_for_skeptic_triggers():
    that function intentionally lets [PILOT-ONLY]/[SYNTHETIC-ACKNOWLEDGED]/
    [DEFER-SKEPTIC] suppress the soft-warning path (legitimate for genuine
    prototypes and documented synthetic data). But skeptic-triggers.md's own
    Escape Hatches section says "Never override: Production validation
    claims, customer-facing metrics" -- the highest-risk signature (perfect
    metric + high-confidence claim, no real-data citation) must never be
    silently bypassed by any hatch, including [DEFER-SKEPTIC] (documented for
    "time-critical, validate later", not "skip validation entirely").
    """
    if not text:
        return False
    has_t1 = bool(_TRIGGER_1_PATTERN.search(text))
    has_t2 = bool(_TRIGGER_2_PATTERN.search(text))
    has_real_data = any(m.search(text) for m in _REAL_DATA_MARKERS)
    return has_t1 and has_t2 and not has_real_data


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

    # WHY compute the critical check BEFORE the escape-hatch-aware trigger
    # list, and independent of it: check_response_for_skeptic_triggers()
    # returns [] the moment any escape hatch is present, which previously
    # short-circuited main() via `if not triggered: sys.exit(0)` -- meaning
    # [DEFER-SKEPTIC] silently suppressed the ArgosArb hard-block too, not
    # just the soft warning it's meant to defer.
    is_critical = is_argosarb_critical_pattern(response)

    triggered = check_response_for_skeptic_triggers(response)
    if not triggered and not is_critical:
        sys.exit(0)

    # WHY: Map trigger indices to human-readable names for telemetry
    trigger_names = [
        "high_confidence_claim",  # 100%, all, zero, perfect
        "perfect_metric",  # F1=1.000, precision=1.0
        "synthetic_evidence",  # [VERIFIED-SYNTHETIC]
        "round_number",  # 1.000, 0.990
        "inline_synthetic",  # embedded tuples/dicts as test data
    ]
    # WHY fall back to a synthesized index list: if an escape hatch
    # suppressed `triggered` but is_critical is still True (bypasses hatches),
    # trigger_names[triggered[0]] would otherwise raise on an empty list.
    if not triggered:
        triggered = [0, 1]
    trigger_type = trigger_names[triggered[0]]  # Report first trigger

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
        # Strongest available signal (exit 2), not a true block -- PostToolUse
        # fires after the tool call already completed (see module docstring).
        print(
            "[skeptic-auto-trigger] 🚫 STOP: ArgosArb pattern detected.\n"
            f"Triggers fired: {', '.join(trigger_names[i] for i in triggered)}\n"
            "The response already exists -- this cannot undo that -- but do "
            "NOT treat it as valid evidence.\n"
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
