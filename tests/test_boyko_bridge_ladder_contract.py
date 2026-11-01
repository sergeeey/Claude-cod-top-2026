"""Contract tests for boyko-bridge-ladder (Skill Audit 2.1 №1 audit, P0/P1, 2026-11-01)."""

from pathlib import Path

SKILL = (Path(__file__).resolve().parents[1] / "skills" / "extensions" / "boyko-bridge-ladder" / "SKILL.md").read_text(encoding="utf-8")


def test_rival_and_common_cause_check_exists_before_classification():
    assert "## Шаг 2b — Rival и common-cause проверка" in SKILL
    assert "`A ← C → B`" in SKILL
    assert SKILL.index("## Шаг 2b") < SKILL.index("## Шаг 3 — Классифицировать")


def test_every_bridge_has_prediction_if_false_and_boundary():
    for field in ("prediction_if_true", "prediction_if_false", "boundary_condition"):
        assert field in SKILL, field
    assert "Мост без `prediction_if_false` — это метафора" in SKILL


def test_reversal_test_is_present_and_ordered():
    assert "## Шаг 5b — Reversal test" in SKILL
    assert SKILL.index("## Шаг 5b") < SKILL.index("## Шаг 6 — Irreducible Core")
