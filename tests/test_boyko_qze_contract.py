"""Contract tests for boyko-qze: the mechanic is questions first, then checks.

Order in the workflow: understand the decision -> frame check -> propose questions ->
check numbers -> conditional answer -> decision boundary -> premortem -> stop.
"""

import re
from pathlib import Path

SKILL = (Path(__file__).resolve().parents[1] / "skills" / "extensions" / "boyko-qze" / "SKILL.md").read_text(encoding="utf-8")


def _workflow() -> str:
    return SKILL[SKILL.index("## Порядок работы (QUICK)"): SKILL.index("## Классы поиска пропусков")]


def test_questions_come_before_numbers_check_and_base_answer():
    w = _workflow()
    assert w.index("Предложи вопросы") < w.index("Проверь числа и даты") < w.index("Базовый условный ответ")


def test_frame_check_is_before_questions_and_allows_zero_questions():
    w = _workflow()
    assert w.index("Проверка рамки") < w.index("Предложи вопросы")
    assert "вопросов задай 0" in w


def test_each_question_states_both_consequences():
    assert "что меняется, если ответ X, и что меняется, если ответ Y" in _workflow()


def test_output_format_starts_with_questions():
    s = SKILL.index("## Формат ответа")
    e = SKILL.index("## Самопроверка перед ответом")
    fmt = SKILL[s:e]
    assert fmt.index("0. Первым блоком — вопросы") < fmt.index("1. Решение")
    assert "вопросов нет: рамка достаточна" in fmt


def test_gap_types_and_zero_question_rule_stay():
    for kind in ("DECISION_CRITICAL", "DECISION_INFORMATIVE", "DISCOVERY"):
        assert kind in SKILL, kind
    assert "Информативный пропуск сообщается, но вопросом не становится." in SKILL


def test_picker_description_mentions_questions_first_and_is_parseable():
    import yaml
    fm = re.match(r"^---\n(.*?)\n---", SKILL, re.DOTALL).group(1)
    desc = yaml.safe_load(fm)["description"]
    assert desc.startswith("Сначала предлагает вопросы")
