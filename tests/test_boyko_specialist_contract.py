"""Contract tests for skills/extensions/boyko-specialist (audit №9, 2026-11-01).

Pins v1.3: status vocabulary instead of 'not found = open', three verification levels,
scale rule for specialist_score, search log, privacy gate, and a portable lifecycle fixture.
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "extensions" / "boyko-specialist"


@pytest.fixture(scope="module")
def skill_md() -> str:
    return (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


def test_versions_are_1_3(skill_md):
    plugin = json.loads((SKILL_DIR / "plugin.json").read_text(encoding="utf-8"))
    assert plugin["version"] == "1.3.0"
    assert "**Version:** 1.3.0" in skill_md


def test_verdict_uses_status_vocabulary(skill_md):
    for status in ("SOLVED", "PARTIAL", "NOT_FOUND_IN_SEARCH", "OPEN_WITH_EVIDENCE", "UNKNOWN"):
        assert status in skill_md
    assert "«не найдено» больше не означает «открыто»" in skill_md


def test_three_verification_levels(skill_md):
    for level in ("identity_verified", "contribution_verified", "applicability_verified"):
        assert level in skill_md


def test_score_scale_rule(skill_md):
    assert "Шкалы (v1.3" in skill_md
    assert "рейтинг объявляется неустойчивым" in skill_md


def test_search_log_and_privacy_gate(skill_md):
    assert "Журнал поиска (v1.3" in skill_md
    assert "Privacy-gate перед WebSearch (v1.3)" in skill_md


def test_lifecycle_fixture_is_repo_relative():
    text = (ROOT / "skills" / "lifecycle_tests" / "boyko-specialist.yaml").read_text(encoding="utf-8")
    assert 'skill_file: "skills/extensions/boyko-specialist/SKILL.md"' in text
    assert "C:/Users" not in text
