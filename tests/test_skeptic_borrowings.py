"""Skill Audit 2.1 №2 (skeptic, 2026-11-01): Pareto borrowings are present in SKILL.md.

Pins: steelman after attacks (LifeOS RedTeam), claim→evidence→finding chain (Kalaris),
outcome vocabulary with the source's own labels stated (Nature Paper).
"""

from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent / "skills" / "extensions" / "skeptic" / "SKILL.md"


@pytest.fixture(scope="module")
def text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_block_present(text):
    assert "## Заимствования по Парето (Skill Audit 2.1 №2" in text


def test_steelman_rule(text):
    assert "Steelman обязателен" in text
    assert "сильнейшее контрвозражение" in text


def test_claim_evidence_finding_chain(text):
    for field in ("`claim_id`", "`evidence_id`", "`finding_id`"):
        assert field in text


def test_outcome_vocabulary(text):
    for verdict in ("FALSIFIED", "WEAKENED", "SUPPORTED_WITHIN_SCOPE", "INCONCLUSIVE", "BLOCKED"):
        assert verdict in text
    assert "CONFIRMED / PARTIAL / REJECTED / BLOCKED" in text


def test_sources_are_named(text):
    for src in ("LifeOS RedTeam", "Kalaris ARA Rigor Reviewer", "Nature Paper claim-source-verification"):
        assert src in text
