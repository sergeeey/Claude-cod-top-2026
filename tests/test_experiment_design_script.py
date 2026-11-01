"""Regression tests for skills/extensions/experiment-design/scripts/design_experiments.py.

Each test pins one defect found in the 2026-11-01 audit of this script.
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "extensions"
    / "experiment-design"
    / "scripts"
    / "design_experiments.py"
)


@pytest.fixture(scope="module")
def dx():
    spec = importlib.util.spec_from_file_location("design_experiments", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_call_run_count_unchanged(dx):
    # 9 grid configs + 4 ablations + 1 baseline placeholder, x 1 dataset x 3 seeds = 42
    design = dx.generate_design({"method": "x"})
    assert design["estimated_total_runs"] == 42


@pytest.mark.parametrize("bad", [-2, 0, "3", True, 2.5, None])
def test_invalid_num_seeds_rejected(dx, bad):
    with pytest.raises(dx.PlanError):
        dx.generate_design({"num_seeds": bad})


def test_empty_hyperparameter_list_rejected(dx):
    with pytest.raises(dx.PlanError):
        dx.generate_design({"hyperparameter_grid": {"lr": []}})


def test_empty_grid_falls_back_and_warns(dx):
    design = dx.generate_design({"hyperparameter_grid": {}})
    assert design["hyperparameter_grid_source"] == "default"
    assert any("default 2-parameter grid" in w for w in design["warnings"])


def test_duplicate_components_rejected(dx):
    with pytest.raises(dx.PlanError):
        dx.generate_design({"components": ["A", "A"]})


def test_empty_components_rejected(dx):
    with pytest.raises(dx.PlanError):
        dx.generate_design({"components": []})


def test_unknown_task_type_rejected(dx):
    with pytest.raises(dx.PlanError, match="unknown task_type"):
        dx.generate_design({"task_type": "banana"})


def test_statistical_test_is_recommendation_not_performed(dx):
    design = dx.generate_design({"num_seeds": 5})
    protocol = design["evaluation_protocol"]
    assert protocol["recommended_test"] == "paired_ttest"
    assert protocol["test_performed"] is False
    assert "statistical_test" not in protocol


def test_missing_datasets_and_baselines_recorded(dx):
    design = dx.generate_design({"method": "x"})
    joined = " ".join(design["warnings"])
    assert "no datasets" in joined
    assert "no baselines" in joined


def test_markdown_renders_warnings(dx):
    text = dx.format_markdown(dx.generate_design({"method": "x"}))
    assert "## Warnings" in text
    assert "Recommended test (not run)" in text
