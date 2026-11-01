"""Consistency tests for skills/extensions/boyko-knowledge-audit (audit №3, 2026-11-01).

The skill had a Maxwell-equations contradiction: the Tie-breaker rule in SKILL.md said a
canonical, uncontested law survives the adversarial check, while the worked example and
the eval said it must be downgraded to Level 0. These tests pin the single policy.
"""

import json
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent / "skills" / "extensions" / "boyko-knowledge-audit"


@pytest.fixture(scope="module")
def skill_md() -> str:
    return (SKILL / "SKILL.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def worked_example() -> str:
    return (SKILL / "references" / "worked-example.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def maxwell_eval() -> dict:
    data = json.loads((SKILL / "evals" / "evals.json").read_text(encoding="utf-8"))
    entries = data["evals"] if isinstance(data, dict) else data
    matches = [e for e in entries if "Maxwell" in e["prompt"]]
    assert len(matches) == 1
    return matches[0]


def test_tie_breaker_rule_exists_in_skill(skill_md):
    assert "Tie-breaker rule" in skill_md
    assert "канонический" in skill_md


def test_eval_expects_maxwell_to_survive_not_downgrade(maxwell_eval):
    expected = maxwell_eval["expected_output"]
    assert "SURVIVES" in expected
    assert (
        "downgrade to Level 0 with reasoning that the text provides no in-text evidence"
        not in expected
    )


def test_eval_still_downgrades_the_deductive_claim(maxwell_eval):
    expected = maxwell_eval["expected_output"]
    assert "follows deductively" in expected
    assert "downgrade to Level 0 since no proof sketch" in expected


def test_worked_example_maxwell_survives(worked_example):
    assert "Downgrade fails — claim survives" in worked_example
    assert "Level 3-P → **Level 0** (`EXTERNAL_NOT_USED_TO_UPGRADE`)" not in worked_example


def test_worked_example_appropriateness_is_two_thirds(worked_example):
    assert "/ 3 = 0.67" in worked_example
    assert "/ 3 = 0.33" not in worked_example


def test_rigor_score_split_documented(skill_md):
    assert "audit_quality" in skill_md
    assert "text_evidence" in skill_md
    assert "in_text_direct_rate" in skill_md


def test_independence_marker_documented(skill_md):
    assert "independence: second_pass" in skill_md
    assert "independence: single_pass" in skill_md
    assert "[LOW_INDEPENDENCE]" in skill_md
