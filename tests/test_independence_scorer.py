"""Tests for independence_scorer.py.

Positive control (mandatory — per patterns.md [AVOID] validation theater):
  compute_independence must give score=0.0 when both paths are identical
  and score=1.0 when paths share nothing (all non-null fields differ).
  These are structural invariants, not optional coverage.
"""

import json
import sys
from pathlib import Path

import yaml

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
        updated = _update_score_in_content(self._template(), score, tier(score), shared, detail)
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
        updated = _update_score_in_content(template, score, tier(score), shared, detail)
        assert "verification_substrate" in updated
        assert "observer_only: true" in updated
        assert "contribution: null" in updated
        assert "None" not in updated
