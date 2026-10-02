"""Tests for independence_scorer.py.

Positive control (mandatory — per patterns.md [AVOID] validation theater):
  compute_independence must give score=0.0 when both paths are identical
  and score=1.0 when paths share nothing (all non-null fields differ).
  These are structural invariants, not optional coverage.
"""

import io
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from independence_scorer import (
    _COVERAGE_THRESHOLD,
    _library_major_set,
    _normalise,
    _parse_yaml_paths,
    _update_score_in_content,
    _yaml_scalar,
    compute_independence,
    evidence_coverage,
    tier,
)

# ---------------------------------------------------------------------------
# _normalise
# ---------------------------------------------------------------------------


class TestNormalise:
    def test_none_returns_none(self):
        assert _normalise(None) is None

    def test_null_string_returns_none(self):
        assert _normalise("null") is None

    def test_tilde_returns_none(self):
        assert _normalise("~") is None

    def test_empty_string_returns_none(self):
        assert _normalise("  ") is None

    def test_non_null_value_lowercased(self):
        assert _normalise("Claude-Sonnet") == "claude-sonnet"

    def test_leading_trailing_whitespace_stripped(self):
        assert _normalise("  gpt-4  ") == "gpt-4"


# ---------------------------------------------------------------------------
# _library_major_set
# ---------------------------------------------------------------------------


class TestLibraryMajorSet:
    def test_empty_returns_empty(self):
        assert _library_major_set([]) == set()

    def test_none_returns_empty(self):
        assert _library_major_set(None) == set()

    def test_major_version_only(self):
        result = _library_major_set(["numpy==1.26.0", "scipy==1.11.4"])
        assert result == {"numpy==1", "scipy==1"}

    def test_same_major_different_patch_are_equal(self):
        a = _library_major_set(["numpy==1.26.0"])
        b = _library_major_set(["numpy==1.24.3"])
        assert a == b  # overlap — same major

    def test_different_major_are_different(self):
        a = _library_major_set(["numpy==1.26.0"])
        b = _library_major_set(["numpy==2.0.0"])
        assert a != b

    def test_package_without_version_uses_bare_name(self):
        result = _library_major_set(["pandas"])
        assert "pandas" in result


# ---------------------------------------------------------------------------
# compute_independence — structural invariants
# ---------------------------------------------------------------------------


class TestComputeIndependenceInvariants:
    """Positive control tests: score must satisfy known extremes."""

    def test_identical_non_null_paths_give_zero(self):
        path = {
            "model_family": "claude-sonnet",
            "dataset": "real-dataset-v1",
            "code_commit": "abc123",
            "libraries": ["numpy==1.26.0"],
            "retrieval_snapshot": "sha256:aaa",
            "definition_of_metric": "recall@5",
        }
        score, shared, _ = compute_independence(path, path.copy())
        assert score == 0.0, f"identical paths must score 0, got {score}"
        assert len(shared) > 0

    def test_fully_different_paths_give_one(self):
        a = {
            "model_family": "claude-sonnet",
            "dataset": "dataset-a",
            "code_commit": "abc123",
            "libraries": ["numpy==1.26.0"],
            "retrieval_snapshot": "sha256:aaa",
            "definition_of_metric": "recall@5",
        }
        b = {
            "model_family": "gpt-4",
            "dataset": "dataset-b",
            "code_commit": "def456",
            "libraries": ["sage==9.8"],
            "retrieval_snapshot": "sha256:bbb",
            "definition_of_metric": "precision@5",
        }
        score, shared, _ = compute_independence(a, b)
        assert score == 1.0, f"fully different paths must score 1.0, got {score}"
        assert shared == []

    def test_all_null_fields_are_unknown_not_independent(self):
        """REGRESSION INVERSION (2026-09-19). This test used to be
        `test_all_null_fields_give_one` and asserted `score == 1.0` with the
        docstring "unknown = not shared". That pinned the defect: a pair with
        NO recorded provenance scored 1.0, landed in the HIGH tier, and -- the
        only consumer warns solely on LOW -- produced silence. UNKNOWN is not
        INDEPENDENT: no comparable dimension means no score at all."""
        a = {"model_family": None, "dataset": None}
        b = {"model_family": None, "dataset": None}
        score, shared, detail = compute_independence(a, b)
        assert score is None
        assert shared == []
        assert evidence_coverage(a, b) == 0.0
        assert tier(score, evidence_coverage(a, b)) == "UNKNOWN"

    def test_score_range(self):
        a = {"model_family": "claude-sonnet", "dataset": "ds-a"}
        b = {"model_family": "claude-sonnet", "dataset": "ds-b"}
        score, _, _ = compute_independence(a, b)
        assert score is not None
        assert 0.0 <= score <= 1.0

    def test_one_null_one_filled_is_unknown_not_a_difference(self):
        """REGRESSION INVERSION (2026-09-19). Previously `Null in one path →
        can't prove overlap → difference` (and asserted score > 0). Failing to
        verify an overlap is not evidence of independence: UNKNOWN ≠ DIFFERENT.
        The dimension is not comparable, so it contributes nothing either way."""
        a = {"model_family": "claude-sonnet"}
        b = {"model_family": None}
        score, shared, detail = compute_independence(a, b)
        assert score is None  # nothing comparable → no score, not a favourable 1.0
        assert all(d["field"] != "model_family" for d in shared)
        row = next(r for r in detail if r["dimension"] == "model_family")
        assert row["skipped"] is True
        assert row["contribution"] == 0.0
        # the persisted row still shows WHICH side was recorded
        assert row["a_val"] == "claude-sonnet"
        assert row["b_val"] is None


# ---------------------------------------------------------------------------
# compute_independence — partial overlap (libraries Jaccard)
# ---------------------------------------------------------------------------


class TestLibraryOverlap:
    def test_partial_library_overlap_reduces_contribution(self):
        a = {"libraries": ["numpy==1.26.0", "scipy==1.11.0"]}
        b = {"libraries": ["numpy==1.26.0", "pandas==2.1.0"]}  # numpy shared
        score_partial, _, _ = compute_independence(a, b)

        c = {"libraries": ["numpy==1.26.0"]}
        d = {"libraries": ["numpy==1.26.0"]}  # fully shared
        score_full, _, _ = compute_independence(c, d)

        # Partial overlap must give higher score than full overlap
        assert score_partial > score_full

    def test_no_library_overlap_gives_full_weight(self):
        a = {"libraries": ["numpy==1.26.0"]}
        b = {"libraries": ["sage==9.8"]}
        score, shared, _ = compute_independence(a, b)
        lib_shared = [d for d in shared if d.get("field") == "libraries"]
        assert lib_shared == []


# ---------------------------------------------------------------------------
# tier()
# ---------------------------------------------------------------------------


class TestTier:
    """Score bands are unchanged; every call now states its evidence coverage
    (fully observed = 1.0 here) because `tier` no longer accepts a score alone."""

    def test_high_at_threshold(self):
        assert tier(0.70, 1.0) == "HIGH"

    def test_high_above(self):
        assert tier(1.0, 1.0) == "HIGH"

    def test_medium_at_threshold(self):
        assert tier(0.40, 1.0) == "MEDIUM"

    def test_medium_below_high(self):
        assert tier(0.69, 1.0) == "MEDIUM"

    def test_low_below_medium(self):
        assert tier(0.39, 1.0) == "LOW"

    def test_low_at_zero(self):
        assert tier(0.0, 1.0) == "LOW"

    def test_no_score_is_unknown_whatever_the_coverage(self):
        assert tier(None, 1.0) == "UNKNOWN"
        assert tier(None, 0.0) == "UNKNOWN"

    def test_low_coverage_overrides_a_high_local_score(self):
        """A perfect local score computed on too little observable provenance
        must not read as HIGH independence."""
        assert tier(1.0, 0.49) == "UNKNOWN"
        assert tier(0.0, 0.10) == "UNKNOWN"  # and not LOW either: also unproven

    def test_coverage_exactly_at_threshold_is_not_unknown(self):
        assert tier(1.0, _COVERAGE_THRESHOLD) == "HIGH"

    def test_coverage_is_a_required_argument(self):
        """No default on purpose: a default of 1.0 would re-create the
        favourable-default bug one call site at a time."""
        with pytest.raises(TypeError):
            tier(1.0)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# evidence_coverage + the UNKNOWN contract (2026-09-19)
#   UNKNOWN != DIFFERENT, UNKNOWN != INDEPENDENT
# ---------------------------------------------------------------------------

_FULL_A = {
    "model_family": "claude-sonnet",
    "dataset": "dataset-a",
    "code_commit": "abc123",
    "libraries": ["numpy==1.26.0"],
    "retrieval_snapshot": "sha256:aaa",
    "definition_of_metric": "recall@5",
}
_FULL_B = {
    "model_family": "gpt-4",
    "dataset": "dataset-b",
    "code_commit": "def456",
    "libraries": ["sage==9.8"],
    "retrieval_snapshot": "sha256:bbb",
    "definition_of_metric": "precision@5",
}


class TestEvidenceCoverage:
    def test_weighted_not_counted(self):
        """model_family (0.30) known on both sides outweighs
        definition_of_metric (0.03) -- coverage is by WEIGHT, not field count."""
        assert evidence_coverage({"model_family": "a"}, {"model_family": "b"}) == 0.3
        assert (
            evidence_coverage({"definition_of_metric": "a"}, {"definition_of_metric": "b"}) == 0.03
        )

    def test_full_is_one(self):
        assert evidence_coverage(_FULL_A, _FULL_B) == 1.0

    def test_needs_both_sides(self):
        assert evidence_coverage(_FULL_A, {}) == 0.0
        assert evidence_coverage({}, _FULL_B) == 0.0

    def test_empty_library_list_counts_as_not_recorded(self):
        """`libraries: []` is indistinguishable from "not filled in" in the
        parser; an empty list is treated as not recorded (documented in
        `_recorded_value`), so it must not buy any coverage."""
        a = dict(_FULL_A)
        b = dict(_FULL_B, libraries=[])
        assert evidence_coverage(a, b) == 0.85  # everything except libraries (0.15)

    def test_boundary_is_stable_against_float_noise(self):
        """0.30 + 0.20 must be exactly 0.5, so the >= threshold comparison
        does not flip on summation noise."""
        a = {"model_family": "x", "code_commit": "1"}
        b = {"model_family": "y", "code_commit": "2"}
        assert evidence_coverage(a, b) == 0.5
        score, _, _ = compute_independence(a, b)
        assert tier(score, evidence_coverage(a, b)) == "HIGH"


class TestUnknownContract:
    """The regression table for the 2026-09-19 fix, end to end (score,
    coverage, tier)."""

    @staticmethod
    def _verdict(a: dict, b: dict) -> tuple[float | None, float, str]:
        score, _, _ = compute_independence(a, b)
        cov = evidence_coverage(a, b)
        return score, cov, tier(score, cov)

    def test_empty_vs_empty_is_unknown(self):
        assert self._verdict({}, {}) == (None, 0.0, "UNKNOWN")

    def test_fully_recorded_vs_nothing_recorded_is_unknown(self):
        """The reproduced failure: A fully documented, B has NO provenance at
        all. Used to score 1.0 / HIGH (verified against origin/main@5a77fde)."""
        assert self._verdict(_FULL_A, {}) == (None, 0.0, "UNKNOWN")
        assert self._verdict({}, _FULL_B) == (None, 0.0, "UNKNOWN")

    def test_a_dimension_null_on_one_side_adds_no_independence(self):
        """Identical everywhere except B doesn't record model_family. The old
        code counted that null as a 0.30 "difference"; now it is simply not
        comparable, and everything that IS comparable is identical."""
        b = dict(_FULL_A, model_family=None)
        score, cov, t = self._verdict(_FULL_A, b)
        assert score == 0.0
        assert cov == 0.7
        assert t == "LOW"

    def test_fully_identical_is_low_zero(self):
        assert self._verdict(_FULL_A, dict(_FULL_A)) == (0.0, 1.0, "LOW")

    def test_fully_disjoint_is_high_one(self):
        assert self._verdict(_FULL_A, _FULL_B) == (1.0, 1.0, "HIGH")

    def test_jointly_known_below_threshold_is_unknown_despite_a_perfect_local_score(self):
        """model_family + retrieval_snapshot + definition_of_metric = 0.40 of
        the weight, all differing -> local score 1.0, but only 40% of the
        provenance is observable on both paths, so the tier is UNKNOWN."""
        a = {"model_family": "x", "retrieval_snapshot": "1", "definition_of_metric": "m1"}
        b = {"model_family": "y", "retrieval_snapshot": "2", "definition_of_metric": "m2"}
        score, cov, t = self._verdict(a, b)
        assert score == 1.0
        assert cov == 0.4
        assert t == "UNKNOWN"

    def test_jointly_known_at_or_above_threshold_is_scored_normally(self):
        a = {"model_family": "x", "dataset": "d1"}  # 0.30 + 0.25 = 0.55
        b = {"model_family": "y", "dataset": "d2"}
        assert self._verdict(a, b) == (1.0, 0.55, "HIGH")

    def test_partially_shared_partially_unknown(self):
        """Comparable: model_family (shared, 0.30) + dataset (differs, 0.25);
        unknown: everything else. score = 0.25/0.55, coverage 0.55 -> scored."""
        a = {"model_family": "same", "dataset": "d1"}
        b = {"model_family": "same", "dataset": "d2"}
        score, cov, t = self._verdict(a, b)
        assert score == round(0.25 / 0.55, 3)  # 0.455
        assert cov == 0.55
        assert t == "MEDIUM"  # 0.40 <= 0.455 < 0.70


def _line_value(text: str, key: str) -> str:
    """The raw value on a top-level `key: value` line.

    WHY not `yaml.safe_load(whole file)`: writing back an EMPTY list currently
    produces `shared_dependencies:[]` (no space after the colon -- invalid YAML;
    `_replace_yaml_block` emits `f"{key}:{new_value}"`). That is a separate,
    pre-existing bug in the write-back, deliberately NOT fixed in this change
    (one fix per PR), so these tests read the fields they own line by line
    instead of depending on the whole file being valid YAML.
    """
    m = re.search(rf"^{re.escape(key)}:[ \t]*(.*?)[ \t]*(?:#.*)?$", text, re.MULTILINE)
    assert m, f"`{key}:` line missing from:\n{text}"
    return m.group(1)


class TestUnknownWriteBack:
    @staticmethod
    def _template(with_coverage_line: bool) -> str:
        cov = "evidence_coverage: null\n" if with_coverage_line else ""
        return (
            "shared_dependencies: []\n"
            "dimension_detail: []\n"
            "independence_score: null\n"
            "independence_tier: null   # HIGH | MEDIUM | LOW | UNKNOWN\n"
            f"{cov}"
            "artifact_hash: null\n"
        )

    def test_none_score_is_written_as_yaml_null(self):
        out = _update_score_in_content(self._template(True), None, "UNKNOWN", [], None, 0.0)
        assert _line_value(out, "independence_score") == "null"  # not the string "None"
        assert _line_value(out, "independence_tier") == "UNKNOWN"
        assert _line_value(out, "evidence_coverage") == "0.0"
        assert "None" not in out

    def test_coverage_line_is_inserted_into_an_older_file_without_one(self):
        out = _update_score_in_content(self._template(False), 0.4, "MEDIUM", [], None, 0.7)
        assert _line_value(out, "evidence_coverage") == "0.7"
        assert out.count("evidence_coverage:") == 1
        # inserted directly after independence_tier, not appended somewhere random
        lines = out.splitlines()
        tier_idx = next(i for i, ln in enumerate(lines) if ln.startswith("independence_tier:"))
        assert lines[tier_idx + 1].startswith("evidence_coverage:")

    def test_second_run_replaces_coverage_not_appends(self):
        first = _update_score_in_content(self._template(False), 0.4, "MEDIUM", [], None, 0.7)
        second = _update_score_in_content(first, None, "UNKNOWN", [], None, 0.0)
        assert second.count("evidence_coverage:") == 1
        assert _line_value(second, "evidence_coverage") == "0.0"
        assert _line_value(second, "independence_score") == "null"

    def test_omitting_coverage_keeps_the_old_call_signature_working(self):
        out = _update_score_in_content(self._template(True), 0.5, "MEDIUM", [])
        assert "independence_score: 0.5" in out
        assert "evidence_coverage: null" in out  # unknown, not invented

    def test_omitting_coverage_never_leaves_a_stale_number_from_a_previous_run(self):
        """Skeptic F3 (2026-09-19): leaving the line untouched would park the
        PREVIOUS run's coverage beside a freshly written score/tier."""
        first = _update_score_in_content(self._template(True), 0.9, "HIGH", [], None, 1.0)
        assert _line_value(first, "evidence_coverage") == "1.0"
        second = _update_score_in_content(first, 0.1, "LOW", [])  # coverage omitted
        assert _line_value(second, "evidence_coverage") == "null"
        assert _line_value(second, "independence_score") == "0.1"

    def test_omitting_coverage_inserts_nothing_into_a_file_without_the_line(self):
        out = _update_score_in_content(self._template(False), 0.5, "MEDIUM", [])
        assert "evidence_coverage" not in out


# ---------------------------------------------------------------------------
# _parse_yaml_paths — template detection
# ---------------------------------------------------------------------------


class TestParseYamlPaths:
    def test_template_returns_none(self):
        template_content = (
            'experiment_id: "<YYYYMMDD-short-slug>"\n'
            "paths:\n"
            "  path_a:\n"
            "    model_family: null\n"
            "  path_b:\n"
            "    model_family: null\n"
        )
        assert _parse_yaml_paths(template_content) is None

    def test_filled_returns_dicts(self):
        content = (
            'experiment_id: "20260823-test"\n'
            "paths:\n"
            "  path_a:\n"
            "    label: Primary\n"
            "    model_family: claude-sonnet\n"
            "    dataset: real-data\n"
            "  path_b:\n"
            "    label: Reconstruction\n"
            "    model_family: gpt-4\n"
            "    dataset: real-data\n"
        )
        result = _parse_yaml_paths(content)
        assert result is not None
        a, b = result
        assert a.get("model_family") == "claude-sonnet"
        assert b.get("model_family") == "gpt-4"
        assert a.get("dataset") == "real-data"


# ---------------------------------------------------------------------------
# _yaml_scalar / dimension_detail write-back (Research/Evidence Loop minimal
# extension, 2026-09-12): compute_independence() already computed this
# per-dimension breakdown before this pass -- it was just discarded after
# being returned. These tests cover persisting it, not new scoring logic.
# ---------------------------------------------------------------------------


class TestYamlScalar:
    def test_none(self):
        assert _yaml_scalar(None) == "null"

    def test_bool(self):
        assert _yaml_scalar(True) == "true"
        assert _yaml_scalar(False) == "false"

    def test_number(self):
        assert _yaml_scalar(0.15) == "0.15"
        assert _yaml_scalar(3) == "3"

    def test_string_is_quoted(self):
        assert _yaml_scalar("claude-sonnet") == '"claude-sonnet"'

    def test_string_with_backslash_and_quote_is_escaped(self):
        """Regression (Codex P2 finding, 2026-09-12): a raw f'"{value}"' wrap
        does not escape embedded backslashes/quotes -- a Windows path like
        `C:\\data\\foo` would produce an invalid double-quoted YAML scalar
        (\\d is not a recognized YAML escape), and an embedded `"` would
        terminate the string early. json.dumps's escaping is a valid subset
        of YAML double-quoted scalar syntax."""
        raw = r'C:\data\foo" ; also has "quotes"'
        scalar = _yaml_scalar(raw)
        assert scalar == json.dumps(raw)
        # round-trips back to the exact original string via yaml.safe_load
        assert yaml.safe_load(f"key: {scalar}")["key"] == raw

    def test_list_is_flow_style(self):
        assert _yaml_scalar(["numpy==1.26", "pandas==2.0"]) == '["numpy==1.26", "pandas==2.0"]'

    def test_bool_not_confused_with_number(self):
        # WHY this test exists: isinstance(True, int) is True in Python --
        # a naive `isinstance(value, (int, float))` check BEFORE the bool
        # check would render True as "1", corrupting the YAML write-back.
        assert _yaml_scalar(True) != "1"


class TestUpdateScoreInContentDimensionDetail:
    def _template(self) -> str:
        return (
            "shared_dependencies: []\n"
            "dimension_detail: []\n"
            "independence_score: null\n"
            "independence_tier: null\n"
        )

    def test_writes_dimension_detail_when_field_present(self):
        detail = [
            {
                "dimension": "model_family",
                "a_val": "claude-sonnet",
                "b_val": "gpt-4",
                "shared": False,
                "weight": 0.3,
                "contribution": 0.3,
                "skipped": False,
            }
        ]
        updated = _update_score_in_content(self._template(), 0.667, "HIGH", [], detail)
        assert 'dimension: "model_family"' in updated
        assert "shared: false" in updated
        assert "weight: 0.3" in updated

    def test_noop_when_field_absent_from_template(self):
        """Backward compatibility: a dependency_graph.yaml written before
        dimension_detail existed has no line to replace -- doing nothing
        there must not raise or corrupt the rest of the write-back."""
        old_template = (
            "shared_dependencies: []\nindependence_score: null\nindependence_tier: null\n"
        )
        updated = _update_score_in_content(old_template, 0.5, "MEDIUM", [], [{"dimension": "x"}])
        assert "dimension_detail" not in updated
        assert "independence_score: 0.5" in updated

    def test_detail_none_keeps_old_call_signature_working(self):
        """Old callers passing only 4 positional args (no detail) must still work."""
        updated = _update_score_in_content(self._template(), 0.5, "MEDIUM", [])
        assert "independence_score: 0.5" in updated
        # dimension_detail line stays as the template's own placeholder, untouched
        assert "dimension_detail: []" in updated

    def test_full_pipeline_persists_real_compute_independence_output(self):
        """End-to-end: compute_independence()'s own detail output round-trips
        through the write-back without needing any new scoring logic."""
        path_a = {"model_family": "claude-sonnet", "libraries": ["numpy==1.26"]}
        path_b = {"model_family": "gpt-4", "libraries": ["numpy==1.26"]}
        score, shared, detail = compute_independence(path_a, path_b)
        cov = evidence_coverage(path_a, path_b)
        updated = _update_score_in_content(
            self._template(), score, tier(score, cov), shared, detail, cov
        )
        assert "model_family" in updated
        assert "libraries" in updated
        assert f"independence_score: {score}" in updated

    def test_second_run_replaces_stale_dimension_detail_not_appends(self):
        """Regression (Codex P1 finding, 2026-09-12): the old `^dimension_detail:.*$`
        MULTILINE replace only ever matched the header line -- on a second run
        over the SAME already-scored file, the indented `  - {...}` rows a
        prior run wrote stayed in place and the new rows were inserted before
        them, growing the block (with potentially contradictory data) on
        every run instead of replacing it."""
        first_detail = [{"dimension": "model_family", "a_val": "claude-sonnet"}]
        second_detail = [{"dimension": "dataset", "a_val": "real-data-v2"}]

        after_first = _update_score_in_content(self._template(), 0.3, "LOW", [], first_detail)
        after_second = _update_score_in_content(after_first, 0.7, "HIGH", [], second_detail)

        assert "model_family" not in after_second
        assert "claude-sonnet" not in after_second
        assert "dataset" in after_second
        assert "real-data-v2" in after_second
        # exactly one dimension_detail header remains, not a stray duplicate
        assert after_second.count("dimension_detail:") == 1
        assert "independence_score: 0.7" in after_second

    def test_second_run_replaces_stale_shared_dependencies_not_appends(self):
        """Same block-replacement bug, applied to the pre-existing
        shared_dependencies field which uses the identical `_replace_yaml_block`
        machinery -- a second run must not leave the first run's rows behind."""
        first_shared = [{"field": "model_family", "value": "claude-sonnet"}]
        second_shared = [{"field": "dataset", "value": "real-data-v2"}]

        after_first = _update_score_in_content(self._template(), 0.3, "LOW", first_shared)
        after_second = _update_score_in_content(after_first, 0.7, "HIGH", second_shared)

        assert "claude-sonnet" not in after_second
        assert "real-data-v2" in after_second
        assert after_second.count("shared_dependencies:") == 1


# ---------------------------------------------------------------------------
# verification_substrate — OBSERVE-only dimension (2026-09-16)
#
# WHY these cases specifically: the whole point of this dimension is that it
# must NEVER move independence_score/independence_tier, no matter what values
# it carries -- so every case pairs a verification_substrate value/non-value
# with an assertion that the score is unaffected, not just that the detail
# row looks right in isolation.
# ---------------------------------------------------------------------------


class TestVerificationSubstrateObserver:
    def test_same_substrate_is_marked_shared_and_does_not_affect_score(self):
        a = {"model_family": "claude-sonnet", "verification_substrate": "same_model"}
        b = {"model_family": "claude-sonnet", "verification_substrate": "same_model"}
        score_with, _, detail_with = compute_independence(a, b)

        a_no_vs = {"model_family": "claude-sonnet"}
        b_no_vs = {"model_family": "claude-sonnet"}
        score_without, _, _ = compute_independence(a_no_vs, b_no_vs)

        assert score_with == score_without, "verification_substrate must not move the score"
        row = next(d for d in detail_with if d["dimension"] == "verification_substrate")
        assert row["shared"] is True
        assert row["observer_only"] is True
        assert row["contribution"] is None

    def test_different_substrate_is_marked_not_shared_and_does_not_affect_score(self):
        a = {"model_family": "claude-sonnet", "verification_substrate": "executable_test"}
        b = {"model_family": "claude-sonnet", "verification_substrate": "formal_proof"}
        score_with, _, detail_with = compute_independence(a, b)

        score_without, _, _ = compute_independence(
            {"model_family": "claude-sonnet"}, {"model_family": "claude-sonnet"}
        )

        assert score_with == score_without, "a differing OBSERVE dimension must still not score"
        row = next(d for d in detail_with if d["dimension"] == "verification_substrate")
        assert row["shared"] is False
        assert row["contribution"] is None

    def test_both_null_is_skipped_like_any_other_dimension(self):
        a = {"model_family": "claude-sonnet", "verification_substrate": None}
        b = {"model_family": "claude-sonnet", "verification_substrate": None}
        _, _, detail = compute_independence(a, b)
        row = next(d for d in detail if d["dimension"] == "verification_substrate")
        assert row["skipped"] is True
        assert row["a_val"] is None
        assert row["b_val"] is None
        assert row["contribution"] is None

    def test_one_null_one_filled_is_not_shared_but_still_zero_weight(self):
        a = {"model_family": "claude-sonnet", "verification_substrate": "physical_experiment"}
        b = {"model_family": "claude-sonnet", "verification_substrate": None}
        score, _, detail = compute_independence(a, b)
        row = next(d for d in detail if d["dimension"] == "verification_substrate")
        assert row["shared"] is False
        assert row["skipped"] is False
        assert row["contribution"] is None
        # same as the null/null case and the same-substrate case -- this
        # dimension never contributes regardless of null/shared/differing
        assert (
            score
            == compute_independence(
                {"model_family": "claude-sonnet"}, {"model_family": "claude-sonnet"}
            )[0]
        )

    def test_verification_substrate_never_appears_in_shared_dependencies(self):
        """shared_dependencies feeds a human-facing 'why is the score low'
        explanation -- an OBSERVE-only match belongs only in dimension_detail,
        since it never caused the score to be anything."""
        a = {"model_family": "claude-sonnet", "verification_substrate": "human_expert"}
        b = {"model_family": "claude-sonnet", "verification_substrate": "human_expert"}
        _, shared, _ = compute_independence(a, b)
        assert all(d["field"] != "verification_substrate" for d in shared)

    def test_old_dependency_graph_without_the_field_is_unaffected(self):
        """Backward compatibility: a path dict from a dependency_graph.yaml
        written before this dimension existed simply has no key for it --
        must behave exactly like an explicit null, not raise."""
        a = {"model_family": "claude-sonnet", "dataset": "ds-a"}
        b = {"model_family": "claude-sonnet", "dataset": "ds-b"}
        score, _, detail = compute_independence(a, b)
        row = next(d for d in detail if d["dimension"] == "verification_substrate")
        assert row["skipped"] is True
        assert (
            score
            == compute_independence(
                {
                    "model_family": "claude-sonnet",
                    "dataset": "ds-a",
                    "verification_substrate": None,
                },
                {
                    "model_family": "claude-sonnet",
                    "dataset": "ds-b",
                    "verification_substrate": None,
                },
            )[0]
        )

    def test_persists_through_yaml_write_back_with_null_contribution(self):
        """End-to-end: an observer-only row with contribution=None must
        round-trip through _update_score_in_content as YAML `null`, not the
        string "None" or a crash on a mixed-type list."""
        a = {"model_family": "claude-sonnet", "verification_substrate": "simulation"}
        b = {"model_family": "gpt-4", "verification_substrate": "independent_dataset"}
        score, shared, detail = compute_independence(a, b)
        template = (
            "shared_dependencies: []\ndimension_detail: []\n"
            "independence_score: null\nindependence_tier: null\n"
        )
        cov = evidence_coverage(a, b)
        updated = _update_score_in_content(template, score, tier(score, cov), shared, detail, cov)
        assert "verification_substrate" in updated
        assert "observer_only: true" in updated
        assert "contribution: null" in updated
        assert "None" not in updated


# ---------------------------------------------------------------------------
# Inline comments must not turn an UNFILLED field into a "recorded" one
# (skeptic F1, 2026-09-19)
# ---------------------------------------------------------------------------


class TestInlineCommentsDoNotCountAsRecorded:
    """The shipped template writes `model_family: null   # e.g. "claude-sonnet"`.
    Before `_strip_inline_comment`, that raw text was not a null spelling, so an
    unfilled field parsed as a recorded string and a file with ZERO real
    provenance reported evidence_coverage 1.0 / tier HIGH -- the defect the
    coverage change removes, re-entering through the parser."""

    @staticmethod
    def _parse(a_block: str, b_block: str) -> tuple[dict, dict]:
        content = (
            'experiment_id: "20260919-comments"\n'
            "paths:\n  path_a:\n" + a_block + "  path_b:\n" + b_block
        )
        parsed = _parse_yaml_paths(content)
        assert parsed is not None
        return parsed

    def test_commented_null_is_still_null(self):
        a, _ = self._parse('    model_family: null   # e.g. "claude-sonnet", "gpt-4"\n', "")
        assert a["model_family"] is None

    def test_comment_only_value_is_null(self):
        a, _ = self._parse("    dataset:   # to be filled\n", "")
        assert a["dataset"] is None

    def test_commented_real_value_keeps_the_value_not_the_comment(self):
        a, _ = self._parse("    code_commit: abc123   # pinned 2026-09-19\n", "")
        assert a["code_commit"] == "abc123"

    def test_commented_list_is_still_parsed_as_a_list(self):
        a, _ = self._parse("    libraries: [numpy==1.26.0, scipy==1.11.0]  # pinned\n", "")
        assert a["libraries"] == ["numpy==1.26.0", "scipy==1.11.0"]

    def test_commented_empty_list_is_an_empty_list(self):
        a, _ = self._parse("    libraries: []   # e.g. [numpy==1.26.0]\n", "")
        assert a["libraries"] == []

    def test_hash_without_leading_whitespace_is_part_of_the_value(self):
        """YAML: `#` starts a comment only after whitespace."""
        a, _ = self._parse("    retrieval_snapshot: sha256:abc#1\n", "")
        assert a["retrieval_snapshot"] == "sha256:abc#1"

    def test_quoted_value_containing_space_hash_is_preserved(self):
        a, _ = self._parse('    definition_of_metric: "recall # at 5"  # note\n', "")
        assert a["definition_of_metric"] == "recall # at 5"

    def test_single_quoted_escaped_quote_is_not_truncated(self):
        """`'it''s'` must not be cut at the first inner quote (that would give
        `it`, and two different values `'it''s'` / `'it''x'` would then collide
        as "shared"). Same value with and without a trailing comment."""
        with_comment, _ = self._parse("    dataset: 'it''s'  # note\n", "")
        without, _ = self._parse("    dataset: 'it''s'\n", "")
        assert with_comment["dataset"] == without["dataset"] == "it''s"

    def test_double_quoted_backslash_escape_keeps_the_rest_of_the_value(self):
        a, _ = self._parse('    dataset: "a \\" # b"  # note\n', "")
        assert a["dataset"].endswith("# b")  # not cut at the escaped inner quote

    def test_unterminated_quote_is_returned_unchanged_as_before(self):
        """Pre-existing behaviour, deliberately untouched (YAML-invalid input)."""
        a, _ = self._parse('    dataset: "unterminated  # note\n', "")
        assert a["dataset"] == "unterminated  # note"

    def test_the_shipped_template_with_only_experiment_id_filled_is_unknown(self):
        """Skeptic (second pass): every other test here uses hand-written
        comments that merely RESEMBLE the template. This one loads the real
        file, so renaming its placeholder sentinel or changing its comment style
        cannot silently reopen the defect the comment stripping fixed. Only the
        experiment id is filled -- no provenance at all."""
        template = (
            Path(__file__).parent.parent / "experiments" / "_template" / "dependency_graph.yaml"
        )
        content = template.read_text(encoding="utf-8").replace(
            "<YYYYMMDD-short-slug>", "20260919-template-check"
        )
        parsed = _parse_yaml_paths(content)
        assert parsed is not None, "template must parse once its placeholder is replaced"
        a, b = parsed
        score, _, _ = compute_independence(a, b)
        cov = evidence_coverage(a, b)
        assert (score, cov, tier(score, cov)) == (None, 0.0, "UNKNOWN")

    def test_two_unfilled_commented_blocks_are_unknown_not_high(self):
        """The skeptic's exact scenario: the template's commented path_a block
        copy-pasted under path_b (comments differ per field), nothing filled in.
        Old behaviour: coverage 1.0 / tier HIGH on zero real provenance."""
        block_a = (
            '    model_family: null    # e.g. "claude-sonnet"\n'
            "    dataset: null         # dataset A\n"
            "    code_commit: null     # sha\n"
            "    libraries: []         # [numpy==1.26.0]\n"
            "    retrieval_snapshot: null   # snapshot id\n"
            "    definition_of_metric: null # metric\n"
        )
        block_b = (
            '    model_family: null    # e.g. "gpt-4"\n'
            "    dataset: null         # dataset B\n"
            "    code_commit: null     # commit sha\n"
            "    libraries: []         # [sage==9.8]\n"
            "    retrieval_snapshot: null   # snapshot hash\n"
            "    definition_of_metric: null # metric def\n"
        )
        a, b = self._parse(block_a, block_b)
        score, _, _ = compute_independence(a, b)
        cov = evidence_coverage(a, b)
        assert (score, cov, tier(score, cov)) == (None, 0.0, "UNKNOWN")


# ---------------------------------------------------------------------------
# Hook entry point -- the message a human actually sees (2026-09-19)
# ---------------------------------------------------------------------------


class TestHookMainUnknownTier:
    """End to end through main(): an all-unknown pair must produce an UNKNOWN
    warning, never the old "✓ HIGH independence" reassurance -- the only
    consumer of this score is this message."""

    _UNKNOWN_YAML = (
        'experiment_id: "20260919-unknown-check"\n'
        "paths:\n"
        "  path_a:\n"
        "    model_family: null\n"
        "    dataset: null\n"
        "  path_b:\n"
        "    model_family: null\n"
        "    dataset: null\n"
        "shared_dependencies: []\n"
        "dimension_detail: []\n"
        "independence_score: null\n"
        "independence_tier: null\n"
    )
    _KNOWN_YAML = (
        'experiment_id: "20260919-known-check"\n'
        "paths:\n"
        "  path_a:\n"
        "    model_family: claude-sonnet\n"
        "    dataset: dataset-a\n"
        "    code_commit: abc123\n"
        "    libraries: [numpy==1.26.0]\n"
        "    retrieval_snapshot: aaa\n"
        "    definition_of_metric: recall\n"
        "  path_b:\n"
        "    model_family: gpt-4\n"
        "    dataset: dataset-b\n"
        "    code_commit: def456\n"
        "    libraries: [sage==9.8]\n"
        "    retrieval_snapshot: bbb\n"
        "    definition_of_metric: precision\n"
        "shared_dependencies: []\n"
        "dimension_detail: []\n"
        "independence_score: null\n"
        "independence_tier: null\n"
    )

    def _run(self, monkeypatch, tmp_path, capsys, content: str):
        import independence_scorer

        target = tmp_path / "experiments" / "x" / "dependency_graph.yaml"
        target.parent.mkdir(parents=True)
        target.write_text(content, encoding="utf-8")
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(target), "content": content},
        }
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        independence_scorer.main()
        return target, capsys.readouterr().out

    def test_all_unknown_pair_warns_unknown_and_never_claims_high(
        self, monkeypatch, tmp_path, capsys
    ):
        target, out = self._run(monkeypatch, tmp_path, capsys, self._UNKNOWN_YAML)
        assert "UNKNOWN" in out
        assert "HIGH independence" not in out
        written = target.read_text(encoding="utf-8")
        assert _line_value(written, "independence_score") == "null"
        assert _line_value(written, "independence_tier") == "UNKNOWN"
        assert _line_value(written, "evidence_coverage") == "0.0"

    def test_fully_recorded_disjoint_pair_still_reports_high(self, monkeypatch, tmp_path, capsys):
        """Positive control: the fix must not turn every pair into UNKNOWN."""
        target, out = self._run(monkeypatch, tmp_path, capsys, self._KNOWN_YAML)
        assert "HIGH independence" in out
        written = target.read_text(encoding="utf-8")
        assert _line_value(written, "independence_score") == "1.0"
        assert _line_value(written, "independence_tier") == "HIGH"
        assert _line_value(written, "evidence_coverage") == "1.0"
