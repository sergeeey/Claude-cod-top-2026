"""Contract tests for skills/extensions/boyko-triangle-audit (audit №11, 2026-11-01).

Pins v1.1: the guard description is accurate, claim-evidence binding with verbatim spans,
discriminating observation for the explanation vertex, independence axes, PROCESS_COMPLETE.
"""

import json
import re
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "extensions" / "boyko-triangle-audit"


@pytest.fixture(scope="module")
def skill_md() -> str:
    return (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


def test_versions_are_1_1_0(skill_md):
    assert 'version: "1.1.0"' in skill_md
    assert json.loads((SKILL_DIR / "plugin.json").read_text(encoding="utf-8"))["version"] == "1.1.0"


def test_outdated_guard_wording_is_gone(skill_md):
    assert "проверяет только \"поле не пустое\"" not in skill_md
    assert "механически проверяет 'поле не пустое'" not in skill_md
    assert "sealed holdout" in skill_md


def test_verbatim_span_and_script(skill_md):
    assert "source_span" in skill_md and "дословная подстрока" in skill_md
    assert "scripts/check_spans.py" in skill_md
    assert (SKILL_DIR / "scripts" / "check_spans.py").is_file()


def test_discriminating_observation_required(skill_md):
    assert "Различающее наблюдение (v1.1" in skill_md
    assert "не выше `present-weak`" in skill_md


def test_independence_axes(skill_md):
    assert "Независимость (v1.1)" in skill_md
    for axis in ("исполнитель", "данные", "метод", "кодовый путь", "общие предпосылки"):
        assert axis in skill_md


def test_process_complete_not_claim_validated(skill_md):
    assert "PROCESS_COMPLETE" in skill_md
    assert "CLAIM_VALIDATED" in skill_md
    assert re.search(r"ПОЛНЫЙ ЦИКЛ — все 4", skill_md) is None
