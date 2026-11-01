"""Contract tests for sci-evidence (Skill Audit 2.1 №5, P0/P1 fixes, 2026-11-01).

The skill is prose, so these tests pin the wording of the rules that the audit found
contradictory or unsupported. Each test names the defect it guards against.
"""

from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "skills" / "extensions" / "sci-evidence"
SKILL = (BASE / "SKILL.md").read_text(encoding="utf-8")
FALSIFY = (BASE / "references" / "falsify.md").read_text(encoding="utf-8")
BUILD = (BASE / "references" / "build.md").read_text(encoding="utf-8")


# --- P0: one verdict rule, no counting of "high" worlds --------------------------------


def test_skill_no_longer_stops_on_two_high_worlds():
    # SKILL.md said STOP, falsify.md said PIVOT for the same condition: a contradiction.
    assert "≥2 миров" not in SKILL
    assert "references/falsify.md" in SKILL


def test_falsify_has_no_world_counting_rules():
    assert "≥2 мира с вероятностью" not in FALSIFY
    assert "≥3 мира с вероятностью" not in FALSIFY


def test_verdict_rules_are_ordered_and_kill_confirmed_comes_first():
    section = FALSIFY[FALSIFY.index("**Правила вердикта") :]
    first = section.index("1. ≥1 kill-условие ВЫПОЛНЕНО")
    second = section.index("2. Иначе")
    third = section.index("3. Иначе → **ПРОДОЛЖИТЬ**")
    assert first < second < third
    assert "Подсчёт миров здесь не участвует" in section


def test_fragility_index_is_diagnostic_not_universal_kill():
    assert "независимо от p-value" not in FALSIFY
    assert "**Диагностика:**" in FALSIFY


def test_auc_threshold_is_not_a_confound_verdict():
    assert "AUC > 0.90" not in FALSIFY
    assert "это само по себе не доказывает confound" in FALSIFY


# --- P1: estimand timing and Consilience semantics -------------------------------------


def test_estimand_timing_distinguishes_prospective_and_retrospective():
    assert "**Проспективный анализ**" in SKILL
    assert "**Ретроспективный анализ**" in SKILL
    assert "RETROSPECTIVE / POST-HOC" in SKILL


def test_consilience_is_declared_a_heuristic_not_truth_or_publication_readiness():
    assert "Consilience Score — эвристика покрытия, а не вероятность истинности" in SKILL
    assert "не сертификат готовности к публикации" in SKILL
    assert "Эвристика покрытия путей" in BUILD


def test_arbiter_is_not_described_as_bayesian():
    assert "Байесовский арбитраж" not in SKILL
    assert "не байесовская модель" in SKILL
