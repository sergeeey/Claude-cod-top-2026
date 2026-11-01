"""Contract tests for boyko-hypothesis-revival (Skill Audit 2.1 №10, P0/P1 fixes, 2026-11-01)."""

import json
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "extensions" / "boyko-hypothesis-revival"
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
PLUGIN = json.loads((SKILL_DIR / "plugin.json").read_text(encoding="utf-8"))


def test_plugin_name_and_russian_description():
    assert PLUGIN["name"] == "boyko-hypothesis-revival"
    assert any("а" <= ch <= "я" for ch in PLUGIN["description"].lower())


def test_sleeping_beauty_is_not_detected_by_current_citation_sort():
    # P0: cited_by_count is the total count today, not the first 10 years.
    assert "sort=cited_by_count:asc" not in SKILL
    assert "`cited_by_count` — это общее число цитирований на сегодня" in SKILL
    assert "`TRAJECTORY_UNVERIFIED`" in SKILL


def test_historical_status_comes_before_any_modern_enabler():
    assert "### Шаг 2.5 — Исторический статус ДО enabler" in SKILL
    assert "Подбирать ENABLER_NOW" in SKILL
    assert "`evidence_strength`" in SKILL


def test_revival_is_separated_from_reinvention_and_tool_application():
    assert "## Revival ≠ переизобретение ≠ применение инструмента" in SKILL
    assert "`MODERN_REINVENTION_NOT_REVIVAL`" in SKILL
    assert "`TOOL_APPLICATION_NOT_REVIVAL`" in SKILL


def test_abstract_is_not_read_as_plaintext_field():
    assert "w.get('abstract','')" not in SKILL
    assert "abstract_inverted_index" in SKILL


def test_openalex_key_requirement_is_stated_and_unverified_marked():
    assert "API key" in SKILL
    assert "[UNVERIFIED-SOURCE]" in SKILL
