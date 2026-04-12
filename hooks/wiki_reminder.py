#!/usr/bin/env python3
"""Stop hook: remind Claude to save architectural decisions to wiki.

WHY: Decisions made mid-session ("chose asyncpg over SQLAlchemy because X")
are the highest-value knowledge to capture — they explain WHY the code is
the way it is. Without capture, this reasoning is gone after /clear.
This hook detects 2+ decision keywords in the last assistant response and
fires a systemMessage nudge. Debounced to 5 minutes to avoid spam.

Borrowed pattern from ub3dqy/llm-wiki (stop-wiki-reminder.py), adapted
to our WHY-comment style and bilingual keyword set.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# WHY: recursion guard — prevents hooks from re-firing when Agent SDK
# invokes Claude Code internally (e.g., during auto_capture or subagent runs).
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

DEBOUNCE_FILE = Path.home() / ".claude" / "cache" / "wiki_reminder_debounce.txt"
DEBOUNCE_SEC = 300  # 5 minutes — enough gap to avoid reminder fatigue

# WHY: require 2+ keywords to reduce false positives.
# Single keyword matches (e.g. "approach") fire on nearly every message.
# Two semantic matches = genuine decision/architecture discussion.
_DECISION_KEYWORDS = [
    # English — decision & architecture vocabulary
    "decided",
    "decision",
    "chose",
    "chosen",
    "architecture",
    "architectural",
    "pattern",
    "convention",
    "migration",
    "schema",
    "tradeoff",
    "trade-off",
    "approach",
    "strategy",
    "design",
    "instead of",
    "rather than",
    "because of",
    "in favor",
    "deprecated",
    "replaced",
    "refactor",
    # Russian equivalents
    "решил",
    "решение",
    "выбрал",
    "архитектур",
    "паттерн",
    "конвенци",
    "миграци",
    "схем",
    "стратеги",
    "подход",
    "вместо",
    "из-за",
    "заменил",
    "отказался",
    "рефактор",
]

MIN_KEYWORD_MATCHES = 2


def _check_debounce() -> bool:
    """Return True if enough time has passed since last reminder."""
    if not DEBOUNCE_FILE.exists():
        return True
    try:
        last = float(DEBOUNCE_FILE.read_text(encoding="utf-8").strip())
        return (time.time() - last) >= DEBOUNCE_SEC
    except (ValueError, OSError):
        return True


def _update_debounce() -> None:
    try:
        DEBOUNCE_FILE.parent.mkdir(parents=True, exist_ok=True)
        DEBOUNCE_FILE.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


def _get_last_assistant_response(transcript_path: str) -> str:
    """Read the last assistant response text from the JSONL transcript."""
    p = Path(transcript_path)
    if not p.exists():
        return ""
    last_response = ""
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = entry.get("message", {})
                if not isinstance(msg, dict):
                    continue
                if msg.get("role") != "assistant":
                    continue
                content = msg.get("content", "")
                if isinstance(content, list):
                    parts = [
                        b.get("text", "")
                        for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    ]
                    content = " ".join(parts)
                if isinstance(content, str) and content.strip():
                    last_response = content
    except OSError:
        pass
    return last_response


def _has_decision_language(text: str) -> bool:
    """Return True if the text contains 2+ decision/architecture keywords."""
    text_lower = text.lower()
    matches = sum(1 for kw in _DECISION_KEYWORDS if kw in text_lower)
    return matches >= MIN_KEYWORD_MATCHES


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        hook_input = json.loads(raw)
    except (json.JSONDecodeError, ValueError, EOFError):
        return

    # WHY: stop_hook_active = True means we're inside a Stop hook response loop.
    # Continuing would cause a recursion. Exit immediately.
    if hook_input.get("stop_hook_active"):
        return

    if not _check_debounce():
        return

    transcript_path = hook_input.get("transcript_path", "")
    if not transcript_path:
        return

    response = _get_last_assistant_response(transcript_path)
    if not response:
        return

    if _has_decision_language(response):
        _update_debounce()
        output = {
            "systemMessage": (
                "[wiki-reminder] This response contains architectural decisions or patterns. "
                "Consider saving to wiki: echo '# Decision: ...\\n\\nWHY: ...\\n\\n#decision' "
                "> ~/.claude/memory/raw/decision-$(date +%s).md"
            )
        }
        print(json.dumps(output))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # WHY: fail-open — never block Claude's response
