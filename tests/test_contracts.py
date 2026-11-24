#!/usr/bin/env python3
"""Tests for the goal-contract router library (skills/core/contract).

What is pinned here, and why:
- the generated index.json is not stale (CI would otherwise ship hints from old cards);
- every card is well formed (a card without Done when / Evidence is a slogan, not a contract);
- each card is reachable from a realistic prompt, and silence is the default for everything else;
- a long pasted catalogue must not match every card (judged by head and tail only);
- routes that name tools missing from the repo index are limited to a known personal-only list;
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SKILL = ROOT / "skills" / "core" / "contract"
sys.path.insert(0, str(SKILL))

import contracts_lib as lib  # noqa: E402
from build_index import build_index, parse_frontmatter, unresolved_routes  # noqa: E402

# Skills and agents that exist on the maintainer's machine only (see CLAUDE.md, "Personal-only
# consumers"). Cards may route to them; the repo index cannot resolve them, the live one can.
PERSONAL_ONLY = {
    "stat-validate",
    "sci-code-audit",
    "code-materiality",
    "deletion-test",
    "lit-search",
    "skeptic",
    "source-librarian",
    "debugger",
    "devops",
    "gh-fix-ci",
    "analyst",
    "boyko-capability-audit",
    "metacognitive-gate",
    "scientific-problem-selection",
    "skill-audit",
}

CARD_PROMPTS = {
    "paper-falsification-audit": "проверь, воспроизводятся ли графики из статьи на arXiv",
    "systematic-review": "сделай систематический обзор литературы по теме, найди публикации",
    "experiment-protocol": "составь протокол эксперимента, нужна контрольная группа и размер выборки",
    "dataset-leakage-audit": "проверь, есть ли утечка данных между train и test, кросс-валидация по датасету",
    "causal-claim-audit": "проверь, влияет ли X на Y или это confound, причинность",
    "reproducible-experiment": "сделай воспроизводимость: seed, окружение, provenance, манифест",
    "baseline-ablation": "проверь абляцию и baseline: новый метод превосходит прежний?",
    "statistical-audit": "проверь p-value и множественные сравнения в этой работе",
    "performance-audit": "хочу ускорить хук, p95 латентность, найди узкое место",
    "citation-source-check": "проверь цитату: подтверждает ли статья это утверждение, DOI источника",
    "async-migration": "переведи синхронный сервис на asyncio, нужна обратная совместимость и рост rps",
    "memory-leak-hunt": "найди утечку памяти: rss растёт при долгой работе, нужен профиль памяти",
    "security-vuln-audit": "проведи аудит безопасности: найди sqli, ssrf, idor и prompt injection",
    "observability-instrumentation": "оснасти сервис трассировкой opentelemetry и метриками prometheus, нужен trace_id",
    "chaos-resilience": "проверь отказоустойчивость: chaos-тест, потеря пакетов, circuit breaker и таймауты",
    "test-coverage-synthesis": "напиши тесты для модуля: покрытие, property-based hypothesis, граничные условия",
    "python-to-rust-port": "перепиши узкое место на rust через pyo3, нужно дифференциальное тестирование",
    "cicd-pipeline": "сделай ci/cd pipeline на github actions с минимальным docker distroless и sbom",
    "algorithmic-complexity": "снизь асимптотическую сложность алгоритма на графе, нужна кривая масштабирования",
    "hard-bug-localization": "найди первопричину нерегулярной ошибки: flaky дефект, root cause",
    "concurrency-audit": "проверь код на race condition и deadlock, атомарность и двойное выполнение",
    "db-migration-safe": "спроектируй безопасную миграцию схемы базы с откатом и проверкой целостности",
    "api-compat-contract": "проверь совместимость api: contract tests, breaking change и semver для sdk",
    "dependency-modernization": "обнови зависимости: lockfile, устаревшие пакеты, pip-audit",
    "data-pipeline-reliability": "проверь конвейер обработки данных etl: дубликаты, потеря записей, качество данных",
    "disaster-recovery-drill": "проверь аварийное восстановление: резервная копия, rto, rpo и runbook",
    "reproducible-build": "сделай воспроизводимую сборку: reproducible build, хэш артефакта, чистое окружение",
    "invariants-verification": "проверь критические инварианты: property-based, mutation testing, контрпримеры",
    "model-reliability": "оцени надёжность модели: калибровка, сдвиг распределения, неопределённость по подгруппам",
    "meta-analysis": "сделай метаанализ: размер эффекта, гетерогенность, публикационное смещение",
    "publication-readiness": "подготовь исследование к независимой проверке: пакет воспроизведения, реестр замечаний, рецензент",
    "memory-forensics": "проверь память системы: ложные воспоминания, устаревшие факты, recall и противоречия",
    "context-value-budget": "оцени ценность контекста: бюджет токенов, сжатие контекстного окна, информационный мусор",
    "methodology-tournament": "проведи турнир методологий: ablation и baseline, вклад каждого метода, причинная полезность",
    "autonomy-frontier": "измерь границы автономности: завершение задач, human intervention, ложный успех, зацикливание",
    "evidence-verification-audit": "проверь честность системы: false completion, evidenceledger, независимая проверка свидетельств",
    "reasoning-self-correction": "оцени вред самокоррекции: глубина проверки, избыточный анализ, политика остановки",
    "tool-routing-economics": "проведи аудит инструментов: маршрутизация, дублирующие запросы, стоимость вызовов, tool router",
    "cognitive-supply-chain-security": "проверь отравление памяти: prompt injection через поддельные документы, доверие к источникам",
    "observatory-dashboard": "создай дашборд observatory: визуализация метрик системы, сравнение запусков, интерактивный интерфейс",
    "tech-discovery-lab": "найди технологию для разработки: proof of concept, технические гипотезы, прототип",
}


@pytest.fixture(scope="module")
def index() -> dict:
    loaded = lib.load_index(SKILL / "index.json")
    assert loaded is not None, (
        "index.json missing: run `python skills/core/contract/contract.py build-index`"
    )
    return loaded


def test_index_is_fresh() -> None:
    pytest.importorskip("yaml")  # the registry join needs PyYAML; without it the bytes differ
    proc = subprocess.run(
        [sys.executable, str(SKILL / "contract.py"), "build-index", "--check"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr


def test_cards_are_well_formed(index: dict) -> None:
    assert {c["id"] for c in index["cards"]} == set(CARD_PROMPTS)
    for card in index["cards"]:
        assert len(card["triggers"]) >= 5, card["id"]
        assert card["verifier"], card["id"]
        assert card["statuses"], card["id"]
        assert "## Done when" in card["body"], card["id"]
        assert "## Evidence" in card["body"], card["id"]
        assert card["risk_tier"] in {"Green", "Yellow", "Red"}, card[
            "id"
        ]  # Black never gets a card
        if card["risk_tier"] == "Red":
            assert "## Граница" in card["body"], card["id"]  # a Red card must say where it stops


def test_catalogue_is_complete_and_unique(index: dict) -> None:
    numbers = sorted(c["catalog"] for c in index["cards"] if c.get("catalog"))
    assert numbers == list(range(1, 41)), numbers
    extra = [c["id"] for c in index["cards"] if not c.get("catalog")]
    assert extra == ["citation-source-check"]  # the one card that is ours, not the catalogue's


def test_red_cards_say_plan_only(index: dict) -> None:
    red = [c["id"] for c in index["cards"] if c["risk_tier"] == "Red"]
    assert set(red) == {
        "security-vuln-audit",
        "cognitive-supply-chain-security",
        "chaos-resilience",
        "db-migration-safe",
        "disaster-recovery-drill",
    }
    for cid in red:
        routed = lib.route(CARD_PROMPTS[cid], index)
        assert "контракт красный: до вашего «го» только план" in (lib.hint(routed) or ""), cid
        assert "КРАСНЫЙ КОНТРАКТ" in lib.draft(routed, index, "x"), cid


def test_known_gaps_are_declared(index: dict) -> None:
    by_id = {c["id"]: c for c in index["cards"]}
    for cid in ("dataset-leakage-audit", "baseline-ablation"):
        assert by_id[cid]["gap"], f"{cid} has a known tool gap and must say so"


@pytest.mark.parametrize("card_id,prompt", sorted(CARD_PROMPTS.items()))
def test_each_card_is_reachable(index: dict, card_id: str, prompt: str) -> None:
    routed = lib.route(prompt, index)
    assert routed["card"] is not None, prompt
    assert routed["card"]["id"] == card_id


@pytest.mark.parametrize(
    "prompt",
    [
        "привет, как дела",
        "почини баг в auth.py, падает тест",
        "добавь параметр в функцию и обнови докстринг",
        "что такое декоратор в Python",
        "спасибо, всё понятно",
    ],
)
def test_silence_is_the_default(index: dict, prompt: str) -> None:
    assert lib.route(prompt, index)["card"] is None
    assert lib.hint(lib.route(prompt, index)) is None


def test_long_pasted_input_is_judged_by_head_and_tail(index: dict) -> None:
    middle = " воспроизводятся графики статьи препринт arXiv p-value утечка confound " * 40
    pasted = "вот список для справки " + "x" * 900 + middle + "y" * 600 + " спасибо"
    assert len(pasted) > lib._LONG_INPUT
    assert lib.route(pasted, index)["card"] is None


def test_two_common_words_do_not_make_a_match(index: dict) -> None:
    # "метод" and "эксперимент" appear in several cards; rarity weighting must not let two
    # such words alone select a card.
    assert lib.route("опиши метод и эксперимент", index)["card"] is None


def test_hint_is_one_short_line(index: dict) -> None:
    for prompt in CARD_PROMPTS.values():
        text = lib.hint(lib.route(prompt, index))
        assert text is not None
        assert "\n" not in text
        assert len(text) <= 460
        assert text.startswith("[contract]")


def test_hint_names_matched_stems(index: dict) -> None:
    text = lib.hint(lib.route(CARD_PROMPTS["paper-falsification-audit"], index)) or ""
    assert "совпало:" in text


def test_baseline_first_cards_warn_about_thresholds(index: dict) -> None:
    routed = lib.route(CARD_PROMPTS["performance-audit"], index)
    assert "базовую линию" in (lib.hint(routed) or "")
    assert "ПОСЛЕ замера базовой линии" in lib.draft(routed, index, "x")


def test_draft_without_card_is_a_task_passport(index: dict) -> None:
    routed = lib.route("привет", index)
    text = lib.draft(routed, index, "привет")
    assert "Done when" in text and "Verifier" in text


def test_repo_unresolved_routes_are_only_personal(index: dict) -> None:
    names = set()
    for line in unresolved_routes(index):
        names.add(line.rsplit(" ", 1)[1])
    assert names <= PERSONAL_ONLY, names - PERSONAL_ONLY


def test_index_builds_from_repo_without_errors() -> None:
    skills = [ROOT / "skills" / "core", ROOT / "skills" / "extensions"]
    built = build_index(SKILL / "cards", skills, ROOT / "agents", ROOT / "skills" / "registry.yaml")
    assert built["n_cards"] == len(built["cards"]) == len(CARD_PROMPTS)
    assert built["card_df"] and built["skills"]


def test_load_index_fails_open(tmp_path: Path) -> None:
    assert lib.load_index(tmp_path / "missing.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert lib.load_index(bad) is None
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({"version": 999}), encoding="utf-8")
    assert lib.load_index(wrong) is None


def test_outcome_statistics_only_shrink_never_veto() -> None:
    assert lib.posterior(0, 0) == 0.5
    assert lib._stats_factor(None, "x") == 1.0
    few = {"x": {"n": lib.MIN_OBSERVATIONS - 1, "ok": 0}}
    assert lib._stats_factor(few, "x") == 1.0  # below the minimum nothing is reordered
    worst = {"x": {"n": 1000, "ok": 0}}
    assert lib._stats_factor(worst, "x") >= 0.7  # a bad record lowers a tool, never removes it


def test_exploration_needs_statistics(index: dict) -> None:
    prompt = CARD_PROMPTS["performance-audit"]
    assert lib.route(prompt, index, stats=None)["unproven"] == []
    explored = lib.route(prompt, index, stats={})
    assert len(explored["unproven"]) <= lib.EXPLORE_MAX


def test_frontmatter_parser_handles_the_subset() -> None:
    fields, body = parse_frontmatter(
        '---\nid: a\ntriggers: [x, "y z"]\nskills:\n  - s1\n  - s2\nflag: true\nn: 7\n---\nbody\n'
    )
    assert fields == {
        "id": "a",
        "triggers": ["x", "y z"],
        "skills": ["s1", "s2"],
        "flag": True,
        "n": 7,
    }
    assert body.strip() == "body"


# --- regressions for the review findings ------------------------------------------------------


def test_phrase_must_start_at_a_word_boundary(index: dict) -> None:
    # "n log n" is a phrase of algorithmic-complexity; it must not fire inside "man log notes".
    assert lib.route("man log notes about the algorithm", index)["card"] is None


def test_single_word_phrase_is_rejected_at_build_time(tmp_path: Path) -> None:
    cards = tmp_path / "cards"
    cards.mkdir()
    card = "\n".join(
        ["---", "id: x", "triggers: [a, b, c, d, e]", "phrases: [оптимизируй]", "---", "body", ""]
    )
    (cards / "x.md").write_text(card, encoding="utf-8")
    with pytest.raises(ValueError, match="at least two words"):
        build_index(cards, [])


def test_generic_request_does_not_pick_a_card(index: dict) -> None:
    assert lib.route("оптимизируй текст письма для клиента", index)["card"] is None


@pytest.mark.parametrize(
    "bad", [{"x": "oops"}, {"x": {"n": "many"}}, {"x": None}, {"x": {"n": 9, "ok": "?"}}]
)
def test_malformed_statistics_never_switch_hints_off(index: dict, bad: dict) -> None:
    routed = lib.route(CARD_PROMPTS["performance-audit"], index, stats=bad)
    assert routed["card"] is not None
