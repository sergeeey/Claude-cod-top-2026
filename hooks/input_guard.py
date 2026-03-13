#!/usr/bin/env python3
"""PreToolUse hook: detect prompt injection in MCP server responses and tool inputs.

Reads JSON from stdin (Claude Code hook protocol), scans all string values in
tool_input recursively for known injection patterns, and blocks HIGH-threat payloads.

Threat levels:
- NONE  → allow silently
- LOW   → allow, log warning to stderr
- HIGH  → block with decision JSON to stdout
"""

import json
import re
import sys
from typing import Any

# ПОЧЕМУ: категории разделены по семантике угрозы, а не по синтаксису —
# это позволяет точнее формулировать причину блокировки в сообщении пользователю.
PATTERNS: dict[str, re.Pattern[str]] = {
    "system_override": re.compile(
        r"ignore previous|disregard instructions|you are now|new instructions:",
        re.IGNORECASE,
    ),
    "jailbreak": re.compile(
        r"DAN mode|jailbreak|bypass safety|pretend you",
        re.IGNORECASE,
    ),
    "encoding_attack": re.compile(
        r"\x00|[\u200b\u200c\u200d\ufeff]",
    ),
    "data_exfil": re.compile(
        r"send to http|curl |wget |fetch\(",
        re.IGNORECASE,
    ),
    "role_injection": re.compile(
        r"```system|\[SYSTEM\]|<system>|Human:|Assistant:",
        re.IGNORECASE,
    ),
    "credential_harvest": re.compile(
        r"what is your api key|show me your token|print your password",
        re.IGNORECASE,
    ),
    "command_injection": re.compile(
        r"; rm |\| cat /etc|&& curl|\$\(|`[^`]+`",
    ),
}

# ПОЧЕМУ: эти категории немедленно эскалируют до HIGH даже при единственном совпадении —
# они несут прямой операционный риск (выполнение кода, обход кодировки).
HIGH_PRIORITY_CATEGORIES = {"encoding_attack", "command_injection"}

# Нулевые байты и zero-width символы — единственное что безопасно стрипать автоматически
SANITIZE_PATTERN = re.compile(r"\x00|[\u200b\u200c\u200d\ufeff]")


def collect_strings(value: Any) -> list[str]:
    """Рекурсивно собирает все строковые значения из произвольной структуры данных."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        results: list[str] = []
        for v in value.values():
            results.extend(collect_strings(v))
        return results
    if isinstance(value, list):
        results = []
        for item in value:
            results.extend(collect_strings(item))
        return results
    return []


def sanitize(value: Any) -> Any:
    """Рекурсивно удаляет null-байты и zero-width символы из строк."""
    if isinstance(value, str):
        return SANITIZE_PATTERN.sub("", value)
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def scan(strings: list[str]) -> dict[str, int]:
    """Возвращает словарь {категория: количество_совпадений} для всех строк."""
    hits: dict[str, int] = {}
    for text in strings:
        for category, pattern in PATTERNS.items():
            count = len(pattern.findall(text))
            if count:
                hits[category] = hits.get(category, 0) + count
    return hits


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name: str = data.get("tool_name", "")

    # ПОЧЕМУ: проверяем только MCP-инструменты — они принимают внешние данные,
    # встроенные инструменты Claude (Read, Bash и т.д.) доверенные по определению.
    if not tool_name.startswith("mcp__"):
        sys.exit(0)

    tool_input: Any = data.get("tool_input", {})
    strings = collect_strings(tool_input)
    hits = scan(strings)

    if not hits:
        # NONE — разрешить, вернуть sanitized input
        clean_input = sanitize(tool_input)
        print(json.dumps({"tool_input": clean_input}))
        sys.exit(0)

    categories = list(hits.keys())
    total_matches = sum(hits.values())
    is_high = total_matches >= 2 or any(c in HIGH_PRIORITY_CATEGORIES for c in categories)

    if is_high:
        reason = f"Prompt injection detected: {', '.join(categories)}"
        print(json.dumps({"decision": "block", "reason": reason}))
        sys.exit(0)

    # LOW — разрешить с предупреждением, sanitize на выходе
    print(
        f"[input-guard] LOW threat in {tool_name}: {categories} ({total_matches} match). Allowed.",
        file=sys.stderr,
    )
    clean_input = sanitize(tool_input)
    print(json.dumps({"tool_input": clean_input}))
    sys.exit(0)


if __name__ == "__main__":
    main()
