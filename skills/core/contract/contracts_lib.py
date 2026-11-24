"""Goal-contract router: pick a contract card and the tools for a task, deterministically.

WHY (2026-10-14): the owner does not know every skill and should not have to. Three things
already existed but did not meet: hooks/keyword_router.py suggests ONE skill by substring,
hooks/resource_router.py suggests a model tier, scripts/resolve_route.py resolves only
scientific workflows. None of them knows what a good result for a task looks like, and
none learns which suggestion worked. This module adds the missing middle:

  task text -> contract card (Goal / Done when / Evidence / Verifier) -> tools to run

Design rules, each one from a failure this repo already paid for:

* Stdlib only. The CLI (contract.py) and the evaluation script import this; the hook that
  used to import it was removed (see experiments/20261014-contract-practical-value).
* Deterministic and explainable: every suggestion carries the stems that matched, so a wrong
  suggestion can be diagnosed instead of argued with (keyword hooks that match a trigger word
  without checking it is a mention of the concept were AVOID x7 in patterns.md).
* Narrow by default: every hint needs at least one request verb in the judged text, and
  then either three distinct trigger stems or one exact multi-word phrase (starting at a word
  boundary). No card, no hint. Silence is the default.
* Long input (> 600 chars) is judged by its head and tail only, and only an explicit request
  phrase counts there. Why: on real prompts the first version spoke on about a third of long
  inputs, nearly all of them pasted reports. Current numbers and their caveats: SKILL.md.
* Exploration is explicit and capped: at most one tool the owner has never been steered to
  is added, and it is labelled as unproven. That is how a new skill gets its first use.
* Outcomes enter only as shrunk statistics (Beta(1,1) posterior), never as a veto: with few
  observations the ranking stays the curated one.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any

INDEX_VERSION = 1

# Words that carry no routing signal in either language (kept short on purpose).
_STOP = frozenset(
    """
    the and for with that this from into over under about как что это для при или его ее её
    они она оно все всё так вот уже еще ещё мне тебе нам вам мой наш надо нужно можно будет
    есть был была были чтобы если когда тоже только очень сделай сделать давай пожалуйста
    please just make want need should could would have has had you your our out are was were
    """.split()
)

_WORD_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)

# A pasted catalogue or log must not match every card: judge long input by head and tail.
_LONG_INPUT = 600
_HEAD, _TAIL = 300, 200

# A hint is for a REQUEST, not for a conversation that mentions a topic. Stems of request verbs
# (imperatives and infinitives, RU and EN) as EXACT words: stemming would let past tense
# ("сделали") pass as a request ("сделай"). Words that are mostly nouns here (аудит, audit, test,
# run, build, plan, profile, benchmark, design, review, check, fix, measure) are deliberately
# absent: they
# fill reports. A hint of any kind needs at least one of these words.
_REQUEST_WORDS = """
проверь проверить перепроверь перепроверить проанализируй проанализировать разбери разобрать
оцени оценить найди найти составь составить сделай сделать запусти запустить
воспроизведи воспроизвести
сверь сверить подтверди подтвердить измерь измерить ускорь ускорить оптимизируй
протестируй посчитай пересчитай опиши подготовь подготовить
перепиши переведи напиши внедри устрани оснасти спроектируй выдели обнови исправь создай
настрой проведи снизь выяви
implement migrate refactor optimize
verify analyze analyse find reproduce replicate compare evaluate write validate
""".split()
_REQUEST_SET = frozenset(_REQUEST_WORDS)

# One rule for every Red contract. RED_CORE is quoted verbatim at the start of each Red card's
# "Граница" section and inside RED_DRAFT; RED_HINT is its short form. Tests pin all of this.
RED_CORE = (
    "До явного «го» владельца: только план и работа на изолированном стенде, собранном без "
    "доступа к production, реальным данным и ключам. Снимок production, реальные ключи, живые "
    "зависимости, слияние и выкладка требуют отдельного «го»."
)
RED_HINT = (
    "Если это такая задача, контракт красный: до вашего «го» только план и стенд "
    "без доступа к production."
)
RED_DRAFT = "КРАСНЫЙ КОНТРАКТ. " + RED_CORE + " Раздел «Граница» выше обязателен."

MIN_STEMS_FOR_CARD = 3
# Sum of rarity weights: two stems unique to a card clear it, two stems shared by many do not.
MIN_CARD_SCORE = 4.0
PHRASE_WEIGHT = 4.0
HIGH_CONFIDENCE = 9.0
EXPLORE_MAX = 1
EXPLORE_MIN_STEMS = 3
MIN_OBSERVATIONS = 5  # below this, outcome statistics do not reorder anything


def stem(word: str) -> str:
    """Crude prefix stem that works for Russian inflection and English derivation alike.

    reproduce / reproducible / reproducibility -> reprod ; воспроизводятся / воспроизводимость
    -> воспроиз. Deliberately coarse: precision comes from requiring several matches.
    """
    if len(word) >= 8:
        return word[:6]
    if len(word) >= 5:
        return word[:5]
    return word


def tokenize(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).lower()
    return [stem(w) for w in _WORD_RE.findall(text) if len(w) >= 3 and w not in _STOP]


def effective_text(task: str) -> str:
    if len(task) <= _LONG_INPUT:
        return task
    return task[:_HEAD] + " " + task[-_TAIL:]


def posterior(n: int, ok: int) -> float:
    """Mean of Beta(1 + ok, 1 + n - ok): 0.5 with no data, shrinking towards the rate."""
    return (ok + 1) / (n + 2)


def _stats_factor(stats: dict[str, dict[str, int]] | None, name: str) -> float:
    """Shrunk outcome factor in [0.7, 1.3]; any malformed entry means "no information"."""
    try:
        if not stats or name not in stats:
            return 1.0
        n = int(stats[name].get("n", 0))
        if n < MIN_OBSERVATIONS:
            return 1.0
        return 0.7 + 0.6 * posterior(n, max(0, min(n, int(stats[name].get("ok", 0)))))
    except (AttributeError, TypeError, ValueError):
        return 1.0


def load_index(path: Path) -> dict[str, Any] | None:
    """Read the generated index; None on any problem (callers must fail open)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("version") != INDEX_VERSION:
        return None
    return data


def _phrase_in(phrase: str, low: str) -> bool:
    """A phrase counts only where it starts a word: "n log n" must not match inside "man log"."""
    start = low.find(phrase)
    while start != -1:
        if start == 0 or not low[start - 1].isalnum():
            return True
        start = low.find(phrase, start + 1)
    return False


def _stem_weight(stem_: str, index: dict[str, Any]) -> float:
    """1 + ln(N / df): a stem found in one card is worth more than one found in five."""
    n = max(1, int(index.get("n_cards") or len(index.get("cards", [])) or 1))
    df = max(1, int((index.get("card_df") or {}).get(stem_, 1)))
    return 1.0 + math.log(n / df)


def match_cards(task: str, index: dict[str, Any]) -> list[dict[str, Any]]:
    """Cards that clear the bar, best first. Each carries the evidence for the match."""
    text = effective_text(task)
    long_input = len(task) > _LONG_INPUT
    low = unicodedata.normalize("NFKC", text).lower()
    task_stems = set(tokenize(text))
    has_request_verb = bool(set(_WORD_RE.findall(low)) & _REQUEST_SET)
    found: list[dict[str, Any]] = []
    for card in index.get("cards", []):
        stems_hit = sorted(task_stems & set(card.get("stems", [])))
        phrases_hit = [p for p in card.get("phrases", []) if _phrase_in(p, low)]
        score = sum(_stem_weight(s, index) for s in stems_hit) + PHRASE_WEIGHT * len(phrases_hit)
        enough_stems = len(stems_hit) >= MIN_STEMS_FOR_CARD and score >= MIN_CARD_SCORE
        if not has_request_verb:
            # A hint is for a REQUEST. Neither stems nor a topic phrase ("p-value", "circuit
            # breaker") is evidence of one: both appear in reports, mail and chat that merely
            # mention the topic. Audit 20261014: of the 25 hints without this rule, 3 had no
            # request verb and none of them was a true request. For a Red card it matters most,
            # since its hint claims "plan only until the owner says go".
            continue
        if long_input:
            # Long text is mostly pasted material (reports, role prompts, mail), where the
            # concept words of a card are merely mentioned. A topic phrase inside the head or
            # tail is the only evidence accepted there.
            enough_stems = False
        if not enough_stems and not phrases_hit:
            continue
        confidence = "high" if score >= HIGH_CONFIDENCE else "medium"
        found.append(
            {
                "id": card["id"],
                "title": card.get("title", card["id"]),
                "score": round(score, 2),
                "confidence": confidence,
                "matched_stems": stems_hit,
                "matched_phrases": phrases_hit,
            }
        )
    found.sort(key=lambda c: (-c["score"], c["id"]))
    return found


def _observations(stats: dict[str, dict[str, int]] | None, name: str) -> int:
    try:
        return int((stats or {}).get(name, {}).get("n", 0))
    except (AttributeError, TypeError, ValueError):
        return 0


def _skill_overlap(task_stems: set[str], skill: dict[str, Any], common: set[str]) -> int:
    """Shared stems, ignoring those that most skills mention (they say nothing about fit)."""
    return len((task_stems - common) & set(skill.get("stems", [])))


def route(
    task: str,
    index: dict[str, Any],
    stats: dict[str, dict[str, int]] | None = None,
    explore: bool = True,
) -> dict[str, Any]:
    """Pick the best card and a short, ranked tool list for the task.

    Returns {"card": dict|None, "tools": [..], "unproven": [..], "confidence": str}.
    `tools` come from the card's curated routes (reordered only by shrunk outcome
    statistics); `unproven` holds at most EXPLORE_MAX relevant tools never tried before.
    """
    cards = match_cards(task, index)
    result: dict[str, Any] = {"card": None, "tools": [], "unproven": [], "confidence": "none"}
    if not cards:
        return result
    best = cards[0]
    card = next(c for c in index["cards"] if c["id"] == best["id"])
    known = {s["name"]: s for s in index.get("skills", [])}
    agents = {a["name"] for a in index.get("agents", [])}
    result["card"] = {
        **best,
        "baseline_first": bool(card.get("baseline_first")),
        "risk_tier": card.get("risk_tier", "Green"),
        # False when the card's verifier is a personal agent this index does not know: the
        # draft then says so instead of naming a checker that will silently not be offered.
        "verifier_available": (not card.get("verifier")) or card["verifier"] in agents,
    }
    result["confidence"] = best["confidence"]
    curated: list[dict[str, Any]] = []
    for pos, name in enumerate(card.get("skills", [])):
        if name in known:
            base = 10.0 - pos
            curated.append(
                {
                    "name": name,
                    "kind": "skill",
                    "score": base * _stats_factor(stats, name),
                    "why": "curated for this card",
                }
            )
    for pos, name in enumerate(card.get("agents", [])):
        if name in agents:
            base = 5.0 - pos * 0.5
            curated.append(
                {
                    "name": name,
                    "kind": "agent",
                    "score": base * _stats_factor(stats, name),
                    "why": "independent verifier" if name == card.get("verifier") else "curated",
                }
            )
    curated.sort(key=lambda t: (-t["score"], t["name"]))
    result["tools"] = curated

    # Without usage statistics every skill looks "never tried"; exploring blind would only
    # re-suggest tools the owner already uses. So exploration needs stats to exist at all.
    if explore and stats is not None:
        task_stems = set(tokenize(effective_text(task)))
        common = set(index.get("common_stems", []))
        in_card = set(card.get("skills", [])) | set(card.get("agents", []))
        candidates = []
        for skill in index.get("skills", []):
            name = skill["name"]
            if name in in_card or name == "contract":
                continue
            n = _observations(stats, name)
            overlap = _skill_overlap(task_stems, skill, common)
            if n == 0 and overlap >= EXPLORE_MIN_STEMS:
                hit = sorted((task_stems - common) & set(skill["stems"]))
                candidates.append((overlap, name, hit))
        candidates.sort(key=lambda c: (-c[0], c[1]))
        for overlap, name, hit in candidates[:EXPLORE_MAX]:
            result["unproven"].append(
                {
                    "name": name,
                    "kind": "skill",
                    "score": float(overlap),
                    "why": f"never suggested before; matches {', '.join(hit)}",
                }
            )
    return result


def hint(routed: dict[str, Any], limit: int = 460) -> str | None:
    """One advisory line in the CLI's form, or None to stay silent. No hook calls it now."""
    card = routed.get("card")
    if not card:
        return None
    tools = [t["name"] for t in routed["tools"][:3]]
    parts = [
        f"[contract] Подходит карточка «{card['title']}» ({card['id']}, уверенность "
        f"{card['confidence']}; совпало: {', '.join(card['matched_stems'][:4]) or 'фраза'})."
    ]
    if card.get("risk_tier") == "Red":
        parts.append(RED_HINT)
    if tools:
        parts.append("Инструменты: " + ", ".join(tools) + ".")
    if routed["unproven"]:
        parts.append("Ещё не пробовали: " + routed["unproven"][0]["name"] + ".")
    if card.get("baseline_first"):
        parts.append("Сначала измерить базовую линию.")
    parts.append("`/contract` покажет полный контракт с критериями готовности.")
    text = " ".join(parts)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def draft(routed: dict[str, Any], index: dict[str, Any], task: str) -> str:
    """Full contract draft shown for approval before work starts."""
    card_ref = routed.get("card")
    if not card_ref:
        return (
            "Подходящей карточки нет. Общий контракт (Task Passport, rules/meta-loop.md):\n"
            f"Goal: {task.strip()[:200]}\n"
            "Done when: <одно проверяемое условие, зафиксированное ДО результата>\n"
            "Risk tier: reversible-local | affects-shared-state | hard-to-reverse\n"
            "Side effects: <что можно трогать и что нельзя>\n"
            "Verifier: <кто проверит, не исполнитель>\n"
        )
    card = next(c for c in index["cards"] if c["id"] == card_ref["id"])
    lines = [
        f"Контракт: {card['title']} ({card['id']})",
        f"Уверенность подбора: {card_ref['confidence']} "
        f"(совпало: {', '.join(card_ref['matched_stems']) or 'точная фраза'})",
        f"Риск: {card.get('risk_tier', 'Green')} | бюджет: ~{card.get('budget_turns', 30)} ходов "
        f"| проверяет: {_verifier_text(card, card_ref)}",
        "",
        card.get("body", "").strip(),
        "",
        "Инструменты по порядку:",
    ]
    for t in routed["tools"]:
        lines.append(f"  - {t['kind']}: {t['name']} ({t['why']})")
    for t in routed["unproven"]:
        lines.append(f"  - попробовать: {t['name']} ({t['why']})")
    if card.get("risk_tier") == "Red":
        lines += ["", RED_DRAFT]
    if card_ref.get("baseline_first"):
        lines += [
            "",
            "ВАЖНО: числа, которых нет в «Done when» выше (ускорение, покрытие, процент), называть "
            "только ПОСЛЕ замера базовой линии и фиксировать до получения результата. Числа, "
            "уже записанные в «Done when», это заявленные цели контракта: сверь их с измеренной "
            "базовой линией и при необходимости пересмотри ДО результата, а не после.",
        ]
    return "\n".join(lines)


def _verifier_text(card: dict[str, Any], card_ref: dict[str, Any]) -> str:
    name = card.get("verifier")
    if not name:
        return "не назначен"
    if card_ref.get("verifier_available", True):
        return str(name)
    return f"{name} (в этой установке такого агента нет: назначь независимого проверяющего вручную)"
