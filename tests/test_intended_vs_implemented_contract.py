"""Contract tests for intended-vs-implemented (Skill Audit 2.1 №6, P0/P1 fixes, 2026-11-01).

The skill is prose, so these tests pin the wording the audit found missing: the reverse
Code -> Docs pass, the evidence ladder, source authority, and the full status set.
"""

import re
from pathlib import Path

SKILL = (
    Path(__file__).resolve().parents[1]
    / "skills" / "extensions" / "intended-vs-implemented" / "SKILL.md"
).read_text(encoding="utf-8")


def _frontmatter() -> str:
    m = re.match(r"^---\n(.*?)\n---", SKILL, re.DOTALL)
    assert m, "SKILL.md must start with frontmatter"
    return m.group(1)


def test_description_is_russian():
    # Audit P1: the description began in English.
    assert re.search(r"[А-Яа-яЁё]", _frontmatter())
    assert "Catches high-value bugs" not in _frontmatter()


def test_name_unchanged():
    assert re.search(r"^name: intended-vs-implemented$", _frontmatter(), re.MULTILINE)


def test_reverse_pass_code_to_docs_exists():
    # Audit P0: the skill only traversed Docs -> Code, so undocumented behaviour was invisible.
    assert "### Шаг 2b — Обратный проход: Code → Docs" in SKILL
    assert "UNDOCUMENTED_BEHAVIOR" in SKILL


def test_evidence_ladder_levels_are_defined():
    for level in ("L0 TEXT_MATCH", "L1 CODE_PRESENT", "L2 WIRED", "L3 EXECUTED", "L4 ADVERSARIAL"):
        assert level in SKILL, level


def test_static_presence_is_not_enough_for_security_match():
    # Audit P0: code existing was treated as the boundary being enforced.
    assert "статус `MATCH` требует минимум L3" in SKILL
    assert "L1 и L2 — недостаточно" in SKILL
    assert "Запрещено:** статус `MATCH` для security/privacy/access-control claim на уровне L0–L2" in SKILL


def test_source_authority_hierarchy_is_ordered():
    section = SKILL[SKILL.index("**Авторитет источников") :]
    order = ["внешняя спецификация", "ADR", "публичная API-спецификация", "README", "docstring", "inline-комментарий"]
    positions = [section.index(s) for s in order]
    assert positions == sorted(positions)


def test_tests_count_as_intent_only_when_they_fix_a_public_contract():
    assert "Тест считается источником намерения только если он явно фиксирует публичный контракт" in SKILL


def test_conflicting_sources_are_contradictory_intent_not_compared():
    assert "статус `CONTRADICTORY_INTENT`" in SKILL
    assert "Такой claim не сравнивается с кодом" in SKILL


def test_non_active_claims_are_unverifiable_outside_their_condition():
    assert "STATUS: [active | planned | experimental | deprecated | flag:<name>]" in SKILL
    assert "Вне условия результат — `UNVERIFIABLE`" in SKILL


def test_full_status_set_is_declared():
    for status in ("MATCH", "UNDER_IMPLEMENTED", "OVER_IMPLEMENTED", "UNDOCUMENTED_BEHAVIOR",
                   "CONTRADICTORY_INTENT", "CONDITIONALLY_MATCHED", "UNVERIFIABLE"):
        assert status in SKILL, status
