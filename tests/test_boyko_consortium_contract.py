"""Contract tests for skills/extensions/boyko-scientific-consortium (audit №8, 2026-11-01).

Pins v1.3: the causal identification gate (causal map is not a DAG), the Micro rule that
forbids confirming a causal effect, the independence marker, and the version/status pointer.
Lifecycle fixture behaviour is covered in tests/test_skill_lifecycle_check.py.
"""

import json
from pathlib import Path

import pytest

SKILL_DIR = (
    Path(__file__).resolve().parent.parent / "skills" / "extensions" / "boyko-scientific-consortium"
)


@pytest.fixture(scope="module")
def skill_md() -> str:
    return (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


def test_versions_are_1_3(skill_md):
    plugin = json.loads((SKILL_DIR / "plugin.json").read_text(encoding="utf-8"))
    assert plugin["version"] == "1.4.0"
    assert 'version: "1.4"' in skill_md


def test_causal_map_is_not_called_a_dag(skill_md):
    assert "а **не** DAG" in skill_md
    assert "causal_identification_gate" in skill_md


def test_identification_gate_has_four_parts(skill_md):
    assert "causal_identification_gate (v1.3" in skill_md
    for part in (
        "Рёбра DAG явно",
        "Циклы",
        "Стратегия идентификации",
        "Четыре условия estimand-ops",
    ):
        assert part in skill_md
    assert "гипотеза, gate не пройден" in skill_md


def test_micro_mode_cannot_confirm_causal_effect(skill_md):
    assert "**Причинный эффект не подтверждает:**" in skill_md


def test_independence_section_and_markers(skill_md):
    assert "## Независимость проверки (v1.3" in skill_md
    assert "independence: second_pass" in skill_md
    assert "independence: single_pass" in skill_md
    assert "[LOW_INDEPENDENCE]" in skill_md


def test_status_points_to_registry(skill_md):
    assert "Статус-источник истины — `skills/registry.yaml`" in skill_md
