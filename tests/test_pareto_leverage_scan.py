"""Skill Audit 2.1 №1: pareto-leverage-scan (2026-11-01).

Pins the fixes: p95 values are not summed into shares (P0 eval), leverage is computed
for all admissible options not only the Pareto core (P1), and the 80% measure is compared
with a uniform distribution (P1).
"""

import json
from pathlib import Path

import pytest
import yaml

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "extensions" / "pareto-leverage-scan"


@pytest.fixture(scope="module")
def skill_md() -> str:
    return (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


def test_plugin_version_bumped():
    assert json.loads((SKILL_DIR / "plugin.json").read_text(encoding="utf-8"))["version"] == "1.1.0"


def test_additivity_gate_present(skill_md):
    assert "Gate аддитивности (v1.1" in skill_md
    assert "перцентили (p95, p99)" in skill_md


def test_leverage_not_restricted_to_pareto_core(skill_md):
    assert "для ВСЕХ допустимых вариантов" in skill_md
    assert "две независимые сортировки" in skill_md


def test_concentration_measure_vs_uniform(skill_md):
    assert "Мера концентрации (v1.1)" in skill_md
    assert "равномерным распределением" in skill_md


def test_p95_eval_no_longer_rewards_summed_shares():
    case = yaml.safe_load((SKILL_DIR / "evals" / "pareto-vs-plain-list" / "case.yaml").read_text(encoding="utf-8"))
    outcome = case["expected_outcome"]
    assert "sums to 1765" not in outcome
    assert "non-additive" in outcome


def test_p95_grader_fails_summed_shares():
    text = (SKILL_DIR / "evals" / "pareto-vs-plain-list" / "graders" / "01-computes-raw-shares.md").read_text(encoding="utf-8")
    assert "does NOT compute" in text
    assert "FAILS this check" in text
