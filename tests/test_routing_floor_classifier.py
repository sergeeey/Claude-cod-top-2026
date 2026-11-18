#!/usr/bin/env python3
"""Tests for hooks/routing_floor_classifier.py — the deterministic task-tier safety-floor
classifier that makes the routing floor code-enforced instead of LLM-discretionary.

Key properties:
- deterministic detection of SECURITY / DESTRUCTIVE / RESEARCH task signals (bilingual);
- NO false injection on benign prompts (over-injecting would be noise);
- injects context only, never blocks (a shadow-safe enforcement of the CLASSIFICATION).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
HOOK = ROOT / "hooks" / "routing_floor_classifier.py"


def _run(prompt: str) -> str:
    """Run the hook with a prompt, return its stdout (the injected context, if any)."""
    payload = json.dumps({"prompt": prompt, "session_id": "test"})
    env = {"CLAUDE_INVOKED_BY": ""}  # bypass recursion guard is NOT wanted; empty = proceed
    import os

    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        cwd=str(ROOT),
    )
    assert r.returncode == 0, f"hook must never crash / block (exit {r.returncode}): {r.stderr}"
    return r.stdout


@pytest.mark.parametrize(
    "prompt,tier",
    [
        ("add oauth token refresh to the auth flow", "SECURITY"),
        ("store the api_key in the config", "SECURITY"),
        ("переделай платёжный модуль", "SECURITY"),
        ("drop table users and migrate the schema", "DESTRUCTIVE"),
        ("run rm -rf on the cache dir", "DESTRUCTIVE"),
        ("снести миграцию и пересоздать таблицу", "DESTRUCTIVE"),
        ("test the hypothesis that X causes Y", "RESEARCH"),
        ("проверить гипотезу о причинной связи", "RESEARCH"),
    ],
)
def test_detects_tier(prompt, tier):
    out = _run(prompt)
    assert f"[routing-floor] {tier}" in out, f"expected {tier} tier for: {prompt!r}\ngot: {out!r}"


@pytest.mark.parametrize(
    "prompt",
    [
        "rename this variable to foo",
        "add a docstring to the function",
        "what does this regex match",
        "format the readme table",
    ],
)
def test_benign_prompt_injects_nothing(prompt):
    """A benign prompt must NOT trigger a floor injection -- over-injecting is noise that
    would train the reader to ignore the signal."""
    out = _run(prompt).strip()
    assert "[routing-floor]" not in out, f"false injection on benign prompt {prompt!r}: {out!r}"


def test_empty_prompt_is_silent():
    assert "[routing-floor]" not in _run("")


@pytest.mark.parametrize(
    "prompt",
    [
        # pure agent-completion notification carrying RESEARCH signal words — not a user task
        "<system-reminder>\n[SYSTEM NOTIFICATION - NOT USER INPUT]\n<task-notification>"
        '<summary>Agent "Falsify H-B1-1a hypothesis" finished</summary>'
        "<result>experiment falsified the causal claim</result></task-notification>"
        "</system-reminder>",
        # benign user text + a trailing harness block that contains a SECURITY word
        "rename this variable to foo\n<system-reminder>hooks: password rotation reminder"
        "</system-reminder>",
    ],
)
def test_harness_injected_text_is_ignored(prompt):
    """Regression (Y-17 pilot 2026-09-06): 2 of 3 NOISE firings of this hook were on
    <task-notification> text from finished subagents, not on anything the user typed."""
    out = _run(prompt).strip()
    assert "[routing-floor]" not in out, f"fired on harness text: {out!r}"


@pytest.mark.parametrize(
    "prompt",
    [
        # WHY (2026-11-18): descriptive task whose only research word is inside a prohibition
        "Опиши, какие поля есть в выгрузке. Не запускай платные сравнительные эксперименты.",
        # dev task that merely mentions experiments in a negated instruction
        "Переименуй переменную и не трогай эксперименты в notebook.",
        "Не запускай эксперимент сейчас.",
        "Describe the columns only, do not run any experiments.",
    ],
)
def test_weak_experiment_word_in_prohibition_is_not_research(prompt):
    """The weak word alone is not a research signal: a prohibition or a descriptive task with
    the word must not inject the mandatory L0 gate."""
    out = _run(prompt)
    assert "[routing-floor] RESEARCH" not in out, f"false RESEARCH for {prompt!r}: {out!r}"


@pytest.mark.parametrize(
    "prompt",
    [
        "Запусти сравнительный эксперимент: A против B на тестовой выборке, рандомизация по пользователям.",
        "Эксперимент не дал эффекта: разница 0.3 п.п., доверительный интервал включает ноль.",
        "Run an experiment comparing two prompts on 200 items.",
    ],
)
def test_weak_experiment_word_with_intent_is_research(prompt):
    """A real experiment request (affirmative action) or a result report (effect/interval
    vocabulary) keeps the RESEARCH tier."""
    out = _run(prompt)
    assert "[routing-floor] RESEARCH" in out, f"missed RESEARCH for {prompt!r}: {out!r}"


@pytest.mark.parametrize(
    "prompt",
    [
        "Нужен эксперимент для оценки модели",
        "Хочу провести эксперимент над моделью",
        "Давай эксперимент с двумя вариантами промпта",
        "Спланируем эксперимент на 200 примерах",
        "Set up an experiment to compare two retrievers",
    ],
)
def test_planning_or_running_an_experiment_is_research(prompt):
    """Real intent to plan, start or run an experiment: an action verb governs the word."""
    out = _run(prompt)
    assert "[routing-floor] RESEARCH" in out, f"missed RESEARCH intent: {prompt!r}: {out!r}"


@pytest.mark.parametrize(
    "prompt",
    [
        "мы не будем запускать эксперимент, пока нет данных",
        "никакие эксперименты не можем провести сейчас",
        "Не запускай эксперимент сейчас.",
    ],
)
def test_negated_experiment_action_is_not_research(prompt):
    """Negation is scoped to the verb: 'не' before it, or between it and the object, cancels intent."""
    out = _run(prompt)
    assert "[routing-floor] RESEARCH" not in out, f"false RESEARCH: {prompt!r}: {out!r}"


@pytest.mark.parametrize(
    "prompt",
    [
        "Открой experiment_runner.py и поправь путь к конфигу",
        "эксперимент.py падает на None в строке 40",
        "обнови README badge и закрой пилот-эксперименты как resolved",
        "Подключи validate_experiment --frozen к CI",
    ],
)
def test_file_names_and_identifiers_are_not_research(prompt):
    """Weak word inside a file name, identifier or hyphen compound is not a research claim."""
    out = _run(prompt)
    assert "[routing-floor] RESEARCH" not in out, f"false RESEARCH on identifier: {prompt!r}"


@pytest.mark.parametrize(
    "prompt",
    [
        'Цитата из отчёта: "эксперимент показал рост на 5%"',
        "Quote from the notes: 'the experiment failed to replicate'",
    ],
)
def test_quoted_experiment_text_is_not_research(prompt):
    """Words inside quotation marks describe someone else's text, not this task."""
    out = _run(prompt)
    assert "[routing-floor] RESEARCH" not in out, f"false RESEARCH on quote: {prompt!r}: {out!r}"


@pytest.mark.parametrize(
    "prompt",
    [
        "run the unit tests and fix the experiment script",
        "запусти тесты и почини скрипт эксперимента",
        "run the hook on the experiment folder to check the output",
    ],
)
def test_dev_task_with_experiment_mention_is_not_research(prompt):
    """A verb governing other objects (tests, hook) must not turn a dev task into RESEARCH."""
    out = _run(prompt)
    assert "[routing-floor] RESEARCH" not in out, f"false RESEARCH on dev task: {prompt!r}"


@pytest.mark.parametrize(
    "prompt",
    [
        "Проанализируй результаты эксперимента: p-value 0.03, эффект 2 п.п.",
        "Эксперимент не дал эффекта: доверительный интервал включает ноль",
    ],
)
def test_analysis_of_experiment_results_is_research(prompt):
    """Statistics or effect vocabulary next to the word marks analysis of experiment results."""
    out = _run(prompt)
    assert "[routing-floor] RESEARCH" in out, f"missed result analysis: {prompt!r}: {out!r}"


def test_ambiguous_dev_fix_with_interval_word_is_pinned():
    """Ambiguous, accepted: a code fix that names a confidence interval fires RESEARCH because
    'интервал' is result vocabulary. Pinned so a later change is a conscious decision."""
    out = _run("Исправь код эксперимента: функция считает доверительный интервал неверно")
    assert "[routing-floor] RESEARCH" in out


def test_user_text_still_classified_when_reminder_attached():
    out = _run("test the hypothesis that X causes Y\n<system-reminder>ctx</system-reminder>")
    assert "[routing-floor] RESEARCH" in out


def test_never_blocks_even_on_security_prompt():
    """Non-blocking is the safety property: this hook injects, it must never deny/exit(1)."""
    # covered by the exit-0 assertion in _run, but assert explicitly for the security case
    payload = json.dumps({"prompt": "delete the auth secret from the database", "session_id": "t"})
    import os

    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_INVOKED_BY": ""},
        cwd=str(ROOT),
    )
    assert r.returncode == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
