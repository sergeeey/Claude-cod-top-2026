"""Tests for mutation_tracker.py pure functions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from mutation_tracker import (
    _is_mutation_suite,
    _is_template,
    _parse_results,
    _update_mdr_in_content,
    _yaml_list_str,
    compute_mdr,
)

# ---------------------------------------------------------------------------
# _is_template
# ---------------------------------------------------------------------------


class TestIsTemplate:
    def test_unfilled_template_detected(self):
        content = "experiment_id: <YYYYMMDD-short-slug>\nverification_command: foo"
        assert _is_template(content)

    def test_unfilled_command_detected(self):
        content = "verification_command: <paste exact command here>"
        assert _is_template(content)

    def test_filled_file_not_template(self):
        content = "experiment_id: 20260823-test\nverification_command: pytest tests/"
        assert not _is_template(content)


# ---------------------------------------------------------------------------
# _is_mutation_suite
# ---------------------------------------------------------------------------


class TestIsMutationSuite:
    def test_correct_name_in_experiments(self):
        assert _is_mutation_suite("experiments/20260823-test/mutation_suite.yaml")

    def test_wrong_name(self):
        assert not _is_mutation_suite("experiments/20260823-test/dependency_graph.yaml")

    def test_not_in_experiments(self):
        assert not _is_mutation_suite("hooks/mutation_suite.yaml")


# ---------------------------------------------------------------------------
# _parse_results
# ---------------------------------------------------------------------------


SAMPLE_CONTENT = """\
experiment_id: 20260823-test

mutations:
  - id: M-001
    type: sign_flip
    detection_expected: true
  - id: M-002
    type: threshold_shift
    detection_expected: true
  - id: M-003
    type: negation
    detection_expected: false

results:
  - id: M-001
    injected: true
    detected: true
    exit_code: 1
    notes: "found it"
  - id: M-002
    injected: true
    detected: false
    exit_code: 0
    notes: ""
"""


class TestParseResults:
    def test_parses_mutations(self):
        mutations, results = _parse_results(SAMPLE_CONTENT)
        assert len(mutations) == 3

    def test_parses_detection_expected(self):
        mutations, _ = _parse_results(SAMPLE_CONTENT)
        assert mutations[0]["detection_expected"] is True
        assert mutations[2]["detection_expected"] is False

    def test_parses_results_detected(self):
        _, results = _parse_results(SAMPLE_CONTENT)
        assert results[0]["detected"] is True
        assert results[1]["detected"] is False

    def test_empty_results_block(self):
        content = "mutations:\n  - id: M-001\n    detection_expected: true\nresults: []\n"
        mutations, results = _parse_results(content)
        assert len(mutations) == 1
        assert results == []

    def test_no_mutations_block(self):
        mutations, results = _parse_results("some: yaml\n")
        assert mutations == []
        assert results == []


# ---------------------------------------------------------------------------
# compute_mdr
# ---------------------------------------------------------------------------


class TestComputeMdr:
    def test_no_results_returns_pending(self):
        mutations = [{"id": "M-001", "detection_expected": True}]
        rate, verdict, blind = compute_mdr(mutations, [])
        assert rate is None
        assert verdict == "PENDING"
        assert blind == []

    def test_pass_verdict(self):
        mutations = [
            {"id": "M-001", "detection_expected": True},
            {"id": "M-002", "detection_expected": True},
        ]
        results = [
            {"id": "M-001", "detected": True},
            {"id": "M-002", "detected": True},
        ]
        rate, verdict, blind = compute_mdr(mutations, results)
        assert rate == 1.0
        assert verdict == "PASS"
        assert blind == []

    def test_warn_verdict(self):
        mutations = [
            {"id": "M-001", "detection_expected": True},
            {"id": "M-002", "detection_expected": True},
        ]
        results = [
            {"id": "M-001", "detected": True},
            {"id": "M-002", "detected": False},  # missed
        ]
        rate, verdict, blind = compute_mdr(mutations, results)
        assert 0.50 <= rate < 0.80
        assert verdict == "WARN"
        assert "M-002" in blind

    def test_fail_verdict(self):
        mutations = [
            {"id": "M-001", "detection_expected": True},
            {"id": "M-002", "detection_expected": True},
            {"id": "M-003", "detection_expected": True},
        ]
        results = [
            {"id": "M-001", "detected": False},
            {"id": "M-002", "detected": False},
            {"id": "M-003", "detected": False},
        ]
        rate, verdict, blind = compute_mdr(mutations, results)
        assert rate == 0.0
        assert verdict == "FAIL"
        assert set(blind) == {"M-001", "M-002", "M-003"}

    def test_not_expected_not_counted(self):
        """Mutations with detection_expected=False don't affect MDR."""
        mutations = [
            {"id": "M-001", "detection_expected": True},
            {"id": "M-002", "detection_expected": False},  # known blind spot
        ]
        results = [
            {"id": "M-001", "detected": True},
            {"id": "M-002", "detected": False},  # irrelevant to score
        ]
        rate, verdict, _ = compute_mdr(mutations, results)
        assert rate == 1.0
        assert verdict == "PASS"

    def test_missing_result_id_skipped(self):
        """If a mutation has no result entry, it doesn't count in denominator."""
        mutations = [
            {"id": "M-001", "detection_expected": True},
            {"id": "M-002", "detection_expected": True},
        ]
        results = [{"id": "M-001", "detected": True}]  # M-002 not recorded yet
        rate, verdict, _ = compute_mdr(mutations, results)
        assert rate == 1.0  # 1 detected out of 1 scored

    def test_no_expected_detections(self):
        mutations = [{"id": "M-001", "detection_expected": False}]
        results = [{"id": "M-001", "detected": False}]
        rate, verdict, _ = compute_mdr(mutations, results)
        assert verdict == "NO_EXPECTED_DETECTIONS"
        assert rate is None

    def test_rate_rounded_to_3_places(self):
        mutations = [{"id": f"M-{i:03d}", "detection_expected": True} for i in range(3)]
        results = [
            {"id": "M-000", "detected": True},
            {"id": "M-001", "detected": True},
            {"id": "M-002", "detected": False},
        ]
        rate, _, _ = compute_mdr(mutations, results)
        # 2/3 ≈ 0.667
        assert rate == round(2 / 3, 3)


# ---------------------------------------------------------------------------
# _yaml_list_str
# ---------------------------------------------------------------------------


class TestYamlListStr:
    def test_empty_is_empty_brackets(self):
        assert _yaml_list_str([]) == "[]"

    def test_single_item(self):
        assert _yaml_list_str(["M-001"]) == "[M-001]"

    def test_multiple_items(self):
        result = _yaml_list_str(["M-001", "M-002"])
        assert result == "[M-001, M-002]"


# ---------------------------------------------------------------------------
# _update_mdr_in_content
# ---------------------------------------------------------------------------


class TestUpdateMdrInContent:
    def _base_content(self) -> str:
        return SAMPLE_CONTENT + "\nmdr:\n  rate: null\n  verdict: null\n  blind_spots: []\n"

    def test_updates_rate_and_verdict(self):
        mutations = [
            {"id": "M-001", "detection_expected": True},
            {"id": "M-002", "detection_expected": True},
        ]
        results = [
            {"id": "M-001", "detected": True},
            {"id": "M-002", "detected": True},
        ]
        updated = _update_mdr_in_content(self._base_content(), mutations, results, 1.0, "PASS", [])
        assert "verdict: PASS" in updated
        assert "rate: 1.0" in updated

    def test_appends_when_no_mdr_block(self):
        content = SAMPLE_CONTENT  # no mdr: block
        mutations = [{"id": "M-001", "detection_expected": True}]
        results = [{"id": "M-001", "detected": False}]
        updated = _update_mdr_in_content(content, mutations, results, 0.0, "FAIL", ["M-001"])
        assert "mdr:" in updated
        assert "verdict: FAIL" in updated
        assert "M-001" in updated

    def test_blind_spots_written(self):
        content = self._base_content()
        mutations = [{"id": "M-002", "detection_expected": True}]
        results = [{"id": "M-002", "detected": False}]
        updated = _update_mdr_in_content(content, mutations, results, 0.0, "FAIL", ["M-002"])
        assert "M-002" in updated
