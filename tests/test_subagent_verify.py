"""Tests for hooks/subagent_verify.py — Audit Verification Gate (Check 4).

WHY this file exists: subagent_verify.py previously had zero test coverage.
It enforces the same audit-verification-gate.md discipline this whole repo's
integrity rules depend on, so a bug here (letting an explicitly-unverified
finding pass as verified) silently defeats the gate it exists to enforce.
"""

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "hooks"))


class TestCountUnverifiedFindings:
    def test_no_findings_returns_zero(self):
        from subagent_verify import _count_unverified_findings

        assert _count_unverified_findings("Everything looks fine, no issues here.") == 0

    def test_finding_with_verified_tool_marker_nearby_is_not_counted(self):
        from subagent_verify import _count_unverified_findings

        text = "HIGH: SQL injection bug in query.py [VERIFIED-tool] confirmed via grep."
        assert _count_unverified_findings(text) == 0

    def test_finding_with_no_marker_is_counted_unverified(self):
        from subagent_verify import _count_unverified_findings

        # WHY findings are on separate lines, >120 chars apart: _HIGH_MEDIUM_PATTERN's
        # greedy .{0,120} can otherwise span from one finding's keyword all the way to
        # a second finding's keyword within the same window, merging two separate
        # findings into a single match (a distinct, pre-existing regex-greediness
        # issue, out of scope for this fix).
        text = (
            "HIGH: SQL injection bug in query.py, completely unverified so far.\n\n"
            "Also worth flagging separately as its own paragraph of context: "
            "MEDIUM: missing null check in parser.py, a real risk with no evidence."
        )
        assert _count_unverified_findings(text) == 2

    def test_hypothesis_marker_does_not_count_as_verification(self):
        """Regression (HIGH): [HYPOTHESIS] explicitly means "not yet
        tool-confirmed" (audit-verification-gate.md) -- the opposite of
        verification. It previously sat inside _VERIFIED_TOOL_PATTERN, so a
        HIGH/MEDIUM finding marked [HYPOTHESIS] satisfied its own nearby-
        verification check and silently passed the gate as if verified."""
        from subagent_verify import _count_unverified_findings

        text = "HIGH: SQL injection bug in query.py [HYPOTHESIS] — not yet confirmed."
        assert _count_unverified_findings(text) == 1

    def test_dismissed_marker_excludes_finding_from_count(self):
        """[DISMISSED] means already checked and found false -- it should not
        count as an open unverified finding, but must not count as
        verification evidence for OTHER nearby findings either."""
        from subagent_verify import _count_unverified_findings

        text = "HIGH: false alarm about query.py [DISMISSED] after review."
        assert _count_unverified_findings(text) == 0

    def test_dismissed_marker_does_not_verify_a_different_nearby_finding(self):
        # WHY >500 chars of filler: _count_unverified_findings intentionally
        # treats markers within 500 chars as "same paragraph" (documented,
        # pre-existing design, not a bug) -- this test checks a finding
        # genuinely OUTSIDE that window is still counted independently.
        from subagent_verify import _count_unverified_findings

        filler = "Unrelated context filler text. " * 20  # ~640 chars
        text = (
            f"HIGH: false alarm about query.py [DISMISSED] after review.\n\n{filler}\n\n"
            "MEDIUM: real issue in auth.py with no evidence at all so far."
        )
        assert _count_unverified_findings(text) == 1

    def test_mixed_verified_and_unverified_findings(self):
        from subagent_verify import _count_unverified_findings

        filler = "Unrelated context filler text. " * 20  # ~640 chars
        text = (
            f"HIGH: bug in a.py [VERIFIED-pytest] confirmed via a real test run.\n\n{filler}\n\n"
            "MEDIUM: risk in b.py with no verification at all so far."
        )
        assert _count_unverified_findings(text) == 1


class TestMain:
    def _run(self, monkeypatch, payload: dict) -> str:
        from subagent_verify import main

        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            main()
        return buf.getvalue()

    def test_empty_response_flagged(self, monkeypatch):
        out = self._run(
            monkeypatch,
            {"agent_type": "explorer", "agent_id": "1", "last_assistant_message": ""},
        )
        result = json.loads(out)
        assert "empty response" in result["message"]

    def test_short_response_flagged(self, monkeypatch):
        out = self._run(
            monkeypatch,
            {"agent_type": "explorer", "agent_id": "1", "last_assistant_message": "ok done"},
        )
        result = json.loads(out)
        assert "too short" in result["message"]

    def test_apology_marker_flagged(self, monkeypatch):
        long_apology = "I apologize, but " + "I was not able to complete this task. " * 3
        out = self._run(
            monkeypatch,
            {"agent_type": "explorer", "agent_id": "1", "last_assistant_message": long_apology},
        )
        result = json.loads(out)
        assert "apology" in result["message"]

    def test_good_response_produces_no_output(self, monkeypatch):
        good_response = (
            "Analysis complete. Read all 12 files in hooks/ and confirmed the "
            "registration list matches settings.json exactly. No issues found."
        )
        out = self._run(
            monkeypatch,
            {"agent_type": "explorer", "agent_id": "1", "last_assistant_message": good_response},
        )
        assert out == ""

    def test_two_unverified_findings_trigger_gate_warning(self, monkeypatch):
        response = (
            "HIGH: SQL injection risk in query.py, no check at all so far.\n\n"
            "As a separate, independently reported finding elsewhere in the review: "
            "MEDIUM: missing null guard in parser.py, a real risk with no verification."
        )
        out = self._run(
            monkeypatch,
            {"agent_type": "explorer", "agent_id": "1", "last_assistant_message": response},
        )
        result = json.loads(out)
        assert "VERIFIED-tool" in result["message"]

    def test_hypothesis_marked_findings_still_trigger_gate(self, monkeypatch):
        """Integration-level regression for the [HYPOTHESIS] fix: two HIGH
        findings both marked [HYPOTHESIS] (i.e. explicitly NOT verified) must
        still trigger the gate warning end-to-end, not be silently accepted."""
        response = (
            "HIGH: SQL injection risk in query.py [HYPOTHESIS] pending review.\n\n"
            "As a fully separate finding reported later in the same review: "
            "HIGH: missing auth check in api.py [HYPOTHESIS] pending review."
        )
        out = self._run(
            monkeypatch,
            {"agent_type": "explorer", "agent_id": "1", "last_assistant_message": response},
        )
        result = json.loads(out)
        assert "VERIFIED-tool" in result["message"]
