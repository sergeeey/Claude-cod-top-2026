#!/usr/bin/env python3
"""UserPromptSubmit hook: detect task complexity and suggest thinking level.

WHY: Users rarely remember to invoke /think ultrathink for architectural tasks
or /think harder for debugging sessions. A passive nudge (never blocking)
surfaces the right thinking level without interrupting flow.
"""

import json
import sys

# WHY: separate keyword lists by tier so priority resolution is unambiguous —
# higher tier wins when multiple keywords match (e.g. "refactor and debug").
L3_KEYWORDS: tuple[str, ...] = (
    "architecture",
    "refactor",
    "security audit",
    "design system",
    "migrate",
    "rewrite",
    "scale",
    "distributed",
)

L2_KEYWORDS: tuple[str, ...] = (
    "debug",
    "review",
    "analyze",
    "explain why",
    "compare",
    "investigate",
    "optimize",
    "performance",
)

L1_KEYWORDS: tuple[str, ...] = (
    "implement",
    "add feature",
    "fix bug",
    "write test",
    "update",
    "modify",
    "create",
)

# WHY: if the user already named a thinking level we stay silent — suggesting
# what they already requested creates noise without adding value.
ALREADY_THINKING: tuple[str, ...] = (
    "ultrathink",
    "think hard",
    "think harder",
    "think carefully",
    "/think",
)


def already_requested_thinking(prompt: str) -> bool:
    """Return True if the prompt already contains an explicit thinking directive."""
    lower = prompt.lower()
    return any(kw in lower for kw in ALREADY_THINKING)


def classify(prompt: str) -> int:
    """Return complexity level 0-3 based on keyword presence."""
    lower = prompt.lower()
    if any(kw in lower for kw in L3_KEYWORDS):
        return 3
    if any(kw in lower for kw in L2_KEYWORDS):
        return 2
    if any(kw in lower for kw in L1_KEYWORDS):
        return 1
    return 0


def main() -> None:
    """Entry point: read stdin JSON, classify complexity, emit suggestion or pass through."""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError, UnicodeDecodeError):
        sys.exit(0)

    prompt: str = data.get("prompt", "")
    if not isinstance(prompt, str) or not prompt.strip():
        sys.exit(0)

    if already_requested_thinking(prompt):
        sys.exit(0)

    level = classify(prompt)

    if level == 3:
        msg = "[thinking-level] Complex task detected. Consider: /think ultrathink"
        print(json.dumps({"result": "info", "message": msg}))
    elif level == 2:
        msg = "[thinking-level] Analytical task detected. Consider: /think harder"
        print(json.dumps({"result": "info", "message": msg}))

    # WHY: levels 0-1 produce no output — silent pass-through avoids
    # notification fatigue for routine tasks.
    sys.exit(0)


if __name__ == "__main__":
    main()
