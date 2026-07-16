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
# WHY _normalize + HIGH_PRIORITY_CATEGORIES (red-team 2026-07-16): scan() detects on
# NORMALIZED text; the detectors below MUST normalize identically or a Cyrillic homoglyph
# (ignоre) is detected-as-HIGH yet evades the directive regex and downgrades to INFO (C1).
# HIGH_PRIORITY_CATEGORIES (data_exfil/command_injection/encoding_attack) must never be
# downgraded by prose context (C2/C3).
from input_guard import HIGH_PRIORITY_CATEGORIES, _normalize, is_high_threat, scan

# --- strong directive: an imperative aimed at the reading agent -----------------
# Doubles as a DETECTION-ADDER: catches imperatives the keyword scan() misses.
# WHY \s+ everywhere (not literal spaces) + broadened verbs (red-team 2026-07-16): the
# old regex hard-coded single ASCII spaces (so "ignore  previous" / "ignore\tprevious"
# evaded it) and listed too few imperative verbs (transfer/override/disable/escalate went
# silent). Verb-listing is fundamentally unwinnable -- this is best-effort hardening; the
# real backstop for novel phrasings is shadow-mode logging (RFC-003).
_STRONG_DIRECTIVE = re.compile(
    r"ignore\s+(all\s+|the\s+|your\s+|what\s+)?"
    r"(previous|prior|above|earlier|the\s+user|your\s+|rules?|instructions?|safety|checklist)"
    r"|disregard\s+(all\s+|the\s+)?(previous\s+|prior\s+|above\s+|earlier\s+|the\s+)?\s*"
    r"(instruction|rule|checklist|safety)"
    r"|forget\s+(all\s+|your\s+)?(previous\s+|prior\s+)?instruction"
    r"|you\s+are\s+now\b|you\s+(must|should|may)\s+(now\s+)?|from\s+now\s+on|your\s+task\s+is"
    r"|act\s+as\s+(the\s+)?(user|admin|system)\b"
    r"|reveal\s+your\b|print\s+your\b|show\s+me\s+your\b"
    # weaponising verbs against sensitive objects
    r"|(override|disable|enable|escalate|revoke|grant|unlock|bypass)\s+"
    r"(the\s+|your\s+|two|2fa|safety|confirmation|content|filter|check|account)"
    r"|(transfer|wire|move|withdraw|pay)\s+[^\n]{0,30}?"
    r"(fund|balance|money|amount|account|iban|btc|eth|wallet)"
    # exfil / secret request: [^\n] (file paths ~/.ssh contain periods); target incl. email
    r"|(send|upload|email|post|forward|exfiltrat\w*|leak)\b[^\n]{0,60}?"
    r"(to\s+(me\b|my\s+|https?://|[\w.+-]+@)|credential|token|password|api[ _-]?key|secret"
    r"|id_rsa|\.ssh|\.aws|customer\s+list)"
    r"|\$\([^)]|\|\s*(sh|bash)\b|rm\s+-rf\b"
    r"|execute\s+the\s+(trade|order|command|transaction)"
    r"|approve\s+(every|all|the|each)\b|delete\s+(all|the|their)\b"
    # RU
    r"|игнорируй\s+(предыдущие|все|что)\b|покажи\s+(свой\s+|твой\s+)?(токен|пароль|ключ|api)"
    r"|отправь\s+[^\n]{0,60}?(на\s+(сервер|http)|мне)"
    r"|переведи\s+[^\n]{0,30}?(средства|деньги|баланс)",
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

# Categories that ARE injection structure, not mere vocabulary. Prose/quote context must
# never downgrade these (red-team C3/C4): "new instructions:" / "[SYSTEM]" / "ignore
# previous" ARE the injection, not a citation of one. Only soft vocabulary (a bare
# "jailbreak" word in a paper) may be quieted. HIGH_PRIORITY (operational) is handled
# separately with a hard HIGH floor.
_DIRECTIVE_SHAPED = frozenset(
    {"system_override", "role_injection", "social_engineering", "credential_harvest"}
)


def _original_severity(hits: dict[str, int]) -> str:
    """Map the current guard's verdict onto the RFC-003 severity vocabulary."""
    if not hits:
        return _ORIGINAL_SILENT
    return "HIGH" if is_high_threat(hits) else "MEDIUM"


def has_strong_directive(text: str) -> bool:
    return bool(_STRONG_DIRECTIVE.search(text))


def provable_descriptive_context(text: str) -> bool:
    return bool(_DESCRIPTIVE_PROSE.search(text) or _FENCE.search(text) or _BLOCKQUOTE.search(text))


def _calibrate(norm_text: str, hits: dict[str, int]) -> str:
    """Pure severity computation on NORMALIZED text. See module docstring for the rule."""
    directive = has_strong_directive(norm_text)
    # A directive dominates everything: it both blocks a downgrade AND adds detection
    # (raising a missed imperative from silent to HIGH). Never downgraded by context.
    if directive:
        return "HIGH"
    original = _original_severity(hits)
    if original == _ORIGINAL_SILENT:
        # No hit and no directive -> nothing to surface.
        return _ORIGINAL_SILENT
    # HIGH-PRIORITY floor (red-team C2/C3): an operational category (data_exfil,
    # command_injection, encoding_attack) is a completed/executable signal -- prose
    # context must NEVER quiet it. Keep it HIGH regardless of descriptive markers.
    if any(c in HIGH_PRIORITY_CATEGORIES for c in hits):
        return "HIGH"
    # Directive-shaped categories (red-team C4): "new instructions:" / "[SYSTEM]" ARE the
    # injection -- keep their original severity, never quiet to INFO by prose context.
    if any(c in _DIRECTIVE_SHAPED for c in hits):
        return original
    # Only soft vocabulary remains (e.g. a bare "jailbreak" word). Downgrade ONLY on
    # provable descriptive context -- this is the sole path where context lowers volume.
    if provable_descriptive_context(norm_text):
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
    # Normalize identically to scan() (red-team C1): detect homoglyph/leet/nbsp-obfuscated
    # directives that scan() already folded, so they can't evade the directive gate.
    norm_text = _normalize(text)
    try:
        effective = _calibrate(norm_text, hits)
        context = (
            "strong_directive"
            if has_strong_directive(norm_text)
            else "descriptive_or_quoted"
            if provable_descriptive_context(norm_text)
            else "none"
        )
        error = None
    except Exception as exc:  # noqa: BLE001 - fail-safe: never lower severity on error
        effective, context, error = original, "error", type(exc).__name__

    # UNCONDITIONAL floor (red-team M1): the old guard only ran on error, dead code for the
    # real attack. A HIGH from a HIGH_PRIORITY category may never be quieted below MEDIUM by
    # ANY path (calibration bug, future edit, or an error). Applies always, not just on error.
    _ORDER = {
        "silent": 0, _ORIGINAL_SILENT: 0, "INFO": 1,
        "REQUIRES_CHECK": 2, "MEDIUM": 3, "HIGH": 4,
    }
    _is_operational = any(c in HIGH_PRIORITY_CATEGORIES for c in hits)
    if _is_operational and _ORDER.get(effective, 0) < _ORDER["MEDIUM"]:
        effective = "HIGH"
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
