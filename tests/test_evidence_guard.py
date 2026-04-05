"""Unit tests for hooks/evidence_guard.py — Evidence Policy enforcement.

WHY: evidence_guard is the only deterministic enforcement of Evidence Policy.
If it's broken, Claude can omit [VERIFIED] markers with no consequence.
"""

import io
import json
from unittest.mock import patch

from evidence_guard import (
    MIN_RESPONSE_LENGTH,
    count_factual_claims,
    has_evidence_markers,
    main,
)

# === has_evidence_markers ===


class TestHasEvidenceMarkers:
    def test_verified_marker(self):
        assert has_evidence_markers("[VERIFIED] Python 3.12 is used") is True

    def test_inferred_marker(self):
        assert has_evidence_markers("[INFERRED] defaults to 5") is True

    def test_unknown_marker(self):
        assert has_evidence_markers("This is [UNKNOWN]") is True

    def test_docs_marker(self):
        assert has_evidence_markers("[DOCS] see the docs") is True

    def test_code_marker(self):
        assert has_evidence_markers("[CODE] from source") is True

    def test_weak_marker(self):
        assert has_evidence_markers("[WEAK] indirect evidence") is True

    def test_conflicting_marker(self):
        assert has_evidence_markers("[CONFLICTING] sources differ") is True

    def test_verified_high_marker(self):
        assert has_evidence_markers("[VERIFIED-HIGH] confirmed by 2 tools") is True

    def test_no_markers(self):
        assert has_evidence_markers("Python version 3.11 is required") is False

    def test_lowercase_not_matched(self):
        # WHY: markers are uppercase-only by Evidence Policy spec
        assert has_evidence_markers("[verified] Python 3.11") is False

    def test_partial_match_not_counted(self):
        assert has_evidence_markers("VERIFIED without brackets") is False


# === count_factual_claims ===


class TestCountFactualClaims:
    def test_version_pattern(self):
        assert count_factual_claims("version 3.12 is stable") >= 1

    def test_python_version_pattern(self):
        assert count_factual_claims("Python 3.11 is required") >= 1

    def test_percentage_pattern(self):
        assert count_factual_claims("50% of coverage is needed") >= 1

    def test_always_keyword(self):
        assert count_factual_claims("you must always do X") >= 1

    def test_never_keyword(self):
        assert count_factual_claims("you must never do Y") >= 1

    def test_best_practice(self):
        assert count_factual_claims("best practice is to use X") >= 1

    def test_default_pattern(self):
        assert count_factual_claims("defaults to 100") >= 1

    def test_up_to_pattern(self):
        assert count_factual_claims("supports up to 1000 items") >= 1

    def test_no_factual_claims(self):
        assert count_factual_claims("here is the code you asked for") == 0

    def test_multiple_claims_accumulate(self):
        text = (
            "Python 3.11 is required. You must always use version 3.11. Coverage defaults to 80%."
        )
        assert count_factual_claims(text) >= 3


# === main() ===


class TestMain:
    LONG_UNMARKED = (
        "Python version 3.11 is required by this project. "
        "You must always use type hints. "
        "The best practice is to run ruff before committing. "
        "Coverage defaults to 80 percent of business logic. "
        "This is a sufficiently long response to trigger the guard check."
    )

    def _run_main(self, monkeypatch, data: dict) -> str:
        """Run main() with given hook data, return stdout."""
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            try:
                main()
            except SystemExit:
                pass
        return buf.getvalue()

    def _make_data(self, response: str) -> dict:
        return {"tool_response": {"stdout": response}}

    def test_short_response_skipped(self, monkeypatch, capsys):
        data = self._make_data("Short response.")
        out = self._run_main(monkeypatch, data)
        assert out == ""

    def test_few_claims_skipped(self, monkeypatch):
        # Long but only 1 factual claim → skip
        text = "A" * MIN_RESPONSE_LENGTH + " version 3.11 is used."
        data = self._make_data(text)
        out = self._run_main(monkeypatch, data)
        assert out == ""

    def test_already_marked_skipped(self, monkeypatch):
        text = (
            "[VERIFIED] Python 3.11 is required. "
            "You must always use type hints. "
            "Best practice defaults to running ruff. " * 5
        )
        data = self._make_data(text)
        out = self._run_main(monkeypatch, data)
        assert out == ""

    def test_unmarked_long_response_emits_nudge(self, monkeypatch):
        data = self._make_data(self.LONG_UNMARKED)
        out = self._run_main(monkeypatch, data)
        assert out != ""
        parsed = json.loads(out.strip())
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "evidence-guard" in ctx
        assert "Evidence Policy" in ctx

    def test_nudge_contains_claim_count(self, monkeypatch):
        data = self._make_data(self.LONG_UNMARKED)
        out = self._run_main(monkeypatch, data)
        parsed = json.loads(out.strip())
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        # WHY: nudge should tell Claude how many claims were found
        import re

        assert re.search(r"\d+", ctx), "Nudge should contain claim count"

    def test_empty_data_no_crash(self, monkeypatch):
        out = self._run_main(monkeypatch, {})
        assert out == ""

    def test_string_tool_response(self, monkeypatch):
        # WHY: extract_tool_response handles string format too
        long_text = self.LONG_UNMARKED
        data = {"tool_response": long_text}
        # Should not raise
        self._run_main(monkeypatch, data)
