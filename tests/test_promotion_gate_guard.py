"""Tests for promotion_gate_guard.py hook."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from promotion_gate_guard import (
    _check_claim_entropy,
    _check_controls,
    _check_external_reconstruction,
    _check_no_collapse,
    _check_result_summary,
    _check_verified_real,  # alias — kept for backward-compat
    _has_promote,
    _is_decision_md,
)

# ── path helpers ─────────────────────────────────────────────────────────────


class TestIsDecisionMd:
    def test_valid_path(self):
        assert _is_decision_md("experiments/20260101-test/decision.md")

    def test_nested_path(self):
        assert _is_decision_md("D:/repo/experiments/20260101-test/decision.md")

    def test_wrong_filename(self):
        assert not _is_decision_md("experiments/20260101-test/claim.md")

    def test_no_experiments_parent(self):
        assert not _is_decision_md("docs/decision.md")


class TestHasPromote:
    def test_detects_checked_promote(self):
        assert _has_promote("- [x] PROMOTE — claim holds")

    def test_ignores_unchecked(self):
        assert not _has_promote("- [ ] PROMOTE — claim holds")

    def test_case_insensitive(self):
        assert _has_promote("- [X] promote")

    def test_no_promote(self):
        assert not _has_promote("- [x] REJECT — falsified")


# ── per-condition checks ──────────────────────────────────────────────────────


class TestCheckClaimEntropy:
    def test_passes_when_entropy_zero(self, tmp_path):
        claim = tmp_path / "claim.md"
        claim.write_text(
            "## Claim Entropy\n| **Total claim_entropy** | 0 |\n",
            encoding="utf-8",
        )
        passed, detail = _check_claim_entropy(tmp_path)
        assert passed
        assert "0" in detail

    def test_fails_when_entropy_nonzero(self, tmp_path):
        claim = tmp_path / "claim.md"
        claim.write_text(
            "## Claim Entropy\n| **Total claim_entropy** | 3 |\n",
            encoding="utf-8",
        )
        passed, _ = _check_claim_entropy(tmp_path)
        assert not passed

    def test_fails_when_claim_md_missing(self, tmp_path):
        passed, detail = _check_claim_entropy(tmp_path)
        assert not passed
        assert "missing" in detail

    def test_uses_state_file_when_table_absent(self, tmp_path):
        # WHY key "entropy", not "current": claim_entropy_tracker.save_state()
        # writes {"entropy": current} -- this is the real interop contract.
        claim = tmp_path / "claim.md"
        claim.write_text("## Claim Entropy\n(no table here)\n", encoding="utf-8")
        state = tmp_path / ".claim_entropy_state.json"
        state.write_text(json.dumps({"entropy": 0}), encoding="utf-8")
        passed, detail = _check_claim_entropy(tmp_path)
        assert passed
        assert "state file" in detail

    def test_fails_via_state_file_nonzero(self, tmp_path):
        claim = tmp_path / "claim.md"
        claim.write_text("## Claim Entropy\n", encoding="utf-8")
        state = tmp_path / ".claim_entropy_state.json"
        state.write_text(json.dumps({"entropy": 2}), encoding="utf-8")
        passed, _ = _check_claim_entropy(tmp_path)
        assert not passed

    def test_regression_state_file_wrong_key_previously_always_failed(self, tmp_path):
        """Regression: the old code read state["current"], but the real
        producer (claim_entropy_tracker.py) writes state["entropy"] -- the
        wrong key always defaulted to -1 and this path never actually
        worked, silently. A state file with the real key must now pass."""
        claim = tmp_path / "claim.md"
        claim.write_text("## Claim Entropy\n", encoding="utf-8")
        state = tmp_path / ".claim_entropy_state.json"
        state.write_text(json.dumps({"entropy": 0}), encoding="utf-8")
        passed, _ = _check_claim_entropy(tmp_path)
        assert passed

    def test_hollow_zero_total_with_unresolved_components_fails(self, tmp_path):
        """Regression (HIGH): PROMOTE could pass claim_entropy=0 by editing
        only the Total row while component rows stayed unresolved."""
        claim = tmp_path / "claim.md"
        claim.write_text(
            "## Claim Entropy\n"
            "| Component | Count |\n"
            "|---|---|\n"
            "| Unresolved blockers | 3 |\n"
            "| **Total claim_entropy** | 0 |\n",
            encoding="utf-8",
        )
        passed, detail = _check_claim_entropy(tmp_path)
        assert not passed
        assert "disagrees" in detail


REAL_CONTROLS_MD = """\
## Positive Control
**Input:** known-good input
**Result:** [x] PASS

## Negative Control
**Input:** known-bad input
**Result:** [x] FAIL

## No-Collapse Tests
| Test | Result |
| Data swap | [x] PASS |
| Noise injection | [x] PASS |
| Negative control | [x] FAIL |
"""


class TestCheckControls:
    def test_passes_when_controls_actually_run(self, tmp_path):
        (tmp_path / "controls.md").write_text(REAL_CONTROLS_MD, encoding="utf-8")
        passed, _ = _check_controls(tmp_path)
        assert passed

    def test_fails_when_controls_missing(self, tmp_path):
        passed, detail = _check_controls(tmp_path)
        assert not passed
        assert "missing" in detail

    def test_fails_on_empty_placeholder_controls(self, tmp_path):
        """Regression (HIGH): a freshly-templated, unfilled controls.md
        (Result checkboxes unmarked) previously satisfied this condition
        purely by existing."""
        (tmp_path / "controls.md").write_text(
            "## Positive Control\n**Result:** [ ] PASS  [ ] FAIL\n\n"
            "## Negative Control\n**Result:** [ ] PASS  [ ] FAIL\n",
            encoding="utf-8",
        )
        passed, detail = _check_controls(tmp_path)
        assert not passed
        assert "not marked as run" in detail

    def test_fails_when_only_positive_control_run(self, tmp_path):
        (tmp_path / "controls.md").write_text(
            "## Positive Control\n**Result:** [x] PASS\n\n"
            "## Negative Control\n**Result:** [ ] PASS  [ ] FAIL\n",
            encoding="utf-8",
        )
        passed, detail = _check_controls(tmp_path)
        assert not passed
        assert "Negative Control not marked" in detail


class TestCheckNoCollapse:
    def test_passes_with_enough_tests_run(self, tmp_path):
        (tmp_path / "controls.md").write_text(REAL_CONTROLS_MD, encoding="utf-8")
        passed, _ = _check_no_collapse(tmp_path)
        assert passed

    def test_fails_without_section(self, tmp_path):
        (tmp_path / "controls.md").write_text(
            "## Controls\n| positive | PASS |\n",
            encoding="utf-8",
        )
        passed, detail = _check_no_collapse(tmp_path)
        assert not passed
        assert "No-Collapse" in detail

    def test_fails_when_controls_missing(self, tmp_path):
        passed, _ = _check_no_collapse(tmp_path)
        assert not passed

    def test_fails_on_placeholder_no_collapse_section(self, tmp_path):
        """Regression (MEDIUM): "TODO: No-Collapse Tests" previously
        satisfied this condition via a bare substring match, with zero
        tests actually run."""
        (tmp_path / "controls.md").write_text(
            "## No-Collapse Tests\nTODO: No-Collapse Tests not yet run\n",
            encoding="utf-8",
        )
        passed, detail = _check_no_collapse(tmp_path)
        assert not passed
        assert "0/3" in detail

    def test_fails_below_minimum_test_count(self, tmp_path):
        (tmp_path / "controls.md").write_text(
            "## No-Collapse Tests\n| Data swap | [x] PASS |\n",
            encoding="utf-8",
        )
        passed, detail = _check_no_collapse(tmp_path)
        assert not passed
        assert "1/3" in detail


class TestCheckResultSummary:
    def test_passes_with_result_summary(self, tmp_path):
        (tmp_path / "result_summary.md").write_text("## Results\n", encoding="utf-8")
        passed, _ = _check_result_summary(tmp_path)
        assert passed

    def test_passes_with_metrics_run_json(self, tmp_path):
        (tmp_path / "metrics").mkdir()
        (tmp_path / "metrics" / "run.json").write_text("{}", encoding="utf-8")
        passed, _ = _check_result_summary(tmp_path)
        assert passed

    def test_fails_when_neither_exists(self, tmp_path):
        passed, detail = _check_result_summary(tmp_path)
        assert not passed
        assert "missing" in detail


class TestCheckExternalReconstruction:
    """Condition 5: [VERIFIED-REAL] must appear in result_summary.md specifically."""

    def test_passes_when_marker_in_result_summary(self, tmp_path):
        (tmp_path / "result_summary.md").write_text(
            "Validated [VERIFIED-REAL] via external API.\n", encoding="utf-8"
        )
        passed, detail = _check_external_reconstruction(tmp_path)
        assert passed
        assert "result_summary" in detail

    def test_fails_when_result_summary_missing(self, tmp_path):
        passed, detail = _check_external_reconstruction(tmp_path)
        assert not passed
        assert "missing" in detail

    def test_fails_when_result_summary_has_no_marker(self, tmp_path):
        (tmp_path / "result_summary.md").write_text(
            "Results look good but no real citation.\n", encoding="utf-8"
        )
        passed, detail = _check_external_reconstruction(tmp_path)
        assert not passed
        assert "lacks [VERIFIED-REAL]" in detail

    def test_fails_when_marker_only_in_other_file(self, tmp_path):
        # [VERIFIED-REAL] in claim.md does NOT satisfy condition 5
        (tmp_path / "result_summary.md").write_text("No marker here.\n", encoding="utf-8")
        (tmp_path / "claim.md").write_text("[VERIFIED-REAL] in wrong file.\n", encoding="utf-8")
        passed, detail = _check_external_reconstruction(tmp_path)
        assert not passed
        assert "lacks [VERIFIED-REAL]" in detail

    def test_alias_matches_new_function(self, tmp_path):
        # _check_verified_real is an alias — same behaviour
        (tmp_path / "result_summary.md").write_text(
            "[VERIFIED-REAL] confirmed.\n", encoding="utf-8"
        )
        p1, _ = _check_external_reconstruction(tmp_path)
        p2, _ = _check_verified_real(tmp_path)
        assert p1 == p2

    def test_fails_when_marker_only_in_todo_line(self, tmp_path):
        """Regression (HIGH): "TODO: add [VERIFIED-REAL] later" previously
        satisfied this condition by containing the marker string, with zero
        real evidence attached."""
        (tmp_path / "result_summary.md").write_text(
            "Results look promising.\nTODO: add [VERIFIED-REAL] later\n",
            encoding="utf-8",
        )
        passed, detail = _check_external_reconstruction(tmp_path)
        assert not passed
        assert "TODO/placeholder" in detail

    def test_passes_when_real_marker_present_alongside_a_todo_line(self, tmp_path):
        """A genuine [VERIFIED-REAL] citation elsewhere in the file must still
        pass even if an unrelated TODO line also happens to be present."""
        (tmp_path / "result_summary.md").write_text(
            "TODO: add more citations later\n"
            "Confirmed [VERIFIED-REAL] via https://example.com/dataset\n",
            encoding="utf-8",
        )
        passed, _ = _check_external_reconstruction(tmp_path)
        assert passed
