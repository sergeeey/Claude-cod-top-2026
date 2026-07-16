#!/usr/bin/env python3
"""RFC-003 step 3 — deterministic response-guard severity calibrator (NOT wired live).

WHY: the response guards over-warn on benign security prose and under-detect real
injections phrased around their keywords (see experiments/20260716-response-guard-fp-
calibration/severity_calibration_baseline.md). RFC-003 fixes this by CALIBRATING severity,
never by suppressing a signal: the raw match is always preserved; only how loudly it
surfaces changes.

This module is a PURE FUNCTION. It is deliberately NOT imported by web_response_guard.py or
mcp_response_guard.py yet — wiring it (log-only) is shadow mode (step 5), after the step-4
red-team. Building it standalone means it changes zero live behavior: it can be measured
against the corpus and attacked without any risk to the running guard.

The load-bearing rule (from the RFC-002 red-team): a downgrade fires ONLY when
  (provable descriptive/quoted context)  AND  (NO strong directive to the agent).
A directive keeps HIGH even inside a quote/fence, AND raising a missed imperative to HIGH is
the detection-adder half of the strong-directive signal. Context may only LOWER volume
(never make an untrusted source trusted); a directive may only RAISE the threat flag. Both
err toward warning. Any error returns the original severity unchanged (fail-safe).

The strong-directive and descriptive detectors are regex — hence regex-limited, and WILL
miss novel phrasings. That imperfection is the entire reason RFC-003 mandates shadow mode
before any displayed behavior changes: shadow mode surfaces every wrong proposal on real
traffic first.
"""

from __future__ import annotations

import re
from typing import Any

# WHY the bare import (not `from hooks.input_guard`): matches every other hook in this
# dir (web_response_guard, mcp_response_guard) and keeps mypy from seeing input_guard
# under two module names. Callers put hooks/ on sys.path (settings.json / test conftest).
from input_guard import is_high_threat, scan

# --- strong directive: an imperative aimed at the reading agent -----------------
# Doubles as a DETECTION-ADDER: catches imperatives the keyword scan() misses.
_STRONG_DIRECTIVE = re.compile(
    # imperative aimed at the agent (incl. "ignore your rules", "ignore what the user said")
    r"ignore (all |the |your |what )?"
    r"(previous|prior|above|earlier|the user|your |rules?|instructions?)"
    r"|disregard (all |the )?(previous |prior |above |earlier |the )?\s*(instruction|rule)"
    r"|forget (all |your )?(previous |prior )?instruction"
    r"|you are now\b|you (must|should|may) (now )?\b|from now on,? you\b"
    r"|act as (the )?(user|admin|system)\b"
    r"|reveal your\b|print your\b|show me your\b"
    # exfil/secret-request: [^\n] (NOT [^.] — file paths ~/.ssh contain periods) + no \b
    # before the alternation (so \.ssh matches right after a slash).
    r"|(send|upload|email|post|forward|exfiltrat\w*)\b[^\n]{0,60}?"
    r"(to (me\b|my |https?://)|credential|token|password|api[ _-]?key|secret|id_rsa|\.ssh|\.aws)"
    r"|\$\([^)]|\|\s*(sh|bash)\b|rm -rf\b"
    r"|approve (every|all|the|each)\b|delete (all|the|their)\b"
    # RU
    r"|игнорируй (предыдущие|все|что)\b|покажи (свой |твой )?(токен|пароль|ключ|api)"
    r"|отправь [^\n]{0,60}?(на (сервер|http)|мне)",
    re.IGNORECASE,
)

# --- provable descriptive/quoted context ----------------------------------------
_DESCRIPTIVE_PROSE = re.compile(
    r"attacks?\s+(are|is|can|typically|commonly|often|hide|work)"
    r"|commonly divided|is a common|used by attackers|an attacker\b"
    r"|detection\b|scans? for\b|exploit works by|threat model|top llm|security risk"
    r"|\bcategories:|\bincluding\b|the paper\b|per owasp|for reproducibility"
    r"|researchers (study|showed)"
    r"|to (download|install)\b|you can (fetch|download|install)\b|\binstall\b|environment variable"
    r"|returns a promise|best.?practice|deduplicat\w*|our (api )?docs",
    re.IGNORECASE,
)
# Structural markers that a span is being shown AS DATA (fence / quote / citation).
_FENCE = re.compile(r"```|~~~|^\s{4,}\S", re.MULTILINE)
_BLOCKQUOTE = re.compile(r"^\s*>\s", re.MULTILINE)

_ORIGINAL_SILENT = "silent"


def _original_severity(hits: dict[str, int]) -> str:
    """Map the current guard's verdict onto the RFC-003 severity vocabulary."""
    if not hits:
        return _ORIGINAL_SILENT
    return "HIGH" if is_high_threat(hits) else "MEDIUM"


def has_strong_directive(text: str) -> bool:
    return bool(_STRONG_DIRECTIVE.search(text))


def provable_descriptive_context(text: str) -> bool:
    return bool(_DESCRIPTIVE_PROSE.search(text) or _FENCE.search(text) or _BLOCKQUOTE.search(text))


def _calibrate(text: str, hits: dict[str, int]) -> str:
    """Pure severity computation. See module docstring for the rule."""
    directive = has_strong_directive(text)
    # A directive dominates everything: it both blocks a downgrade AND adds detection
    # (raising a missed imperative from silent to HIGH). Never downgraded by context.
    if directive:
        return "HIGH"
    original = _original_severity(hits)
    if original == _ORIGINAL_SILENT:
        # No hit and no directive -> nothing to surface.
        return _ORIGINAL_SILENT
    # There is a hit but no directive. Downgrade ONLY on provable descriptive context.
    if provable_descriptive_context(text):
        return "INFO"
    # Hit, no directive, no descriptive proof -> genuinely borderline.
    return "REQUIRES_CHECK"


def calibrate_severity(
    text: str,
    hits: dict[str, int] | None = None,
    *,
    source_tool: str = "",
    source_ref: str = "",
    detector_version: str = "rfc003-step3",
) -> dict[str, Any]:
    """Return the full RFC-003 calibration record. Fail-safe: on ANY error the effective
    severity equals the original (never lower). suppressed is ALWAYS False -- nothing is
    ever silenced by this layer; only its surfaced volume is calibrated."""
    if hits is None:
        hits = scan([text])
    original = _original_severity(hits)
    try:
        effective = _calibrate(text, hits)
        context = (
            "strong_directive"
            if has_strong_directive(text)
            else "descriptive_or_quoted"
            if provable_descriptive_context(text)
            else "none"
        )
        error = None
    except Exception as exc:  # noqa: BLE001 - fail-safe: never lower severity on error
        effective, context, error = original, "error", type(exc).__name__

    # Fail-safe hard guard: a calibration must never end up LOWER than original unless it
    # went through the descriptive-no-directive path. If anything produced a lower severity
    # by another route, snap back to original.
    _ORDER = {
        "silent": 0, _ORIGINAL_SILENT: 0, "INFO": 1,
        "REQUIRES_CHECK": 2, "MEDIUM": 3, "HIGH": 4,
    }
    if error is not None and _ORDER.get(effective, 0) < _ORDER.get(original, 0):
        effective = original

    return {
        "raw_match": [c for c in hits] if hits else [],
        "category": list(hits.keys()) if hits else [],
        "original_severity": original,
        "effective_severity": effective,
        "context": context,
        "provenance": {
            "source_tool": source_tool,
            "source_ref": source_ref,
            "detector_version": detector_version,
        },
        "action": "treat_as_data",
        "suppressed": False,  # invariant: this layer never suppresses a signal
        "error": error,
    }


if __name__ == "__main__":  # pragma: no cover - manual smoke
    import json
    import sys

    txt = sys.stdin.read()
    print(json.dumps(calibrate_severity(txt), ensure_ascii=False, indent=2))
