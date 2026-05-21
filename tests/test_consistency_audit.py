"""Tests for scripts/consistency_audit.py — FL experiment consistency checker."""

import json
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

from consistency_audit import (
    SEVERITY_ERROR,
    SEVERITY_OK,
    SEVERITY_WARN,
    _count_checkboxes,
    _extract_checked_verdict,
    _find_synthetic_patterns,
    check_confidence_vs_sources,
    check_metrics_vs_run_json,
    check_success_criteria_coverage,
    check_synthetic_data,
    check_verdict_consistency,
    run_audit,
)

# ── Helper builders ────────────────────────────────────────────────────────────


def _make_result_summary(
    verdict: str = "PROMOTE",
    confidence: str = "HIGH",
    metric_name: str = "F1",
    metric_value: float = 0.92,
    sources: list[str] | None = None,
) -> str:
    """Build a minimal result_summary.md string."""
    urls = "\n".join(sources or ["https://example.com/data", "https://example.com/data2"])
    return f"""\
## Result Summary

| Metric | Result |
|--------|--------|
| {metric_name} | {metric_value:.2f} |

## Verdict

- [x] **{verdict}**
- [ ] **REPEAT**
- [ ] **REJECT**
- [ ] **ARCHIVE**

## Confidence

- [x] **{confidence}**
- [ ] **MEDIUM**
- [ ] **LOW**

## Evidence

{urls}
"""


def _make_decision(verdict: str = "PROMOTE") -> str:
    """Build a minimal decision.md string."""
    return f"""\
## Decision

- [x] **{verdict}**
- [ ] **REPEAT**
- [ ] **REJECT**
"""


# ── _extract_checked_verdict ──────────────────────────────────────────────────


class TestExtractCheckedVerdict:
    def test_finds_promote(self):
        text = "- [x] **PROMOTE**"
        assert _extract_checked_verdict(text, ["PROMOTE", "REJECT"]) == "PROMOTE"

    def test_finds_uppercase_x(self):
        text = "- [X] **REJECT**"
        assert _extract_checked_verdict(text, ["PROMOTE", "REJECT"]) == "REJECT"

    def test_returns_none_when_no_check(self):
        text = "- [ ] **PROMOTE**"
        assert _extract_checked_verdict(text, ["PROMOTE", "REJECT"]) is None

    def test_returns_first_checked(self):
        text = "- [x] **PROMOTE**\n- [x] **REPEAT**"
        # ARRANGE: PROMOTE is listed first in options
        result = _extract_checked_verdict(text, ["PROMOTE", "REPEAT"])
        assert result == "PROMOTE"


# ── _count_checkboxes ──────────────────────────────────────────────────────────


class TestCountCheckboxes:
    def test_all_checked(self):
        text = "- [x] First\n- [X] Second\n- [x] Third"
        checked, total = _count_checkboxes(text)
        assert checked == 3
        assert total == 3

    def test_mixed(self):
        text = "- [x] Done\n- [ ] Pending\n- [ ] Also pending"
        checked, total = _count_checkboxes(text)
        assert checked == 1
        assert total == 3

    def test_empty(self):
        checked, total = _count_checkboxes("No checkboxes here")
        assert checked == 0
        assert total == 0


# ── _find_synthetic_patterns ──────────────────────────────────────────────────


class TestFindSyntheticPatterns:
    def test_detects_create_synthetic(self):
        found = _find_synthetic_patterns("Used create_synthetic() to generate data")
        assert any("create_synthetic" in p for p in found)

    def test_detects_mock_data(self):
        found = _find_synthetic_patterns("Loaded mock_data for testing")
        assert any("mock_data" in p for p in found)

    def test_detects_verified_synthetic_marker(self):
        found = _find_synthetic_patterns("[VERIFIED-SYNTHETIC] result: F1=0.97")
        assert len(found) > 0

    def test_clean_text_returns_empty(self):
        found = _find_synthetic_patterns("Real data from NIH RePORTER API, confirmed externally.")
        assert found == []


# ── check_metrics_vs_run_json ─────────────────────────────────────────────────


class TestCheckMetricsVsRunJson:
    def test_missing_result_summary_warns(self, tmp_path):
        # ARRANGE: experiment with no result_summary.md
        exp = tmp_path / "exp"
        exp.mkdir()

        # ACT
        finding = check_metrics_vs_run_json(exp)

        # ASSERT: cannot check without the file → warning
        assert finding.severity == SEVERITY_WARN
        assert "result_summary" in finding.message.lower()

    def test_missing_run_json_warns(self, tmp_path):
        # ARRANGE: result_summary.md present but no metrics/run.json
        exp = tmp_path / "exp"
        exp.mkdir()
        (exp / "result_summary.md").write_text(
            _make_result_summary(metric_name="F1", metric_value=0.92),
            encoding="utf-8",
        )

        # ACT
        finding = check_metrics_vs_run_json(exp)

        # ASSERT: missing run.json is a warning (not a hard error)
        assert finding.severity == SEVERITY_WARN
        assert "run.json" in finding.message

    def test_matching_metrics_passes(self, tmp_path):
        # ARRANGE: result_summary claims F1=0.92, run.json confirms 0.92
        exp = tmp_path / "exp"
        exp.mkdir()
        (exp / "result_summary.md").write_text(
            _make_result_summary(metric_name="F1", metric_value=0.92),
            encoding="utf-8",
        )
        metrics_dir = exp / "metrics"
        metrics_dir.mkdir()
        (metrics_dir / "run.json").write_text(json.dumps({"F1": 0.92}), encoding="utf-8")

        # ACT
        finding = check_metrics_vs_run_json(exp)

        # ASSERT: matching values → ok
        assert finding.severity == SEVERITY_OK

    def test_metric_mismatch_errors(self, tmp_path):
        # ARRANGE: result_summary claims F1=0.95, run.json shows 0.70 (27% delta)
        exp = tmp_path / "exp"
        exp.mkdir()
        (exp / "result_summary.md").write_text(
            _make_result_summary(metric_name="F1", metric_value=0.95),
            encoding="utf-8",
        )
        metrics_dir = exp / "metrics"
        metrics_dir.mkdir()
        (metrics_dir / "run.json").write_text(json.dumps({"F1": 0.70}), encoding="utf-8")

        # ACT
        finding = check_metrics_vs_run_json(exp)

        # ASSERT: >5% delta → error (anti-ARCHCODE-manuscript-incident check)
        assert finding.severity == SEVERITY_ERROR
        assert "mismatch" in finding.message.lower()

    def test_invalid_run_json_errors(self, tmp_path):
        # ARRANGE: run.json with invalid JSON content
        exp = tmp_path / "exp"
        exp.mkdir()
        (exp / "result_summary.md").write_text(_make_result_summary(), encoding="utf-8")
        metrics_dir = exp / "metrics"
        metrics_dir.mkdir()
        (metrics_dir / "run.json").write_text("not valid JSON {{{", encoding="utf-8")

        # ACT
        finding = check_metrics_vs_run_json(exp)

        # ASSERT
        assert finding.severity == SEVERITY_ERROR
        assert "invalid json" in finding.message.lower()


# ── check_verdict_consistency ─────────────────────────────────────────────────


class TestCheckVerdictConsistency:
    def test_matching_verdicts_pass(self, tmp_path):
        # ARRANGE: both files show PROMOTE
        exp = tmp_path / "exp"
        exp.mkdir()
        (exp / "decision.md").write_text(_make_decision("PROMOTE"), encoding="utf-8")
        (exp / "result_summary.md").write_text(
            _make_result_summary(verdict="PROMOTE"), encoding="utf-8"
        )

        # ACT
        finding = check_verdict_consistency(exp)

        # ASSERT: consistent verdicts → ok
        assert finding.severity == SEVERITY_OK
        assert "PROMOTE" in finding.message

    def test_verdict_mismatch_errors(self, tmp_path):
        # ARRANGE: decision says PROMOTE, summary says REJECT — classic copy-paste bug
        exp = tmp_path / "exp"
        exp.mkdir()
        (exp / "decision.md").write_text(_make_decision("PROMOTE"), encoding="utf-8")
        (exp / "result_summary.md").write_text(
            _make_result_summary(verdict="REJECT"), encoding="utf-8"
        )

        # ACT
        finding = check_verdict_consistency(exp)

        # ASSERT: mismatch is an error, not just a warning
        assert finding.severity == SEVERITY_ERROR
        assert "PROMOTE" in finding.message
        assert "REJECT" in finding.message

    def test_missing_decision_warns(self, tmp_path):
        # ARRANGE: only result_summary.md present
        exp = tmp_path / "exp"
        exp.mkdir()
        (exp / "result_summary.md").write_text(_make_result_summary(), encoding="utf-8")

        # ACT
        finding = check_verdict_consistency(exp)

        # ASSERT
        assert finding.severity == SEVERITY_WARN

    def test_no_checkbox_checked_in_either_warns(self, tmp_path):
        # ARRANGE: neither file has a checked verdict
        exp = tmp_path / "exp"
        exp.mkdir()
        (exp / "decision.md").write_text("## Decision\n\n- [ ] PROMOTE\n", encoding="utf-8")
        (exp / "result_summary.md").write_text("## Verdict\n\n- [ ] PROMOTE\n", encoding="utf-8")

        # ACT
        finding = check_verdict_consistency(exp)

        # ASSERT: unchecked verdicts are ambiguous → warn
        assert finding.severity == SEVERITY_WARN


# ── check_confidence_vs_sources ───────────────────────────────────────────────


class TestCheckConfidenceVsSources:
    def test_high_confidence_with_two_urls_passes(self, tmp_path):
        # ARRANGE: HIGH confidence backed by 2 URLs
        exp = tmp_path / "exp"
        exp.mkdir()
        (exp / "result_summary.md").write_text(
            _make_result_summary(
                confidence="HIGH",
                sources=["https://source1.com/data", "https://source2.com/data"],
            ),
            encoding="utf-8",
        )

        # ACT
        finding = check_confidence_vs_sources(exp)

        # ASSERT
        assert finding.severity == SEVERITY_OK

    def test_high_confidence_with_one_source_warns(self, tmp_path):
        # ARRANGE: HIGH confidence but only 1 source — integrity rules require ≥2
        exp = tmp_path / "exp"
        exp.mkdir()
        content = """\
## Confidence

- [x] **HIGH**
- [ ] **MEDIUM**

## Evidence

https://single-source.example.com/data
"""
        (exp / "result_summary.md").write_text(content, encoding="utf-8")

        # ACT
        finding = check_confidence_vs_sources(exp)

        # ASSERT: fewer sources than required for HIGH confidence → warning
        assert finding.severity == SEVERITY_WARN
        assert "HIGH" in finding.message

    def test_missing_result_summary_warns(self, tmp_path):
        # ARRANGE: no file at all
        exp = tmp_path / "exp"
        exp.mkdir()

        finding = check_confidence_vs_sources(exp)
        assert finding.severity == SEVERITY_WARN


# ── check_success_criteria_coverage ──────────────────────────────────────────


class TestCheckSuccessCriteriaCoverage:
    def test_all_criteria_checked_passes(self, tmp_path):
        # ARRANGE: claim.md with all boxes checked, result_summary present
        exp = tmp_path / "exp"
        exp.mkdir()
        (exp / "claim.md").write_text(
            "## Success Criteria\n\n- [x] Criterion A\n- [x] Criterion B\n",
            encoding="utf-8",
        )
        (exp / "result_summary.md").write_text("Results here.\n", encoding="utf-8")

        # ACT
        finding = check_success_criteria_coverage(exp)

        # ASSERT
        assert finding.severity == SEVERITY_OK

    def test_majority_unchecked_warns(self, tmp_path):
        # ARRANGE: 3 criteria, only 1 checked (67% unchecked > 50% threshold)
        exp = tmp_path / "exp"
        exp.mkdir()
        (exp / "claim.md").write_text(
            "## Success Criteria\n\n- [x] Done\n- [ ] Pending\n- [ ] Also pending\n",
            encoding="utf-8",
        )
        (exp / "result_summary.md").write_text("Results here.\n", encoding="utf-8")

        # ACT
        finding = check_success_criteria_coverage(exp)

        # ASSERT: >50% unchecked → warning about incomplete reporting
        assert finding.severity == SEVERITY_WARN

    def test_missing_claim_warns(self, tmp_path):
        # ARRANGE: no claim.md
        exp = tmp_path / "exp"
        exp.mkdir()
        (exp / "result_summary.md").write_text("Results.\n", encoding="utf-8")

        finding = check_success_criteria_coverage(exp)
        assert finding.severity == SEVERITY_WARN

    def test_no_success_criteria_section_warns(self, tmp_path):
        # ARRANGE: claim.md without a ## Success Criteria section
        exp = tmp_path / "exp"
        exp.mkdir()
        (exp / "claim.md").write_text("# Claim\n\nNo criteria section.\n", encoding="utf-8")
        (exp / "result_summary.md").write_text("Results.\n", encoding="utf-8")

        finding = check_success_criteria_coverage(exp)
        assert finding.severity == SEVERITY_WARN


# ── check_synthetic_data ──────────────────────────────────────────────────────


class TestCheckSyntheticData:
    def test_clean_experiment_passes(self, tmp_path):
        # ARRANGE: no synthetic patterns anywhere
        exp = tmp_path / "exp"
        exp.mkdir()
        (exp / "result_summary.md").write_text(
            _make_result_summary(confidence="HIGH"),
            encoding="utf-8",
        )
        (exp / "controls.md").write_text(
            "## Controls\n\nUsed real NIH data from https://api.nih.gov/\n",
            encoding="utf-8",
        )

        # ACT
        finding = check_synthetic_data(exp)

        # ASSERT
        assert finding.severity == SEVERITY_OK

    def test_synthetic_with_high_confidence_errors(self, tmp_path):
        # ARRANGE: HIGH confidence + create_synthetic = SYNTHETIC-OVERCLAIM
        # This is the ТОП-10 theater anti-pattern (2026-05-01 postmortem)
        exp = tmp_path / "exp"
        exp.mkdir()
        content = _make_result_summary(confidence="HIGH")
        content += "\ncreate_synthetic() used for all test cases.\n"
        (exp / "result_summary.md").write_text(content, encoding="utf-8")
        (exp / "controls.md").write_text("# Controls\n\nBasic.\n", encoding="utf-8")

        # ACT
        finding = check_synthetic_data(exp)

        # ASSERT: HIGH + synthetic → error to block validation theater
        assert finding.severity == SEVERITY_ERROR
        assert "SYNTHETIC-OVERCLAIM" in finding.message

    def test_synthetic_with_low_confidence_warns(self, tmp_path):
        # ARRANGE: LOW confidence + synthetic is acceptable (downgraded confidence)
        exp = tmp_path / "exp"
        exp.mkdir()
        content = """\
## Verdict

- [x] **PROMOTE**

## Confidence

- [ ] **HIGH**
- [ ] **MEDIUM**
- [x] **LOW**

mock_data was used for initial proof-of-concept.
"""
        (exp / "result_summary.md").write_text(content, encoding="utf-8")
        (exp / "controls.md").write_text("# Controls\n", encoding="utf-8")

        # ACT
        finding = check_synthetic_data(exp)

        # ASSERT: synthetic with LOW confidence → warning (not error)
        assert finding.severity == SEVERITY_WARN


# ── run_audit integration ──────────────────────────────────────────────────────


class TestRunAudit:
    def test_all_five_checks_run(self, tmp_path):
        # ARRANGE: minimal experiment directory
        exp = tmp_path / "exp"
        exp.mkdir()

        # ACT: run_audit always executes all 5 checks
        report = run_audit(exp)

        # ASSERT: 5 findings, one per check
        assert len(report.findings) == 5

    def test_clean_experiment_has_no_errors(self, tmp_path):
        # ARRANGE: well-formed experiment with all checks expected to pass/warn
        exp = tmp_path / "exp"
        exp.mkdir()

        summary_content = _make_result_summary(
            verdict="PROMOTE",
            confidence="HIGH",
            metric_name="F1",
            metric_value=0.88,
            sources=["https://real-data.example.com/A", "https://real-data.example.com/B"],
        )
        (exp / "result_summary.md").write_text(summary_content, encoding="utf-8")
        (exp / "decision.md").write_text(_make_decision("PROMOTE"), encoding="utf-8")
        (exp / "claim.md").write_text(
            "## Success Criteria\n\n- [x] Criterion A\n- [x] Criterion B\n",
            encoding="utf-8",
        )
        (exp / "controls.md").write_text(
            "## Controls\n\nReal data from https://example.com/dataset\n",
            encoding="utf-8",
        )
        metrics_dir = exp / "metrics"
        metrics_dir.mkdir()
        (metrics_dir / "run.json").write_text(json.dumps({"F1": 0.88}), encoding="utf-8")

        # ACT
        report = run_audit(exp)

        # ASSERT: no errors (warnings about sources may still appear depending on
        # count_evidence_sources implementation, but no ERROR severity)
        assert len(report.errors) == 0


# ── --strict mode via exit codes ──────────────────────────────────────────────


class TestStrictMode:
    """Verify that --strict causes sys.exit(1) when there are only warnings.

    We test the exit-code logic by calling run_audit and checking the computed
    exit code — same logic as main() without spawning a subprocess.
    """

    def test_warnings_without_strict_exit_2(self, tmp_path):
        # ARRANGE: experiment with warnings only (no run.json → warn)
        exp = tmp_path / "exp"
        exp.mkdir()
        (exp / "result_summary.md").write_text(_make_result_summary(), encoding="utf-8")
        (exp / "decision.md").write_text(_make_decision("PROMOTE"), encoding="utf-8")
        (exp / "claim.md").write_text("## Success Criteria\n\n- [x] Done\n", encoding="utf-8")
        (exp / "controls.md").write_text("# Controls\n\nBasic.\n", encoding="utf-8")

        report = run_audit(exp)

        # Compute exit code the same way main() does
        n_err = len(report.errors)
        n_warn = len(report.warnings)

        strict = False
        expected_exit = (
            1 if n_err > 0 else (1 if (n_warn > 0 and strict) else (2 if n_warn > 0 else 0))
        )

        # ASSERT: warnings without --strict → exit code 2
        assert n_err == 0
        assert expected_exit == 2

    def test_warnings_with_strict_exit_1(self, tmp_path):
        # ARRANGE: same as above but strict=True
        exp = tmp_path / "exp"
        exp.mkdir()
        (exp / "result_summary.md").write_text(_make_result_summary(), encoding="utf-8")
        (exp / "decision.md").write_text(_make_decision("PROMOTE"), encoding="utf-8")
        (exp / "claim.md").write_text("## Success Criteria\n\n- [x] Done\n", encoding="utf-8")
        (exp / "controls.md").write_text("# Controls\n\nBasic.\n", encoding="utf-8")

        report = run_audit(exp)
        n_err = len(report.errors)
        n_warn = len(report.warnings)

        strict = True
        expected_exit = (
            1 if n_err > 0 else (1 if (n_warn > 0 and strict) else (2 if n_warn > 0 else 0))
        )

        # ASSERT: warnings with --strict → exit code 1
        assert n_err == 0
        assert expected_exit == 1
