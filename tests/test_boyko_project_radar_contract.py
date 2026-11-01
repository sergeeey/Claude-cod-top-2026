"""Contract tests for skills/extensions/boyko-project-radar (audit №6, 2026-11-01).

Pins v1.1: explicit availability check for the TASK executor, the finding registry with
HEAD-verification status, the gate before P1/P2 output, the coverage-state matrix, and a
status line that points to the registry instead of contradicting it.
"""

import json
import re
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "extensions" / "boyko-project-radar"


@pytest.fixture(scope="module")
def skill_md() -> str:
    return (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


def test_plugin_version_is_1_1_0():
    plugin = json.loads((SKILL_DIR / "plugin.json").read_text(encoding="utf-8"))
    assert plugin["version"] == "1.1.0"


def test_task_mode_checks_executor_availability(skill_md):
    assert "Проверка доступности исполнителя (v1.1" in skill_md
    assert "TASK: исполнитель boyko-agent не доступен в этой установке" in skill_md


def test_finding_registry_fields_and_statuses(skill_md):
    assert "6. **Реестр находок (v1.1" in skill_md
    for field in ("`id`", "`scanner`", "`severity`", "`evidence`", "`verified_at`", "`HEAD`"):
        assert field in skill_md
    for status in ("HEAD_VERIFIED", "HISTORICAL", "UNVERIFIED"):
        assert status in skill_md


def test_gate_before_p1_p2_output(skill_md):
    assert "7. **Gate перед выводом P1/P2 (v1.1)" in skill_md
    assert "в «Мой выбор» не попадает" in skill_md


def test_coverage_matrix_has_five_distinct_states(skill_md):
    assert "Матрица покрытия (v1.1" in skill_md
    for state in ("`checked`", "`finding`", "`not_applicable`", "`unknown`", "`skipped`"):
        assert state in skill_md
    assert "Слепое место = `unknown` или `skipped`" in skill_md


def test_status_points_to_registry_not_text(skill_md):
    assert "Источник истины по статусу — `skills/registry.yaml`" in skill_md


def test_registry_entry_still_dogfooded():
    registry = (Path(__file__).resolve().parent.parent / "skills" / "registry.yaml").read_text(
        encoding="utf-8"
    )
    block = re.search(r"- name: boyko-project-radar\n(?:    .*\n)+", registry)
    assert block is not None
    assert "maturity: dogfooded" in block.group(0)
