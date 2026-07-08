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
import time

from hook_state import HookState
from utils import emit_hook_result, log_hook_trigger, parse_stdin

# WHY 30 min: same-session window for correlating a synthetic-flagged Write
# with a later Bash run of that same validator — long enough to cover a
# normal edit-then-run cycle, short enough not to flag an unrelated later run.
_SYNTHETIC_WRITE_TTL_SECONDS = 30 * 60

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
    # WHY not a bare URL-scheme match: any http(s)/s3/gs URL occurring ANYWHERE
    # in the output (an unrelated doc link, a comment, a citation in a
    # docstring) previously counted as "real data" and let a synthetic
    # perfect-score claim dodge the block. Require the URL to appear near an
    # explicit dataset/source word so it reads as an actual data citation.
    re.compile(
        r"(?:https?://|s3://|gs://)\S+.{0,30}\b(dataset|data source|corpus)\b", re.IGNORECASE
    ),
    re.compile(r"\b(dataset|data source|corpus)\b.{0,30}(?:https?://|s3://|gs://)", re.IGNORECASE),
]

# WHY: markers that indicate synthetic data
SYNTHETIC_MARKERS = [
    re.compile(r"\[VERIFIED-SYNTHETIC\]", re.IGNORECASE),
    re.compile(r"synthetic|mock_data|create_synthetic|SYNTHETIC_", re.IGNORECASE),
    re.compile(r"fake|generate_fake|dummy", re.IGNORECASE),
]

# WHY these specific claim phrases (user-confirmed decision, external
# security audit 2026-07-07): a regex/keyword detector can always be evaded
# by paraphrasing a perfect-score claim ("model showed ideal quality on
# generated samples" instead of "F1=1.0") -- no amount of pattern-tuning
# closes that gap. The fix is not a better regex, it's inverting the
# default: production-confidence language requires POSITIVE evidence, not
# merely the absence of a synthetic-data confession.
_PRODUCTION_CLAIM_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bproduction[- ]ready\b", re.IGNORECASE),
    re.compile(r"\bverified\b", re.IGNORECASE),
    re.compile(r"\bvalidated\b", re.IGNORECASE),
    re.compile(r"\bworks reliably\b", re.IGNORECASE),
    re.compile(r"\bsafe to (?:deploy|use|ship)\b", re.IGNORECASE),
    re.compile(r"\bsecure\b", re.IGNORECASE),
]

# WHY these specific markers count as "positive evidence": this repo already
# has an established evidence-marker taxonomy (rules/integrity.md) enforced
# elsewhere -- reusing it here is more consistent than inventing a separate
# structured-evidence schema with no other precedent in this codebase.
_EVIDENCE_MARKERS: list[re.Pattern] = [
    re.compile(r"\[VERIFIED-REAL\]", re.IGNORECASE),
    re.compile(r"\[VERIFIED-SYNTHETIC\]", re.IGNORECASE),
    re.compile(r"\[VERIFIED-INLINE\]", re.IGNORECASE),
    re.compile(r"\[VERIFIED-tool\]", re.IGNORECASE),
    re.compile(r"\[HYPOTHESIS\]", re.IGNORECASE),
    re.compile(r"\[INFERRED\]", re.IGNORECASE),
]


def check_unsubstantiated_production_claim(output: str) -> str | None:
    """Warn when production-confidence language appears with no evidence
    marker anywhere in the same output.

    WHY: "no synthetic markers found" was previously the closest thing to a
    real-evidence signal this hook had -- but absence of a fake-data
    confession is not proof of a real one. This check requires POSITIVE
    evidence (this repo's own [VERIFIED-*]/[HYPOTHESIS]/[INFERRED] marker
    taxonomy) before letting production-confidence language pass unremarked.
    """
    claim_matches = [p.pattern for p in _PRODUCTION_CLAIM_PATTERNS if p.search(output)]
    if not claim_matches:
        return None

    if any(m.search(output) for m in _EVIDENCE_MARKERS):
        return None

    return (
        "[validation-theater-guard] ⚠️ Production-confidence claim without an evidence marker.\n"
        f"Claim language found: {', '.join(claim_matches[:3])}\n"
        "Per rules/integrity.md: this needs [VERIFIED-REAL] / [VERIFIED-SYNTHETIC] / "
        "[VERIFIED-INLINE] / [HYPOTHESIS] / [INFERRED] -- absence of a synthetic/fake "
        "marker is NOT evidence the claim is real.\n"
        "Mark the claim's actual evidence level before treating it as settled."
    )


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

    # WHY record this: a later Bash run of this same validator may print a
    # perfect score without ever repeating a "synthetic" keyword in ITS OWN
    # output -- should_block_validation() previously had no memory of this
    # Write, so that later Bash call sailed through unblocked.
    state = HookState("validation_theater_guard")
    state["last_synthetic_write"] = {"file": file_path, "time": time.time()}
    state.save()

    return (
        f"[validation-theater-guard] ⚠️ Synthetic data detected in validator: {file_path}\n"
        f"Patterns found: {', '.join(matches)}\n"
        "Per audit-verification-gate.md: synthetic tests = [VERIFIED-SYNTHETIC], "
        "NOT [VERIFIED-REAL]. Hypothesis validation requires [VERIFIED-REAL] "
        "with ≥3 real sources.\n"
        "Action: use real-world data (URLs, datasets, files) before claiming validation."
    )


def _recent_synthetic_write_exists() -> bool:
    """Return True if a synthetic-flagged validator was written within the TTL window."""
    state = HookState("validation_theater_guard")
    record = state.get("last_synthetic_write")
    if not isinstance(record, dict):
        return False
    written_at = record.get("time")
    if not isinstance(written_at, (int, float)):
        return False
    return (time.time() - written_at) < _SYNTHETIC_WRITE_TTL_SECONDS


def should_block_validation(output: str) -> bool:
    """Check if validation should be blocked (critical theater case).

    Returns True if:
    - Perfect score detected (F1=1.000, 100%, all passed) AND
    - Synthetic data markers present (in this output, OR a synthetic-flagged
      validator was written recently in this session) AND
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

    # Check for synthetic markers (if absent, don't block) — either restated
    # in this output, or correlated from a recent synthetic Write (see WHY above).
    has_synthetic = any(m.search(output) for m in SYNTHETIC_MARKERS)
    has_synthetic = has_synthetic or _recent_synthetic_write_exists()
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
            warning = check_bash_for_perfect_scores(
                output
            ) or check_unsubstantiated_production_claim(
                output,
            )

    if warning:
        # WHY: telemetry call BEFORE emit_hook_result — if context output fails
        # for any reason (unrelated bug), we still have a record that the
        # guard fired. Action="warning" because VTG is advisory, not blocking.
        # session_id pulled from hook payload when Claude Code provides it.
        session_id = data.get("session_id", "")
        # Pick the matching trigger label so dashboard counts roll up by
        # category, not by individual regex.
        if "Perfect score" in warning:
            trigger_type = "perfect_score"
        elif "Production-confidence claim" in warning:
            trigger_type = "unsubstantiated_claim"
        else:
            trigger_type = "synthetic_data"
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
