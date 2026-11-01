"""Contract tests for skills/extensions/boyko-leverage-map (audit №3, 2026-11-01).

Pins the v1.1 gates added after the audit: Goal Gate, Causal Loop Contract,
Intervention Test, Evidence Registry, and the plugin/skill name match.
"""

import json
import re
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "extensions" / "boyko-leverage-map"


@pytest.fixture(scope="module")
def skill_md() -> str:
    return (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def plugin() -> dict:
    return json.loads((SKILL_DIR / "plugin.json").read_text(encoding="utf-8"))


def test_plugin_name_matches_skill_name(skill_md, plugin):
    skill_name = re.search(r"^name:\s*(\S+)", skill_md, re.MULTILINE).group(1)
    assert plugin["name"] == skill_name == "boyko-leverage-map"


def test_goal_gate_present(skill_md):
    assert "Goal Gate" in skill_md
    assert "цель не задана" in skill_md
    assert "**KPI:**" in skill_md


def test_causal_loop_contract_present(skill_md):
    assert "Causal Loop Contract" in skill_md
    assert "A → B | знак:" in skill_md
    assert "тип не определён" in skill_md


def test_intervention_test_present(skill_md):
    assert "Intervention Test" in skill_md
    assert "Критерий остановки" in skill_md
    assert "[HYPOTHESIS]" in skill_md


def test_evidence_registry_present(skill_md):
    assert "Evidence Registry" in skill_md
    assert "общая первопричина" in skill_md


def test_hard_rules_six_and_seven_numbered(skill_md):
    assert "6. **Goal Gate" in skill_md
    assert "7. **Intervention Test" in skill_md


def test_macro_locality_reference_is_marked_external(skill_md):
    assert "НЕ входит в дерево репозитория" in skill_md
