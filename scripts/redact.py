#!/usr/bin/env python3
"""
CogniML Redaction Hook for Claude Code.
Очищает PII/secrets перед отправкой во внешние MCP-серверы.
PreToolUse hook — получает JSON на stdin, возвращает на stdout.
"""

import sys
import re
import json

# === Паттерны для Казахстана и общие ===
PATTERNS = [
    # IIN Казахстана: 12 цифр (YYMMDD + gender digit 1-6 + 5 цифр)
    (r"\b\d{2}[01]\d[0-3]\d[1-6]\d{5}\b", "[REDACTED:IIN]"),
    # Банковские карты: 16 цифр группами по 4
    (r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "[REDACTED:CARD]"),
    # IBAN Казахстана: KZ + 2 цифры + 16 символов
    (r"\bKZ\d{2}[A-Z0-9]{16}\b", "[REDACTED:IBAN]"),
    # API ключи
    (r"\b(sk-[a-zA-Z0-9]{20,})\b", "[REDACTED:API_KEY]"),
    (r"\b(ghp_[a-zA-Z0-9]{36,})\b", "[REDACTED:GITHUB_TOKEN]"),
    (r"\b(xoxb-[a-zA-Z0-9-]{50,})\b", "[REDACTED:SLACK_TOKEN]"),
    (r"\b(AKIA[0-9A-Z]{16})\b", "[REDACTED:AWS_KEY]"),
    # Email
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[REDACTED:EMAIL]"),
    # Телефоны KZ: +7 7XX XXX XXXX
    (r"\+?7[\s-]?7\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}\b", "[REDACTED:PHONE]"),
]

# Исключения: ClinVar, dbSNP, genomic coords, decimals, git SHA
EXCEPTIONS = [
    r"VCV\d+",
    r"rs\d+",
    r"chr\d+:\d+",
    r"\b\d+\.\d+\b",
    r"\b[a-f0-9]{40}\b",
]


def should_exclude(match_text: str) -> bool:
    for exc_pattern in EXCEPTIONS:
        if re.match(exc_pattern, match_text):
            return True
    return False


def redact(text: str) -> str:
    for pattern, replacement in PATTERNS:

        def replace_if_not_excluded(m, repl=replacement):
            if should_exclude(m.group(0)):
                return m.group(0)
            return repl

        text = re.sub(pattern, replace_if_not_excluded, text)
    return text


def clean(obj):
    if isinstance(obj, str):
        return redact(obj)
    elif isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean(item) for item in obj]
    return obj


if __name__ == "__main__":
    input_data = sys.stdin.read()
    try:
        data = json.loads(input_data)
        print(json.dumps(clean(data)))
    except json.JSONDecodeError:
        print(redact(input_data))
