"""Tests for scripts/routing_replay.py — the routing-floor trace replay harness
(P0b of the 2026-09-12 routing-telemetry work).

Covers the harness mechanics (verdict classification, case loading, aggregate
counting) plus a regression pin on the DEFAULT case set: the two real
quoted-document incidents this session hit must show BASELINE=false_positive,
CANDIDATE=abstain, and zero regressions overall. If that pin ever breaks, it
means either the suppression heuristic or the case fixtures themselves
regressed — worth knowing either way.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from routing_replay import (  # noqa: E402
    DEFAULT_CASES,
    classify_baseline,
    classify_candidate,
    load_cases,
    run_replay,
    verdict_for,
)


class TestVerdictFor:
    def test_correct_when_sets_match_nonempty(self):
        assert verdict_for({"SECURITY"}, {"SECURITY"}) == ["correct"]

    def test_abstain_when_both_empty(self):
        assert verdict_for(set(), set()) == ["abstain"]

    def test_false_positive_when_actual_has_extra(self):
        assert verdict_for(set(), {"SECURITY"}) == ["false_positive"]

    def test_false_negative_when_expected_has_extra(self):
        assert verdict_for({"SECURITY"}, set()) == ["false_negative"]

    def test_mixed_reports_both_labels(self):
        labels = verdict_for({"SECURITY"}, {"RESEARCH"})
        assert set(labels) == {"false_positive", "false_negative"}


class TestClassifyBaseline:
    def test_fires_on_raw_regex_match_regardless_of_context(self):
        """BASELINE has no suppression -- it must fire even inside an obviously
        pasted/quoted document, which is exactly what makes it useful as the
        'before' comparison point for the candidate's suppression logic."""
        text = ("# doc\n\n" * 5) + "discussing credential handling at length " * 40
        assert "SECURITY" in classify_baseline(text)

    def test_benign_text_fires_nothing(self):
        assert classify_baseline("rename this variable to foo") == []


class TestClassifyCandidate:
    def test_matches_live_hook_for_a_plain_prompt(self):
        assert classify_candidate("add oauth token refresh to the auth flow") == ["SECURITY"]

    def test_no_signal_on_benign_prompt(self):
        assert classify_candidate("rename this variable to foo") == []


class TestLoadCases:
    def test_loads_default_case_file(self):
        cases = load_cases(DEFAULT_CASES)
        assert len(cases) >= 15
        for case in cases:
            assert "id" in case
            assert "prompt" in case
            assert "expected_tiers" in case

    def test_rejects_malformed_json(self, tmp_path):
        bad = tmp_path / "bad.jsonl"
        bad.write_text('{"id": "x", "prompt": "y", "expected_tiers": []}\nnot json\n')
        with pytest.raises(ValueError, match="malformed JSON"):
            load_cases(bad)

    def test_skips_blank_lines(self, tmp_path):
        f = tmp_path / "cases.jsonl"
        f.write_text('{"id": "a", "prompt": "x", "expected_tiers": []}\n\n\n')
        cases = load_cases(f)
        assert len(cases) == 1


class TestRunReplayOnDefaultCaseSet:
    """Regression pin: the default case set's known incidents must resolve the
    way this session verified them to, and the candidate must introduce zero
    regressions against baseline."""

    @pytest.fixture(scope="class")
    def result(self):
        return run_replay(load_cases(DEFAULT_CASES))

    def test_no_regressions(self, result):
        assert result["regressions"] == [], (
            f"candidate regressed vs baseline on: {[r['id'] for r in result['regressions']]}"
        )

    def test_quoted_document_incidents_are_improvements(self, result):
        improved_ids = {r["id"] for r in result["improvements"]}
        assert "reg-quoted-doc-credential-ru-tail" in improved_ids
        assert "reg-quoted-doc-research-words" in improved_ids

    def test_baseline_has_false_positives_on_quoted_incidents(self, result):
        by_id = {c["id"]: c for c in result["per_case"]}
        assert "false_positive" in by_id["reg-quoted-doc-credential-ru-tail"]["baseline_verdict"]
        assert "false_positive" in by_id["reg-quoted-doc-research-words"]["baseline_verdict"]

    def test_candidate_abstains_on_quoted_incidents(self, result):
        by_id = {c["id"]: c for c in result["per_case"]}
        assert by_id["reg-quoted-doc-credential-ru-tail"]["candidate_verdict"] == ["abstain"]
        assert by_id["reg-quoted-doc-research-words"]["candidate_verdict"] == ["abstain"]

    def test_genuine_ask_after_long_paste_still_fires_for_both(self, result):
        """Regression guard: a real live SECURITY ask trailing a long paste must
        never be suppressed, for either classifier variant."""
        by_id = {c["id"]: c for c in result["per_case"]}
        case = by_id["tp-security-after-long-paste"]
        assert "SECURITY" in case["baseline_tiers"]
        assert "SECURITY" in case["candidate_tiers"]

    def test_no_false_negatives_for_candidate(self, result):
        assert result["counts"]["candidate"]["false_negative"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
