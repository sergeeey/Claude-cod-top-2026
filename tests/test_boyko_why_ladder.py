"""Tests for skills/extensions/boyko-why-ladder (audit №12, 2026-11-01).

Pins v1.1: two-layer DERIVED/premise rule (P0), local defect types, essentiality-based
Depth Guard, stop kinds (P1), 5-Whys reverse check, regression cases coverage.
"""

import json
import re
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "extensions" / "boyko-why-ladder"


@pytest.fixture(scope="module")
def skill_md() -> str:
    return (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def cases() -> dict:
    return json.loads((SKILL_DIR / "evals" / "regression-cases.json").read_text(encoding="utf-8"))


def test_versions_and_plugin_name():
    plugin = json.loads((SKILL_DIR / "plugin.json").read_text(encoding="utf-8"))
    assert plugin["name"] == "boyko-why-ladder"
    assert plugin["version"] == "1.1.0"
    assert 'version: "1.1.0"' in (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


def test_two_layers_documented(skill_md):
    assert "**Слой A, вывод:**" in skill_md
    assert "**Слой B, предпосылка:**" in skill_md
    assert "Удаление предпосылки меняет статус предпосылки" in skill_md


def test_derived_example_has_no_fitted_verdict(skill_md):
    assert "x > 0" in skill_md
    assert "не делают вывод FITTED" in skill_md


def test_local_defect_types(skill_md):
    for defect in ("FITTED", "TAUTOLOGICAL", "CIRCULAR_DEPENDENCY", "UNJUSTIFIED_PREMISE"):
        assert f"**{defect}**" in skill_md
    assert "Тавтология — не подгонка" in skill_md


def test_depth_guard_essentiality_and_heuristic(skill_md):
    assert "существенность нерешённого звена" in skill_md
    assert "`[HEURISTIC]`" in skill_md


def test_stop_kinds(skill_md):
    for kind in ("DEFINITIONAL_STOP", "THEOREM_STOP", "EMPIRICAL_STOP", "PRAGMATIC_STOP"):
        assert f"`{kind}`" in skill_md
    assert "не закрывает выбор" in skill_md


def test_reverse_check_from_five_whys(skill_md):
    assert "Обратная проверка (из 5-Whys" in skill_md
    assert "должен исчезнуть" in skill_md


def test_regression_cases_cover_all_verdicts(cases):
    coverage = set(cases["coverage"])
    for verdict in ("FOUNDATIONAL_STOP", "CIRCULAR", "ONGOING_REGRESS"):
        assert verdict in coverage
    assert len(cases["cases"]) >= 7


def test_every_case_has_a_must_not(cases):
    for case in cases["cases"]:
        assert case["must_not"], case["id"]
        assert re.match(r"^R\d+-", case["id"])


def test_derived_under_premise_case_is_present(cases):
    ids = {c["id"] for c in cases["cases"]}
    assert "R1-derived-under-premise" in ids
