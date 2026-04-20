#!/usr/bin/env python3
"""UserPromptSubmit hook: periodic mentor protocol + career interview prep.

WHY: Two alternating modes every 3rd prompt:
  - Odd multiples of 3 (3, 9, 15...): mentor-protocol WHY reminder
  - Even multiples of 3 (6, 12, 18...): career interview question tied to context

Career questions are picked from a rotating bank matched to keywords in the
current prompt — so a Neo4j question triggers graph algorithms, a hooks question
triggers system design, etc. This creates passive interview prep with zero
friction: the user is already working, the question arrives in context.
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

from utils import emit_hook_result, hook_main, parse_stdin

if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

COUNTER_FILE = Path.home() / ".claude" / "cache" / "mentor_counter.txt"
INTERVAL = 3

# WHY: questions are grouped by keyword so they match the user's current context.
# Generic interview questions feel random and get ignored — contextual ones stick.
CAREER_QUESTIONS: dict[str, list[str]] = {
    "graph|neo4j|node|edge|cypher": [
        "🎯 Interview Q: BFS vs DFS — when would GeoMiro use each for event traversal? Think O(V+E).",
        "🎯 Interview Q: How would you detect a cycle in a directed graph? (hint: think topological sort)",
        "🎯 Interview Q: Design a graph schema for tracking political influence chains with confidence scores.",
    ],
    "test|pytest|coverage|mock": [
        "🎯 Interview Q: What's the difference between a mock and a stub? Give an example from your hooks.",
        "🎯 Interview Q: How do you test non-deterministic AI outputs? (Anthropic ask this often)",
        "🎯 Interview Q: Explain the tradeoff between test coverage % and test quality.",
    ],
    "hook|event|session|trigger": [
        "🎯 Interview Q: Design an event-driven system that must handle 10k events/sec without data loss.",
        "🎯 Interview Q: How would you implement a circuit breaker pattern? You already have one in your repo.",
        "🎯 Interview Q: What's the difference between pub/sub and event sourcing?",
    ],
    "wiki|memory|cache|knowledge": [
        "🎯 Interview Q: Design a RAG pipeline from scratch. What are the failure modes?",
        "🎯 Interview Q: How do you handle cache invalidation in a distributed system? (famously hard)",
        "🎯 Interview Q: What's the difference between semantic search and keyword search? When to use each?",
    ],
    "agent|llm|prompt|claude|gpt": [
        "🎯 Interview Q: How would you evaluate LLM output quality at scale without human reviewers?",
        "🎯 Interview Q: What are the failure modes of a multi-agent system? How do you detect them?",
        "🎯 Interview Q: Anthropic Q: How do you think about tradeoffs between model capability and safety?",
    ],
    "skill|routing|keyword|match": [
        "🎯 Interview Q: Implement a trie-based router. What's the time complexity vs hash map?",
        "🎯 Interview Q: Design a system that routes tasks to specialized models based on content.",
        "🎯 Interview Q: How would you A/B test two routing strategies without breaking production?",
    ],
    "default": [
        "🎯 Interview Q: Walk me through the most complex system you've built. What would you do differently?",
        "🎯 Interview Q: LeetCode: Given a list of intervals, merge all overlapping ones. O(n log n).",
        "🎯 Interview Q: What does O(1) space complexity mean? Find an example in your current code.",
        "🎯 Interview Q: Tell me about a time you caught a bug before it reached production. (STAR format)",
        "🎯 Interview Q: How do you decide when to use async vs sync code? What's the tradeoff?",
    ],
}


def _read_counter() -> int:
    try:
        return int(COUNTER_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return 0


def _write_counter(n: int) -> None:
    try:
        COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
        COUNTER_FILE.write_text(str(n), encoding="utf-8")
    except OSError:
        pass


def _pick_career_question(prompt: str) -> str:
    """Pick a contextually relevant interview question based on prompt keywords."""
    prompt_lower = prompt.lower()
    import re

    for pattern, questions in CAREER_QUESTIONS.items():
        if pattern == "default":
            continue
        if re.search(pattern, prompt_lower):
            return random.choice(questions)  # noqa: S311

    return random.choice(CAREER_QUESTIONS["default"])  # noqa: S311


def main() -> None:
    data = parse_stdin()

    prompt = data.get("prompt", "") if isinstance(data, dict) else ""
    if len(prompt.strip()) < 10:
        return

    count = _read_counter() + 1
    _write_counter(count)

    if count % INTERVAL != 0:
        return

    # WHY: alternate between mentor (odd multiples) and career (even multiples).
    # Pure mentor reminders become background noise after ~10 sessions.
    # Career questions stay fresh because they're always tied to current context.
    cycle = (count // INTERVAL) % 2  # 0 = mentor, 1 = career

    if cycle == 0:
        message = (
            f"[mentor-protocol] Response #{count}. "
            "Format: 💡 TIP: [1-2 lines BEFORE your answer, tied to THIS specific task/file/line]. "
            "After your answer, wrap the insight in a callout box:\n"
            "> [!lesson] ⚡ Урок\n> [1-3 lines — trend/tool/cross-domain/quote, NOT obvious]\n"
            "Both required. BANNED: generic advice ('use type hints', 'write tests'). "
            "REQUIRED: concrete ('auth.py:47 Literal[...] prevents invalid status bug')."
        )
    else:
        question = _pick_career_question(prompt)
        message = (
            "[career-prep] Passive interview training (response #{count}). "
            "After your main answer, add 1 short paragraph: answer this question "
            "using the current context as an example — {question} "
            "Keep it under 3 sentences. Label it: 💼 Interview angle:"
        ).format(count=count, question=question)

    emit_hook_result("UserPromptSubmit", message)


if __name__ == "__main__":
    hook_main(main)
