"""Contract tests for skills/extensions/boyko-ripple (audit №7, 2026-11-01).

Pins v1.1: the impact_edge contract between rings, three separate confidences, the numeric
ranking with a stability check, the MDE refusal without parameters, plugin/skill name match.
"""

import json
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "extensions" / "boyko-ripple"


@pytest.fixture(scope="module")
def skill_md() -> str:
    return (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


def test_plugin_name_matches_skill_and_version():
    plugin = json.loads((SKILL_DIR / "plugin.json").read_text(encoding="utf-8"))
    assert plugin["name"] == "boyko-ripple"
    assert plugin["version"] == "1.1.0"
    assert any("Ѐ" <= ch <= "ӿ" for ch in plugin["description"])


def test_impact_edge_contract_present(skill_md):
    assert "Контракт связи между кольцами (impact_edge, v1.1" in skill_md
    assert "направление (`+`, `−` или `0`)" in skill_md
    assert "Кольцо описывает область **потенциального** воздействия" in skill_md


def test_three_separate_confidences(skill_md):
    for field in ("`finding_confidence`", "`causal_confidence`", "`effect_confidence`"):
        assert field in skill_md
    assert "Ярлык HIGH с находки на эффект не переносится" in skill_md


def test_numeric_ranking_formula_and_coefficients(skill_md):
    assert "priority = value × coef(effect_confidence) / test_cost_days" in skill_md
    assert "HIGH 0.9, MEDIUM 0.5, LOW 0.2, SPECULATIVE 0.05" in skill_md
    assert "порядок неустойчив: победитель не назван" in skill_md
    assert "scripts/rank_ripple.py" in skill_md


def test_mde_refuses_without_parameters(skill_md):
    assert "MDE: недостаточно данных" in skill_md
    assert "базовая доля" in skill_md


def test_status_points_to_registry(skill_md):
    assert "Статус-источник истины — `skills/registry.yaml`" in skill_md


def test_ranking_script_exists():
    assert (SKILL_DIR / "scripts" / "rank_ripple.py").is_file()
