#!/usr/bin/env python3
"""PostToolUse hook for Bash: напоминает извлечь паттерн после fix: коммита.

ПОЧЕМУ: fix-коммиты — самый ценный источник обучающих паттернов. Баг нашли,
починили, и через 10 минут знание теряется. Этот hook принудительно останавливает
Клода после fix-коммита и требует зафиксировать Симптом→Причину→Фикс→Урок
в patterns.md. Паттерн [AVOID] с счётчиком [×N] позволяет отслеживать
рецидивы одних и тех же ошибок.

Отличие от post_commit_memory: post_commit_memory ведёт оперативный лог коммитов
в activeContext.md (что было сделано). pattern_extractor добавляет в patterns.md
структурированный обучающий паттерн (почему сломалось и как не повторить).
"""

import json
import re
import subprocess
import sys
from pathlib import Path


# ПОЧЕМУ: глобальный patterns.md в ~/.claude/memory/ — не проектный.
# Баги повторяются МЕЖДУ проектами, поэтому паттерны хранятся глобально.
GLOBAL_PATTERNS_PATH = Path.home() / ".claude" / "memory" / "patterns.md"

# ПОЧЕМУ: секция "Отладка и фиксы" — целевое место для bugfix-паттернов.
# Её заголовок стабилен (виден в patterns.md), поэтому используем его как якорь.
TARGET_SECTION = "## Отладка и фиксы"


def run_git(args: list[str], timeout: int = 10) -> str:
    """Запускает git-команду и возвращает stdout."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def extract_fix_subject(commit_msg: str) -> str | None:
    """Извлекает краткое описание из fix:-коммита.

    Поддерживает форматы:
    - "fix: something broken"
    - "fix(scope): something broken"
    Returns None если коммит не fix:.
    """
    # ПОЧЕМУ: re.match c IGNORECASE — коммиты пишут по-разному (Fix:, FIX:, fix:)
    m = re.match(r"^fix(?:\([^)]+\))?:\s*(.+)", commit_msg, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def load_patterns_text() -> str:
    """Читает содержимое patterns.md. Возвращает пустую строку если файл не найден."""
    if GLOBAL_PATTERNS_PATH.exists():
        return GLOBAL_PATTERNS_PATH.read_text(encoding="utf-8")
    return ""


def find_matching_patterns(subject: str, patterns_text: str) -> list[tuple[str, int]]:
    """Ищет существующие паттерны в секции 'Отладка и фиксы', чьи заголовки
    содержат ключевые слова из subject коммита.

    Returns список (заголовок_паттерна, текущий_счётчик).
    ПОЧЕМУ: простой keyword-overlap без NLP — достаточно для 80% случаев.
    Сложные семантические матчи избыточны для hook-уровня.
    """
    if not patterns_text:
        return []

    # Выделяем только секцию "Отладка и фиксы" чтобы не ловить ложные совпадения
    # из других секций (например, архитектурных паттернов)
    section_start = patterns_text.find(TARGET_SECTION)
    if section_start == -1:
        return []

    # Ищем конец секции (следующий ## заголовок на уровне 2)
    offset = section_start + len(TARGET_SECTION)
    next_section = re.search(r"\n## ", patterns_text[offset:])
    if next_section:
        section_end = offset + next_section.start()
        section_text = patterns_text[section_start:section_end]
    else:
        section_text = patterns_text[section_start:]

    # Нормализуем subject: убираем пунктуацию, приводим к lower
    # ПОЧЕМУ: короткие технические термины (SQL, IN, API, PII) тоже важны,
    # а русский/английский mix требует гибкости — порог 3 символа + 1 совпадение
    subject_words = set(re.findall(r"\b\w{3,}\b", subject.lower()))

    matches: list[tuple[str, int]] = []

    # Ищем заголовки паттернов ### [ДАТА] Название
    for header_match in re.finditer(r"^### (.+)$", section_text, re.MULTILINE):
        header = header_match.group(1)
        header_words = set(re.findall(r"\b\w{3,}\b", header.lower()))

        # Пересечение слов — 2+ совпадения для длинных, 1 для коротких технических
        overlap = subject_words & header_words
        # ПОЧЕМУ: технические термины (SQL, API) короткие но точные.
        # 2+ совпадения для обычных слов, но если overlap содержит
        # слово из subject длиной >= 5 — достаточно 1 совпадения
        has_strong = any(len(w) >= 5 for w in overlap)
        if len(overlap) >= 2 or (len(overlap) == 1 and has_strong):
            # Извлекаем текущий счётчик [×N] из заголовка или из строк блока
            counter = _extract_counter(header_match.group(0), section_text, header_match.start())
            matches.append((header, counter))

    return matches


def _extract_counter(header_line: str, section_text: str, header_pos: int) -> int:
    """Извлекает числовой счётчик из заголовка паттерна или его первых строк.

    ПОЧЕМУ: счётчик может быть в заголовке ### [2026-01-01] Название [×3]
    или в отдельной строке ниже. Проверяем оба места.
    """
    # Сначала ищем в самой строке заголовка
    m = re.search(r"\[×(\d+)\]", header_line)
    if m:
        return int(m.group(1))

    # Ищем в следующих 5 строках блока паттерна
    tail = section_text[header_pos:]
    # Берём до следующего ### или конца
    block_end = re.search(r"\n###", tail[4:])
    block = tail[: block_end.start() + 4] if block_end else tail
    m = re.search(r"\[×(\d+)\]", block)
    if m:
        return int(m.group(1))

    return 1  # первое вхождение, ещё не размечено


def build_reminder_message(
    commit_hash: str,
    commit_msg: str,
    subject: str,
    matching: list[tuple[str, int]],
) -> str:
    """Формирует текст напоминания для Claude в additionalContext."""
    lines: list[str] = [
        f"[pattern-extractor] fix:-коммит обнаружен: `{commit_hash}` — «{commit_msg}»",
        "",
        "Пожалуйста, извлеки паттерн и добавь его в ~/.claude/memory/patterns.md",
        f"под секцию «{TARGET_SECTION}».",
        "",
    ]

    if matching:
        lines.append("ВНИМАНИЕ: найдены похожие существующие паттерны:")
        for header, counter in matching:
            lines.append(f"  • {header} [×{counter}]")
            lines.append(
                f"    → Если это тот же баг — увеличь счётчик: [×{counter}] → [×{counter + 1}]"
            )
            lines.append("      вместо создания нового блока.")
        lines.append("")
        lines.append("Если баг новый — создай новую запись по шаблону ниже.")
    else:
        lines.append("Похожих паттернов не найдено — создай новый блок:")

    lines += [
        "",
        "Шаблон:",
        f"### [×1] [AVOID] {subject}",
        "- Симптом: что наблюдалось",
        "- Причина: почему происходило",
        "- Фикс: что изменили",
        "- Урок: как избежать в будущем",
        "",
        "Тег [AVOID] = «не повторять». [×1] = первое появление.",
        "При рецидиве меняй [×1] → [×2] и добавляй строку '- Рецидив [дата]: ...'",
    ]

    return "\n".join(lines)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    # ПОЧЕМУ: поддержка двух форматов stdin JSON — вложенного и плоского.
    # Задокументировано в patterns.md: [2026-03-05] Hook stdin JSON: два формата.
    tool_input = data.get("tool_input", data)
    command = tool_input.get("command", "")

    if "git commit" not in command:
        return

    # ПОЧЕМУ: проверяем tool_response чтобы не реагировать на упавший коммит.
    # Та же логика что в post_commit_memory.py — консистентность важна.
    tool_response = data.get("tool_response", data.get("tool_result", {}))
    if isinstance(tool_response, dict):
        response_text = str(tool_response.get("stdout", tool_response.get("output", "")))
    elif isinstance(tool_response, str):
        response_text = tool_response
    else:
        response_text = str(tool_response)

    if "nothing to commit" in response_text or "error" in response_text.lower():
        return

    commit_hash = run_git(["log", "-1", "--format=%h"])
    commit_msg = run_git(["log", "-1", "--format=%s"])

    if not commit_hash:
        return

    # Активируемся только на fix:-коммиты
    subject = extract_fix_subject(commit_msg)
    if subject is None:
        return

    # Ищем совпадения с существующими паттернами
    patterns_text = load_patterns_text()
    matching = find_matching_patterns(subject, patterns_text)

    reminder = build_reminder_message(commit_hash, commit_msg, subject, matching)

    result = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": reminder,
        }
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
