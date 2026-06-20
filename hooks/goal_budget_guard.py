#!/usr/bin/env python3
"""UserPromptSubmit hook: warn when /goal is used without a turn budget.

# WHY: /goal mode can run indefinitely without a stop condition — this is a
# soft reminder to add 'or stop after N turns', never a blocker (exit 0 always).
"""

import json
import sys


def main() -> None:
    """Read UserPromptSubmit JSON from stdin and emit an info warning if needed."""
    raw = sys.stdin.read()
    data = json.loads(raw)
    prompt: str = data.get("prompt", "")

    prompt_lower = prompt.lower()

    # WHY: case-insensitive match covers /GOAL, /Goal, etc.
    if "/goal" not in prompt_lower:
        return

    has_budget = "stop after" in prompt_lower or "or stop" in prompt_lower
    if not has_budget:
        info = {
            "type": "info",
            "message": (
                "⏱️ /goal без turn budget — "
                "добавь 'or stop after N turns'. "
                "Ориентир: "
                "lint=10, TDD=25, coverage=30, CI=70 turns."
            ),
        }
        print(json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # WHY: hook must never crash or block — silent failure, exit 0
    sys.exit(0)
