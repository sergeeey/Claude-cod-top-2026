#!/usr/bin/env python3
"""Regression tests for findings of the router audit (experiments/20261014-contract-router-precision)
and of the independent reviews of the contract router.

Every text below is synthetic. The audit measured false hints on private prompts; what is pinned
here are the CLASSES of false hint it found, written from scratch, never copied from a prompt.
"""

import ast
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SKILL = ROOT / "skills" / "core" / "contract"
sys.path.insert(0, str(SKILL))

import contracts_lib as lib  # noqa: E402

RED = (
    "security-vuln-audit",
    "cognitive-supply-chain-security",
    "chaos-resilience",
    "db-migration-safe",
    "disaster-recovery-drill",
)
RED_PROMPTS = {
    "chaos-resilience": "проверь отказоустойчивость: chaos-тест, потеря пакетов, circuit breaker и таймауты",
    "db-migration-safe": "спроектируй безопасную миграцию схемы базы с откатом и проверкой целостности",
}


@pytest.fixture(scope="module")
def index() -> dict:
    loaded = lib.load_index(SKILL / "index.json")
    assert loaded is not None
    return loaded


# --- one rule for every Red card -------------------------------------------------------------


@pytest.mark.parametrize("cid", RED)
def test_red_card_boundary_states_the_common_rule(index: dict, cid: str) -> None:
    card = next(c for c in index["cards"] if c["id"] == cid)
    section = card["body"].split("## Граница", 1)[1].split("## ", 1)[0]
    # The whole common sentence, not fragments: a boundary that appends "a snapshot of production
    # is allowed without a go" would still contain every fragment but not the sentence.
    assert section.strip().startswith(lib.RED_CORE)


def test_hint_and_draft_say_the_same_thing_as_the_cards(index: dict) -> None:
    routed = lib.route(RED_PROMPTS["chaos-resilience"], index)
    assert routed["card"]["id"] == "chaos-resilience"
    assert lib.RED_HINT in (lib.hint(routed) or "")
    assert lib.RED_CORE in lib.draft(routed, index, "x")
    assert lib.RED_DRAFT in lib.draft(routed, index, "x")
    # the short hint is a shortening of the same rule, not a different one
    for fragment in ("«го»", "план", "без доступа к production"):
        assert fragment in lib.RED_HINT and fragment in lib.RED_CORE


@pytest.mark.parametrize(
    "prompt",
    [
        "объясни, как у нас устроен circuit breaker",
        "что такое disaster recovery",
        "расскажи про chaos engineering",
    ],
)
def test_red_card_is_never_raised_for_a_mere_mention(index: dict, prompt: str) -> None:
    # A phrase names a topic; a Red hint claims "plan only", so it needs a real request verb.
    assert lib.route(prompt, index)["card"] is None


def test_red_card_still_fires_for_a_real_request(index: dict) -> None:
    routed = lib.route("проверь устойчивость: chaos engineering и circuit breaker", index)
    assert routed["card"] is not None and routed["card"]["id"] == "chaos-resilience"


# --- classes of false hint found by the audit (synthetic) ------------------------------------

_TOPIC_WORDS = (
    "аудит статьи, воспроизводимость графиков, эксперимент с контрольной группой, "
    "статистика, p-value, утечка данных между train и test, причинность и confound, "
    "baseline и ablation. "
)


def test_pasted_report_with_many_topic_words_is_silent(index: dict) -> None:
    report = "Итоги раунда. " + _TOPIC_WORDS * 8 + "Вердикт: SUPPORTED. Следующий шаг: ждём ответа."
    assert len(report) > lib._LONG_INPUT
    assert lib.route(report, index)["card"] is None


def test_long_role_prompt_is_silent(index: dict) -> None:
    role = (
        "# Роль\nТы строгий исследовательский аналитик. " + _TOPIC_WORDS * 6 + "Отвечай по шагам."
    )
    assert lib.route(role, index)["card"] is None


def test_conversation_that_mentions_the_topic_is_silent(index: dict) -> None:
    chat = "Мы вчера обсуждали статью и эксперимент, график был странный, но я пока не уверен."
    assert lib.route(chat, index)["card"] is None


def test_request_for_a_different_task_with_topic_words_is_silent(index: dict) -> None:
    # Class "real request, other task": it names card topics but asks for something no card covers.
    other = "напиши письмо рецензенту про нашу статью и эксперимент"
    assert lib.route(other, index)["card"] is None


# --- the verifier that is not there ----------------------------------------------------------


def test_missing_verifier_is_named_in_the_draft_not_hidden(index: dict) -> None:
    prompt = "найди технологию для разработки: proof of concept, технические гипотезы, прототип"
    without = copy.deepcopy(index)
    without["agents"] = [a for a in without["agents"] if a["name"] != "skeptic"]
    routed = lib.route(prompt, without)
    assert routed["card"]["id"] == "tech-discovery-lab"
    assert routed["card"]["verifier_available"] is False
    assert "такого агента нет" in lib.draft(routed, without, prompt)

    with_it = copy.deepcopy(index)
    if not any(a["name"] == "skeptic" for a in with_it["agents"]):
        with_it["agents"].append({"name": "skeptic", "stems": []})
    routed = lib.route(prompt, with_it)
    assert routed["card"]["verifier_available"] is True
    assert "такого агента нет" not in lib.draft(routed, with_it, prompt)


def test_baseline_warning_does_not_contradict_numbers_already_in_done_when(index: dict) -> None:
    routed = lib.route(
        "снизь асимптотическую сложность алгоритма на графе, нужна кривая масштабирования", index
    )
    assert routed["card"]["baseline_first"] is True
    text = lib.draft(routed, index, "x")
    assert "которых нет в «Done when»" in text
    assert "заявленные цели контракта" in text


# --- the library must stay dependency-free ----------------------------------


@pytest.mark.parametrize("name", ["contracts_lib.py", "build_index.py", "contract.py"])
def test_contract_modules_use_only_the_standard_library(name: str) -> None:
    tree = ast.parse((SKILL / name).read_text(encoding="utf-8"))
    allowed = set(sys.stdlib_module_names) | {"contracts_lib", "build_index", "yaml"}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert imported <= allowed, imported - allowed
