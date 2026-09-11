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
    """verdict_for() returns exactly ONE label (fixed 2026-09-12, skeptic-found:
    an earlier list-returning version could emit both false_positive AND
    false_negative for one case, and the caller incremented both counters --
    for any case hitting that shape, sum(counts.values()) exceeded total.
    See _BADNESS's own module-level comment for the full incident."""

    def test_correct_when_sets_match_nonempty(self):
        assert verdict_for({"SECURITY"}, {"SECURITY"}) == "correct"

    def test_abstain_when_both_empty(self):
        assert verdict_for(set(), set()) == "abstain"

    def test_false_positive_when_actual_has_extra(self):
        assert verdict_for(set(), {"SECURITY"}) == "false_positive"

    def test_false_negative_when_expected_has_extra(self):
        assert verdict_for({"SECURITY"}, set()) == "false_negative"

    def test_mixed_when_both_a_spurious_and_a_missing_tier(self):
        """The reproducer skeptic used: expected={SECURITY}, actual={DESTRUCTIVE}
        -- disjoint non-empty sets, both a false positive AND a false negative
        at once. Must resolve to exactly one label, not two."""
        assert verdict_for({"SECURITY"}, {"DESTRUCTIVE"}) == "mixed"


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
        assert "reg-same-paragraph-synonym-repeat" in improved_ids

    def test_baseline_has_false_positives_on_quoted_incidents(self, result):
        by_id = {c["id"]: c for c in result["per_case"]}
        assert by_id["reg-quoted-doc-credential-ru-tail"]["baseline_verdict"] == "false_positive"
        assert by_id["reg-quoted-doc-research-words"]["baseline_verdict"] == "false_positive"
        assert by_id["reg-same-paragraph-synonym-repeat"]["baseline_verdict"] == "false_positive"

    def test_candidate_abstains_on_quoted_incidents(self, result):
        by_id = {c["id"]: c for c in result["per_case"]}
        assert by_id["reg-quoted-doc-credential-ru-tail"]["candidate_verdict"] == "abstain"
        assert by_id["reg-quoted-doc-research-words"]["candidate_verdict"] == "abstain"
        assert by_id["reg-same-paragraph-synonym-repeat"]["candidate_verdict"] == "abstain"

    def test_genuine_ask_after_long_paste_still_fires_for_both(self, result):
        """Regression guard: a real live SECURITY ask trailing a long paste must
        never be suppressed, for either classifier variant."""
        by_id = {c["id"]: c for c in result["per_case"]}
        case = by_id["tp-security-after-long-paste"]
        assert "SECURITY" in case["baseline_tiers"]
        assert "SECURITY" in case["candidate_tiers"]

    def test_live_ask_mid_prompt_with_trailing_content_fires_for_candidate(self, result):
        """Skeptic-found regression pin (2026-09-12): a live directive in the
        MIDDLE of a long prompt, with more pasted content trailing it, must
        still fire for the candidate -- the first suppression fix only
        re-checked the last 400 characters and silently missed this shape."""
        by_id = {c["id"]: c for c in result["per_case"]}
        case = by_id["reg-live-ask-mid-prompt-followed-by-more-content"]
        assert "RESEARCH" in case["baseline_tiers"]
        assert "RESEARCH" in case["candidate_tiers"]
        assert case["candidate_verdict"] == "correct"

    def test_no_false_negatives_for_candidate(self, result):
        assert result["counts"]["candidate"]["false_negative"] == 0

    def test_counts_sum_to_total_for_both_variants(self, result):
        """Regression pin for the double-counting bug (skeptic-found,
        2026-09-12): each variant's per-label counts must sum to exactly the
        total number of cases -- verdict_for() now returns one label, never
        two, so nothing can be double- or under-counted."""
        assert sum(result["counts"]["baseline"].values()) == result["total"]
        assert sum(result["counts"]["candidate"].values()) == result["total"]

    def test_no_lateral_changes(self, result):
        """No case should have both baseline and candidate wrong in
        different, equally-bad ways -- if this ever fires, it means a
        candidate change made some case wrong in a NEW way without being a
        clean regression or improvement, which needs human review."""
        assert result["lateral_changes"] == [], (
            f"lateral changes found: {[r['id'] for r in result['lateral_changes']]}"
        )


class TestBadnessRankingCapturesPartialTransitions:
    """Regression pin for the dropped-transition bug (skeptic-found,
    2026-09-12): a transition between two DIFFERENT wrong verdicts must be
    visible somewhere (regressions, improvements, or lateral_changes), never
    silently absent from all three."""

    def _fake_case(self, expected, baseline_actual, candidate_actual):
        return (
            {
                "id": "synthetic",
                "prompt": "irrelevant",
                "expected_tiers": list(expected),
            },
            baseline_actual,
            candidate_actual,
        )

    def test_mixed_to_false_positive_is_an_improvement(self, monkeypatch):
        """baseline gets BOTH a spurious and a missing tier (mixed, badness 2);
        candidate keeps only the spurious tier (false_positive, badness 1) --
        strictly better, must land in improvements."""
        import routing_replay as mod

        case, b_actual, c_actual = self._fake_case(
            {"SECURITY"}, {"DESTRUCTIVE"}, {"DESTRUCTIVE", "SECURITY"}
        )
        # candidate now ALSO fires SECURITY (the expected tier) alongside the
        # spurious DESTRUCTIVE -- so candidate={DESTRUCTIVE, SECURITY} against
        # expected={SECURITY}: false_positive only (DESTRUCTIVE is spurious,
        # nothing missing). baseline={DESTRUCTIVE} against expected={SECURITY}:
        # mixed (DESTRUCTIVE spurious AND SECURITY missing).
        monkeypatch.setattr(mod, "classify_baseline", lambda p: list(b_actual))
        monkeypatch.setattr(mod, "classify_candidate", lambda p: list(c_actual))
        result = mod.run_replay([case])
        assert result["per_case"][0]["baseline_verdict"] == "mixed"
        assert result["per_case"][0]["candidate_verdict"] == "false_positive"
        assert len(result["improvements"]) == 1
        assert result["regressions"] == []
        assert result["lateral_changes"] == []

    def test_false_positive_to_false_negative_is_lateral(self, monkeypatch):
        """Same badness rank (both 1), different verdict -- must appear in
        lateral_changes, not silently vanish from every list."""
        import routing_replay as mod

        case, _, _ = self._fake_case({"SECURITY"}, set(), set())
        monkeypatch.setattr(mod, "classify_baseline", lambda p: ["DESTRUCTIVE", "SECURITY"])
        monkeypatch.setattr(mod, "classify_candidate", lambda p: [])
        result = mod.run_replay([case])
        assert result["per_case"][0]["baseline_verdict"] == "false_positive"
        assert result["per_case"][0]["candidate_verdict"] == "false_negative"
        assert result["regressions"] == []
        assert result["improvements"] == []
        assert len(result["lateral_changes"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
