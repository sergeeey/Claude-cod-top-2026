#!/usr/bin/env python3
"""Deterministic core for boyko-toolcheck: readiness levels, run classification, redaction.

WHY: a PASS must mean only what was actually checked. `codex --version` proves the binary
starts, not that it is authenticated or that a real workflow works. This module keeps the
levels separate, refuses to report a higher level than was reached, and redacts secrets
before output is saved. It runs no commands itself; the agent runs them and passes results in.

Levels (ordered): DISCOVERED < STARTS < AUTHENTICATED < FUNCTIONAL < WORKFLOW_READY.
"""

from __future__ import annotations

import json
import re

LEVELS = ["DISCOVERED", "STARTS", "AUTHENTICATED", "FUNCTIONAL", "WORKFLOW_READY"]

# WHY: patterns cover the classes the audit named: tokens, passwords, auth headers,
# API keys in sk- form, and user-specific home paths. Codes, versions and statuses are kept.
_REDACT_RULES = [
    (re.compile(r"(?i)(authorization\s*:\s*)(bearer\s+)?\S+"), r"\1[REDACTED]"),
    (
        re.compile(r"(?i)\b(token|secret|password|passwd|api[_-]?key)(\s*[:=]\s*)\S+"),
        r"\1\2[REDACTED]",
    ),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"), "[REDACTED]"),
    (re.compile(r"(?i)([A-Za-z]:[\\/]+Users[\\/]+)[^\\/\s]+"), r"\1[USER]"),
    (re.compile(r"(/home/)[^/\s]+"), r"\1[USER]"),
]


def redact(text: str) -> str:
    """Replace secret values and user-specific home paths; keep the surrounding evidence."""
    out = text
    for pattern, repl in _REDACT_RULES:
        out = pattern.sub(repl, out)
    return out


def classify_run(exit_code: int | None, stdout: str, timed_out: bool, not_found: bool) -> str:
    """Classify one command run for the STARTS level.

    Returns NOT_FOUND, TIMEOUT, FAIL or PASS. A zero exit code is not enough: if the output
    is a JSON object with an 'error' key, the run failed even though it exited with 0.
    """
    if not_found:
        return "NOT_FOUND"
    if timed_out:
        return "TIMEOUT"
    if exit_code != 0:
        return "FAIL"
    stripped = stdout.strip()
    if stripped.startswith("{"):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return "PASS"
        if isinstance(payload, dict) and "error" in payload:
            return "FAIL"
    if not stripped:
        return "FAIL"
    return "PASS"


def overall(checks: dict[str, str], claim: str) -> dict:
    """Derive the overall verdict from per-level results.

    checks: level -> PASS | FAIL | NOT_RUN. The reached level is the highest one such that
    it and every lower level are PASS. PASS overall requires WORKFLOW_READY to be reached.
    The claim must name the reached level; a claim above it is reported as an error.
    """
    reached = None
    for level in LEVELS:
        if checks.get(level) == "PASS":
            reached = level
        else:
            break

    if reached == "WORKFLOW_READY":
        verdict = "PASS"
    elif reached is None:
        verdict = "FAIL"
    else:
        verdict = "PARTIAL"

    errors: list[str] = []
    claimed = next((lvl for lvl in LEVELS if lvl in claim.upper()), None)
    if claimed and reached is not None and LEVELS.index(claimed) > LEVELS.index(reached):
        errors.append(f"claim names {claimed} but only {reached} was reached")
    if claimed and reached is None:
        errors.append(f"claim names {claimed} but nothing was reached")

    return {"overall": verdict, "reached": reached, "claim": claim, "errors": errors}


def tool_report(name: str, command: str, levels: dict[str, str], evidence: str) -> dict:
    """Build the structured result shape used in the SKILL output."""
    return {
        "tool": name,
        "command": redact(command),
        "levels": levels,
        "evidence": redact(evidence),
    }
