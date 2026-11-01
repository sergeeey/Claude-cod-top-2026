"""Contract tests for boyko-claim-decomposer (audit 2026-11-01, P1 fixes)."""

from pathlib import Path

SKILL = (Path(__file__).resolve().parents[1] / "skills" / "core" / "boyko-claim-decomposer" / "SKILL.md").read_text(encoding="utf-8")


def test_atomicity_is_independent_verifiability_not_conjunction_splitting():
    assert "Атом — независимо проверяемое утверждение" in SKILL
    assert '"И" не означает автоматического разбиения' in SKILL


def test_definitional_load_bearing_atoms_are_not_discarded():
    assert "НЕ выносить из анализа" in SKILL
    assert "OPERATIONALIZATION_REQUIRED" in SKILL


def test_typed_dependency_edges_and_source_span_are_specified():
    for rel in ("REQUIRES", "DEFINES", "CAUSES", "MEASURES", "IMPLEMENTS", "CONFLICTS"):
        assert rel in SKILL, rel
    assert "SOURCE_SPAN" in SKILL


def test_cluster_contradiction_check_exists_after_pairwise():
    assert "Кластерная проверка" in SKILL
    assert SKILL.index("Кластерная проверка") < SKILL.index("## Шаг 5 — Recomposition")
    assert "x+y=1" in SKILL


def test_structure_and_evidence_status_are_separate():
    assert "STRUCTURE: WELL_FORMED" in SKILL and "EVIDENCE: VERIFIED" in SKILL
    assert "EVIDENCE = NOT_CHECKED" in SKILL


def test_minimal_repair_comes_before_kill():
    assert "Минимальная правка перед KILL и PIVOT" in SKILL
    assert SKILL.index("Минимальная правка перед KILL") < SKILL.index("CLAIM_STATUS:")
