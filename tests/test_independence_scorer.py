"""Tests for independence_scorer.py.

Positive control (mandatory — per patterns.md [AVOID] validation theater):
  compute_independence must give score=0.0 when both paths are identical
  and score=1.0 when paths share nothing (all non-null fields differ).
  These are structural invariants, not optional coverage.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from independence_scorer import (
    _library_major_set,
    _normalise,
    _parse_yaml_paths,
    _update_score_in_content,
    _yaml_scalar,
    compute_independence,
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

    def test_all_null_fields_give_one(self):
        """No active dimensions → normalised score = 1.0 (unknown = not shared)."""
        a = {"model_family": None, "dataset": None}
        b = {"model_family": None, "dataset": None}
        score, shared, detail = compute_independence(a, b)
        assert score == 1.0

    def test_score_range(self):
        a = {"model_family": "claude-sonnet", "dataset": "ds-a"}
        b = {"model_family": "claude-sonnet", "dataset": "ds-b"}
        score, _, _ = compute_independence(a, b)
        assert 0.0 <= score <= 1.0

    def test_one_null_one_filled_not_shared(self):
        """Null in one path → can't prove overlap → difference."""
        a = {"model_family": "claude-sonnet"}
        b = {"model_family": None}
        score, shared, _ = compute_independence(a, b)
        # model_family contributes its full weight (not shared)
        assert score > 0.0
        assert all(d["field"] != "model_family" for d in shared)


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
    def test_high_at_threshold(self):
        assert tier(0.70) == "HIGH"

    def test_high_above(self):
        assert tier(1.0) == "HIGH"

    def test_medium_at_threshold(self):
        assert tier(0.40) == "MEDIUM"

    def test_medium_below_high(self):
        assert tier(0.69) == "MEDIUM"

    def test_low_below_medium(self):
        assert tier(0.39) == "LOW"

    def test_low_at_zero(self):
        assert tier(0.0) == "LOW"


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
        updated = _update_score_in_content(self._template(), score, tier(score), shared, detail)
        assert "model_family" in updated
        assert "libraries" in updated
        assert f"independence_score: {score}" in updated
