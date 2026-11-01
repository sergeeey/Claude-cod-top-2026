"""Contract tests for skills/extensions/boyko-toolcheck (audit №10, 2026-11-01).

Pins v1.1: readiness levels, per-tool check contract, execution limits, redaction, the
structured result with an overall verdict, two rules borrowed from actual (flag check via
--help, hand off interactive login), plugin name and Russian description.
"""

import json
import re
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "extensions" / "boyko-toolcheck"
CYRILLIC = re.compile(r"[а-яА-ЯёЁ]")


@pytest.fixture(scope="module")
def skill_md() -> str:
    return (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


def test_plugin_name_version_and_language():
    plugin = json.loads((SKILL_DIR / "plugin.json").read_text(encoding="utf-8"))
    assert plugin["name"] == "boyko-toolcheck"
    assert plugin["version"] == "1.1.0"
    assert CYRILLIC.search(plugin["description"])


def test_readiness_levels_listed(skill_md):
    assert "## Уровни готовности (v1.1" in skill_md
    for level in ("DISCOVERED", "STARTS", "AUTHENTICATED", "FUNCTIONAL", "WORKFLOW_READY"):
        assert f"`{level}`" in skill_md
    assert "`CLI_START_OK` — не `AUTH_OK` и не `WORKFLOW_OK`" in skill_md


def test_codex_version_is_only_start_level(skill_md):
    assert "уровень STARTS" in skill_md
    assert "codex login status" in skill_md


def test_per_tool_contract_fields(skill_md):
    assert "## Контракт проверки (на каждый инструмент)" in skill_md
    for field in ("безопасная команда", "оракул", "негативные признаки", "условие остановки"):
        assert field in skill_md


def test_execution_limits(skill_md):
    assert "## Ограничения исполнения (v1.1)" in skill_md
    assert "Таймаут на команду" in skill_md
    assert "не подставлять строкой в shell" in skill_md
    assert "передать шаг человеку" in skill_md


def test_flag_check_borrowed_from_actual(skill_md):
    assert "<tool> <sub> --help" in skill_md
    assert "actual CLI companion" in skill_md


def test_redaction_section_and_script(skill_md):
    assert "## Редактирование вывода (v1.1)" in skill_md
    assert "scripts/toolcheck.py" in skill_md
    assert (SKILL_DIR / "scripts" / "toolcheck.py").is_file()


def test_result_requires_overall_verdict(skill_md):
    assert "итог: PARTIAL" in skill_md
    assert "`PASS` только при `WORKFLOW_READY`" in skill_md
