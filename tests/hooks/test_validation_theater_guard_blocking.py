#!/usr/bin/env python3
"""Tests for validation_theater_guard.py blocking mode.

WHY: H2 from Sprint 1 — add hard blocking for critical validation theater.
Perfect score + synthetic data simultaneously = highest risk case.
"""

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

# Add hooks to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hooks"))

from validation_theater_guard import (
    check_unsubstantiated_production_claim,
    check_write_for_synthetic,
    should_block_validation,
)


class TestBlockingLogic:
    """Test blocking decision logic."""

    def test_block_perfect_score_plus_synthetic(self):
        """Block when perfect score AND synthetic data in same output."""
        # WHY: ArgosArb incident — F1=1.000 on synthetic data
        outputs = [
            "F1=1.000 [VERIFIED-SYNTHETIC] on create_synthetic_dataset()",
            "All 10 tests passed. Using mock_data for validation.",
            "precision=1.000, recall=1.000 on SYNTHETIC_CASES",
            "100% success rate (synthetic test data)",
        ]
        for output in outputs:
            assert should_block_validation(output), f"Should block: {output}"

    def test_no_block_perfect_score_real_data(self):
        """Don't block perfect score if marked [VERIFIED-REAL]."""
        outputs = [
            "F1=1.000 [VERIFIED-REAL] on production logs from S3",
            "All tests passed using real customer data",
            "100% accuracy on external benchmark dataset (URL: https://...)",
        ]
        for output in outputs:
            assert not should_block_validation(output), f"Should NOT block: {output}"

    def test_no_block_synthetic_without_perfect_score(self):
        """Don't block synthetic data if score is realistic."""
        outputs = [
            "F1=0.87 [VERIFIED-SYNTHETIC] for unit test",
            "75% passed on mock_data (expected for edge cases)",
            "create_synthetic_dataset() → F1=0.64",
        ]
        for output in outputs:
            assert not should_block_validation(output), f"Should NOT block: {output}"

    def test_no_block_imperfect_score(self):
        """Don't block realistic scores even without [VERIFIED-REAL]."""
        outputs = [
            "F1=0.95 on test set",
            "98% of cases passed",
            "precision=0.987, recall=0.912",
        ]
        for output in outputs:
            assert not should_block_validation(output), f"Should NOT block: {output}"

    def test_bare_url_with_no_dataset_context_does_not_bypass_block(self):
        """Regression (HIGH): any http(s)/s3/gs URL anywhere in the output
        previously counted as "real data" and defeated the block, even when
        the URL had nothing to do with the data source (e.g. an unrelated
        doc link sitting next to synthetic mock data)."""
        output = (
            "F1=1.000 on mock_data. See https://example.com/docs for API reference. "
            "SYNTHETIC_CASES used throughout."
        )
        assert should_block_validation(output), (
            "An unrelated URL must not bypass the block when the data is synthetic"
        )

    def test_url_with_dataset_context_still_counts_as_real_data(self):
        """A URL that IS actually cited as the data source must still count,
        so the narrowed pattern doesn't over-correct into false blocks."""
        output = "F1=1.000 on mock_data downloaded dataset from https://example.com/real-corpus"
        assert not should_block_validation(output), (
            "A URL explicitly tied to a dataset citation should still count as real data"
        )

    def test_bare_verified_real_tag_cannot_launder_a_synthetic_claim(self):
        """Regression (deeper look at a stale external audit's F-02 finding,
        2026-07-10): a bare [VERIFIED-REAL] tag co-occurring with a synthetic
        marker in the SAME output previously short-circuited the block --
        has_real_data was checked before any contradiction check ran, so
        the self-contradictory claim slipped through as "real data"."""
        outputs = [
            "F1=1.000 on mock_data [VERIFIED-REAL]",
            "[VERIFIED-REAL] 100% success rate using create_synthetic_dataset()",
            "precision=1.000 SYNTHETIC_CASES used, but [VERIFIED-REAL] confirmed",
        ]
        for output in outputs:
            assert should_block_validation(output), (
                f"A synthetic marker + a bare [VERIFIED-REAL] tag in the same "
                f"output is self-contradictory and must still block: {output}"
            )

    def test_prose_real_data_marker_is_unaffected_by_the_contradiction_check(self):
        """The narrower fix targets ONLY the structured [VERIFIED-REAL] tag --
        prose real-data markers (production logs, real customer data) still
        behave exactly as before even when a synthetic word appears nearby,
        since those aren't the deliberate evidence-taxonomy claim the
        contradiction check is guarding."""
        output = "F1=1.000 on production logs, mock_data variable name is a leftover from testing"
        assert not should_block_validation(output), (
            "A prose real-data marker (not the [VERIFIED-REAL] tag) should not "
            "trigger the new contradiction check"
        )


class TestWriteThenBashCorrelation:
    """Regression (HIGH): a validator flagged synthetic on Write, then run via
    a SEPARATE Bash call that prints a perfect score without ever repeating a
    "synthetic" keyword in its own output, previously sailed through
    unblocked -- should_block_validation() had no memory of the earlier Write."""

    def test_recent_synthetic_write_makes_bash_perfect_score_blockable(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)  # isolate HookState's .claude/state/ file

        write_input = {
            "file_path": "validator_new.py",
            "content": "data = create_synthetic_dataset()\n",
        }
        warning = check_write_for_synthetic(write_input)
        assert warning is not None  # sanity: the Write itself was flagged

        # This Bash output has a perfect score and NO real-data marker, but
        # also no literal "synthetic"/"mock"/"fake" keyword of its own.
        bash_output = "Validation run complete: F1=1.000, all 10 cases passed."
        assert should_block_validation(bash_output)

    def test_unrelated_bash_output_without_any_recent_write_is_not_blocked(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        # No prior synthetic Write recorded in this isolated cwd.
        bash_output = "Validation run complete: F1=1.000, all 10 cases passed."
        assert not should_block_validation(bash_output)


class TestUnsubstantiatedProductionClaim:
    """Regression (user-confirmed decision, external security audit
    2026-07-07): a paraphrased perfect-score claim ("model showed ideal
    quality on generated samples") evades every PERFECT_SCORE_PATTERNS regex.
    Rather than chase infinite paraphrases, production-confidence language
    now requires a POSITIVE evidence marker -- absence of a synthetic/fake
    confession is not evidence a claim is real."""

    def test_verified_without_marker_warns(self):
        warning = check_unsubstantiated_production_claim(
            "This implementation is verified and works reliably in all cases."
        )
        assert warning is not None
        assert "evidence marker" in warning

    def test_production_ready_without_marker_warns(self):
        warning = check_unsubstantiated_production_claim("The pipeline is now production-ready.")
        assert warning is not None

    def test_validated_with_verified_real_marker_silent(self):
        """The exact positive-evidence case: claim language + a real
        evidence marker in the same output → no warning."""
        warning = check_unsubstantiated_production_claim(
            "Validated against production logs. [VERIFIED-REAL] source: https://example.com/dataset"
        )
        assert warning is None

    def test_validated_with_hypothesis_marker_silent(self):
        """[HYPOTHESIS] is also a recognized evidence-level marker -- an
        explicitly-labeled hypothesis is not an unsubstantiated claim, it's
        an honestly-scoped one."""
        warning = check_unsubstantiated_production_claim(
            "This approach is validated for the common case. [HYPOTHESIS] edge cases untested."
        )
        assert warning is None

    def test_no_claim_language_silent(self):
        warning = check_unsubstantiated_production_claim("F1=0.87 on a held-out test split.")
        assert warning is None

    def test_marker_far_from_claim_does_not_substantiate_it(self):
        """F-03 (external audit 2026-07-15): the exact exploit found -- a
        [HYPOTHESIS] marker attached to an unrelated, distant claim
        previously satisfied the whole-output marker check and let an
        unsubstantiated "production-ready" claim through unflagged."""
        output = (
            "This service is production-ready and safe to deploy. "
            + ("filler " * 60)  # push the marker well outside the proximity window
            + "[HYPOTHESIS] unrelated future work on a different subsystem."
        )
        warning = check_unsubstantiated_production_claim(output)
        assert warning is not None
        assert "nearby evidence marker" in warning

    def test_marker_within_proximity_window_still_substantiates(self):
        """Same claim, but the marker is close enough to plausibly belong to
        it -- must stay silent (no regression on the legitimate case)."""
        output = "This service is production-ready. [VERIFIED-REAL] see deploy logs."
        assert check_unsubstantiated_production_claim(output) is None

    def test_paraphrased_perfect_score_with_no_evidence_still_flagged(self):
        """The whole point of this check: language that evades every
        PERFECT_SCORE_PATTERNS regex (no "F1=", no "100%", no "all N
        passed") still gets caught here because it uses claim language
        ("verified") without any evidence marker."""
        output = "Model showed ideal quality on generated samples and is verified for release."
        assert not should_block_validation(output)  # doesn't match the OLD regex-only check
        assert check_unsubstantiated_production_claim(output) is not None  # NEW check catches it


class TestBlockingIntegration:
    """Test hook integration with blocking."""

    def test_hook_blocks_critical_case(self, monkeypatch):
        """Hook should exit(1) on critical validation theater."""
        stdin_data = {
            "tool_name": "Bash",
            "tool_response": {"output": "Validation complete: F1=1.000 on synthetic_cases"},
            "session_id": "test",
        }
        monkeypatch.setattr("sys.stdin", StringIO(json.dumps(stdin_data)))

        from validation_theater_guard import main

        # WHY: sys.exit(1) should raise SystemExit with code 1
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1, "Should exit with code 1 (block)"

    def test_hook_warns_non_critical_case(self, monkeypatch, capsys):
        """Hook should warn (not block) on perfect score alone."""
        stdin_data = {
            "tool_name": "Bash",
            "tool_response": {
                "output": "F1=1.000 on test dataset (source not specified, length >50 chars to trigger warning)"
            },
            "session_id": "test",
        }
        monkeypatch.setattr("sys.stdin", StringIO(json.dumps(stdin_data)))

        from validation_theater_guard import main

        # Hook should complete normally (no blocking exit(1))
        # May or may not call sys.exit(0) — that's implementation detail
        try:
            main()
        except SystemExit as e:
            # If exit called, should be 0 (not blocking)
            assert e.code == 0 or e.code is None, f"Should not block, got exit({e.code})"

        captured = capsys.readouterr()
        assert "Perfect score" in captured.out, "Should warn about perfect score"

    def test_hook_silent_on_real_data(self, monkeypatch, capsys):
        """Hook should be silent when [VERIFIED-REAL] present."""
        stdin_data = {
            "tool_name": "Bash",
            "tool_response": {"output": "F1=0.87 [VERIFIED-REAL] on production dataset"},
            "session_id": "test",
        }
        monkeypatch.setattr("sys.stdin", StringIO(json.dumps(stdin_data)))

        from validation_theater_guard import main

        # Hook should complete normally (may or may not exit)
        try:
            main()
        except SystemExit as e:
            # If exit called, should be 0
            assert e.code == 0 or e.code is None

        captured = capsys.readouterr()
        assert captured.out == "" or "validation-theater" not in captured.out.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
