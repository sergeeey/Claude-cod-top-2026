#!/usr/bin/env python3
"""
CogniML Redaction Hook for Claude Code.
Cleans PII/secrets before sending to external MCP servers.
PreToolUse hook — receives JSON on stdin, returns on stdout.
"""

import json
import re
import sys

# === Kazakhstan and general patterns ===
PATTERNS = [
    # Kazakhstan IIN: 12 digits (YYMMDD + gender digit 1-6 + 5 digits)
    (r"\b\d{2}[01]\d[0-3]\d[1-6]\d{5}\b", "[REDACTED:IIN]"),
    # Bank cards: 16 digits in groups of 4
    (r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "[REDACTED:CARD]"),
    # Kazakhstan IBAN: KZ + 2 digits + 16 characters
    (r"\bKZ\d{2}[A-Z0-9]{16}\b", "[REDACTED:IBAN]"),
    # API keys
    (r"\b(sk-[a-zA-Z0-9]{20,})\b", "[REDACTED:API_KEY]"),
    (r"\b(ghp_[a-zA-Z0-9]{36,})\b", "[REDACTED:GITHUB_TOKEN]"),
    (r"\b(xoxb-[a-zA-Z0-9-]{50,})\b", "[REDACTED:SLACK_TOKEN]"),
    (r"\b(AKIA[0-9A-Z]{16})\b", "[REDACTED:AWS_KEY]"),
    # JWT tokens (from CogniML)
    (r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}", "[REDACTED:JWT]"),
    # Generic token/password/secret assignments (from CogniML)
    (
        r"(?i)(api[_-]?key|token|secret|password|bearer)\s*[:=]\s*['\"]?[\w\-\.]{8,}['\"]?",
        r"\1=[REDACTED:SECRET]",
    ),
    # IP addresses
    (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[REDACTED:IP]"),
    # Email
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[REDACTED:EMAIL]"),
    # KZ phones: +7 7XX XXX XXXX
    (r"\+?7[\s-]?7\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}\b", "[REDACTED:PHONE]"),
]

# Exceptions: ClinVar, dbSNP, genomic coords, simple decimals, git SHA
EXCEPTIONS = [
    r"VCV\d+",
    r"rs\d+",
    r"chr\d+:\d+",
    r"\b\d+\.\d+(?!\.\d)\b",  # decimal like 73.3, but NOT IP-like 1.2.3.4
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
