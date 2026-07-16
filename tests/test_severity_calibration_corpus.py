#!/usr/bin/env python3
"""Well-formedness + safety-invariant gate for the RFC-003 severity-calibration corpus.

WHY (RFC-003 step 2): tests/corpus/prompt_injection/severity_calibration.jsonl is the
differential corpus the shadow-mode severity classifier will be measured against. This
gate does NOT run any classifier (there is none yet — step 3, red-teamed at step 4). It
guarantees the corpus encodes RFC-003's LOAD-BEARING safety rule, so the future classifier
is measured against a substrate that can't quietly permit an unsafe downgrade.

THE invariant this file exists to hold: a row carrying a strong directive
(has_strong_directive=true) must NEVER target INFO. A descriptive/quoted frame may lower a
signal's volume, but not when it wraps a real instruction to the agent — that was the exact
class the RFC-002 red-team weaponised. Encoding it here means the corpus itself refuses to
label an unsafe downgrade as correct.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
CORPUS = ROOT / "tests" / "corpus" / "prompt_injection" / "severity_calibration.jsonl"

CLASSES = {"malicious", "benign_security_research", "ambiguous"}
SEVERITIES = {"HIGH", "MEDIUM", "INFO", "REQUIRES_CHECK"}
SOURCE_TYPES = {
    "security_paper", "package_docs", "search_snippet", "mcp_response",
    "corpus_fixture", "unknown_web", "github_issue", "paper_abstract",
}
DISPLAY_CONTEXTS = {
    "prose", "fenced_code", "blockquote", "search_snippet",
    "paper_abstract", "corpus_fixture",
}


def _rows():
    return [json.loads(ln) for ln in CORPUS.read_text(encoding="utf-8").splitlines() if ln.strip()]


class TestSeverityCorpusWellFormed:
    def test_fields_valid(self):
        for r in _rows():
            assert r["text"].strip()
            assert r["class"] in CLASSES, f"bad class: {r.get('class')}"
            assert r["source_type"] in SOURCE_TYPES, f"bad source_type: {r.get('source_type')}"
            assert r["display_context"] in DISPLAY_CONTEXTS, f"bad display_context: {r.get('display_context')}"
            assert isinstance(r["has_strong_directive"], bool)
            assert r["target_effective_severity"] in SEVERITIES
            assert r.get("note"), "every row needs a rationale note"

    def test_covers_the_critical_cells(self):
        rows = _rows()
        classes = {r["class"] for r in rows}
        assert classes == CLASSES, f"missing class coverage: {CLASSES - classes}"
        # The AND-condition cell MUST be present: a descriptive/quoted frame that still
        # carries a strong directive -> stays HIGH. Without it the corpus can't test the
        # exact hole the red-team found.
        and_cond = [
            r for r in rows
            if r["display_context"] in ("fenced_code", "blockquote")
            and r["has_strong_directive"]
            and r["target_effective_severity"] == "HIGH"
        ]
        assert and_cond, "corpus must contain a framed-but-directive row targeting HIGH"
        # Bilingual coverage (RU injection present).
        assert any("Игнорируй" in r["text"] or "покажи" in r["text"] for r in rows), "no RU row"


class TestSeveritySafetyInvariant:
    """The one rule the whole approach rests on."""

    def test_a_strong_directive_never_targets_info(self):
        offenders = [
            r["text"][:60]
            for r in _rows()
            if r["has_strong_directive"] and r["target_effective_severity"] == "INFO"
        ]
        assert not offenders, (
            "A row with a strong directive is labelled to downgrade to INFO -- that is the "
            "exact unsafe suppression RFC-002's red-team found. A directive keeps HIGH/MEDIUM "
            f"even inside a descriptive frame: {offenders}"
        )

    def test_class_and_target_are_consistent(self):
        bad = []
        for r in _rows():
            c, sev = r["class"], r["target_effective_severity"]
            if c == "malicious" and sev not in ("HIGH", "MEDIUM"):
                bad.append(f"malicious row targets {sev} (must be HIGH/MEDIUM): {r['text'][:40]}")
            if c == "benign_security_research" and sev not in ("INFO", "REQUIRES_CHECK"):
                bad.append(f"benign-research row targets {sev} (must be INFO/REQUIRES_CHECK): {r['text'][:40]}")
        assert not bad, "class/target inconsistencies:\n  " + "\n  ".join(bad)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
