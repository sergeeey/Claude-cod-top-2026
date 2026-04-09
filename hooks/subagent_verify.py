#!/usr/bin/env python3
"""SubagentStop hook: verify deliverables before accepting agent output.

WHY: Agents sometimes return empty or low-quality results. Verifying
that the last_assistant_message is non-trivial catches wasted agent runs
and prompts the orchestrator to retry or escalate.

Check 4 (Audit Verification Gate) — borrowed from VeriFind methodology:
Agent's [VERIFIED] ≠ orchestrator's [VERIFIED]. Explorer/analyzer agents
read files in isolation and produce false positives. HIGH or MEDIUM findings
without [VERIFIED-tool] evidence must be flagged before reaching the user.
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from utils import parse_stdin

# WHY: short responses often indicate the agent failed silently
MIN_RESPONSE_LENGTH = 50

# WHY: these markers indicate tool-confirmed evidence per audit-verification-gate.md
_VERIFIED_TOOL_PATTERN = re.compile(
    r"\[VERIFIED-tool\]|\[VERIFIED-pytest\]|\[VERIFIED-grep\]|\[VERIFIED-bash\]"
    r"|\[DISMISSED\]|\[HYPOTHESIS\]",
    re.IGNORECASE,
)

# WHY: HIGH/MEDIUM claims that lack [VERIFIED-tool] are false positive risks —
# the gate requires every such finding to carry tool-confirmed evidence before
# it reaches the user (audit-verification-gate.md Hard Rule).
_HIGH_MEDIUM_PATTERN = re.compile(
    # WHY: no DOTALL — each HIGH/MEDIUM claim must match within one line.
    # With DOTALL a single greedy .{0,120} absorbs multiple newlines and
    # merges two separate findings into one match, under-counting them.
    r"\b(HIGH|MEDIUM)\b.{0,120}(bug|issue|vulnerability|error|problem|risk|danger|wrong|missing|broken)",
    re.IGNORECASE,
)

# Minimum HIGH/MEDIUM findings to trigger gate warning (avoid noise on 1 mention)
_MIN_FINDINGS_FOR_GATE = 2


def _count_unverified_findings(text: str) -> int:
    """Count HIGH/MEDIUM findings that lack any [VERIFIED-tool] marker nearby.

    WHY: checks paragraph-level proximity (500 chars) — if [VERIFIED-tool] appears
    within the same block as the HIGH/MEDIUM claim, the gate is satisfied.
    """
    findings = list(_HIGH_MEDIUM_PATTERN.finditer(text))
    if not findings:
        return 0

    has_any_verified = bool(_VERIFIED_TOOL_PATTERN.search(text))
    if has_any_verified:
        # At least some findings are verified — count only unverified ones
        unverified = 0
        for match in findings:
            start = max(0, match.start() - 500)
            end = min(len(text), match.end() + 500)
            vicinity = text[start:end]
            if not _VERIFIED_TOOL_PATTERN.search(vicinity):
                unverified += 1
        return unverified
    else:
        # No verification markers at all
        return len(findings)


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    agent_type = data.get("agent_type", "unknown")
    agent_id = data.get("agent_id", "unknown")
    last_message = data.get("last_assistant_message", "")
    session_id = data.get("session_id", "unknown")

    issues: list[str] = []

    # Check 1: non-empty response
    if not last_message or not last_message.strip():
        issues.append("empty response")

    # Check 2: suspiciously short response
    elif len(last_message.strip()) < MIN_RESPONSE_LENGTH:
        issues.append(f"response too short ({len(last_message.strip())} chars)")

    # Check 3: agent returned an error/apology instead of deliverable
    apology_markers = [
        "I apologize",
        "I'm sorry",
        "I cannot",
        "I wasn't able to",
        "unable to complete",
    ]
    if any(marker.lower() in last_message.lower() for marker in apology_markers):
        issues.append("response contains apology/failure markers")

    # Check 4: Audit Verification Gate
    # WHY: explorer/analyzer agents produce HIGH/MEDIUM findings without tool
    # verification (grep/pytest/bash). These are [HYPOTHESIS] not [VERIFIED-tool].
    # Gate: ≥2 unverified findings → warn orchestrator to verify before presenting.
    if last_message:
        unverified = _count_unverified_findings(last_message)
        if unverified >= _MIN_FINDINGS_FOR_GATE:
            issues.append(
                f"{unverified} HIGH/MEDIUM findings without [VERIFIED-tool] evidence "
                f"(audit-verification-gate.md). Verify with pytest/grep/bash before "
                f"presenting to user — treat as [HYPOTHESIS] until confirmed."
            )

    # Log result
    log_dir = Path.home() / ".claude" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "subagent_verify.jsonl"

    try:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "agent_type": agent_type,
            "agent_id": agent_id,
            "session_id": session_id,
            "response_length": len(last_message.strip()) if last_message else 0,
            "issues": issues,
            "verdict": "FAIL" if issues else "PASS",
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass

    # Warn orchestrator if issues found
    if issues:
        warning = (
            f"[subagent-verify] WARNING: {agent_type} agent returned "
            f"low-quality output: {'; '.join(issues)}. "
            f"Consider retrying or escalating."
        )
        print(json.dumps({"result": "info", "message": warning}))


if __name__ == "__main__":
    main()
