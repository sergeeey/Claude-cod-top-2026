#!/usr/bin/env python3
"""UserPromptSubmit hook: detect magic keywords and suggest skill activation.

WHY: Users often type "let's do TDD" or "security audit this" without knowing
which skill to activate. Passive suggestion (never blocking) lowers the
activation barrier for skills without interrupting the flow.
"""

import json
import sys

# WHY: keyword → skill name mapping drives routing logic. Single source of
# truth — updating here is enough; no other file needs to change.
KEYWORD_MAP: dict[str, str] = {
    "tdd": "tdd-workflow",
    "test": "tdd-workflow",
    "coverage": "tdd-workflow",
    "security": "security-audit",
    "audit": "security-audit",
    "fraud": "security-audit",
    "design": "brainstorming",
    "architecture": "brainstorming",
    "alternatives": "brainstorming",
    "explain": "mentor-mode",
    "teach": "mentor-mode",
    "worktree": "git-worktrees",
    "experiment": "git-worktrees",
    "research": "last30days",
    "trending": "last30days",
}

# WHY: questions ABOUT a topic should not trigger skill activation — the user
# is learning, not asking Claude to perform the task. Prefix matching is cheap
# and avoids false positives for "what is TDD?" or "how does security work?".
INFORMATIONAL_PREFIXES: tuple[str, ...] = (
    "what is",
    "что такое",
    "how does",
    "как работает",
)


def is_informational(prompt: str) -> bool:
    """Return True if the prompt is a question about a topic rather than a task request."""
    lower = prompt.lower().strip()
    return any(lower.startswith(prefix) for prefix in INFORMATIONAL_PREFIXES)


def find_skill(prompt: str) -> str | None:
    """Return the first matching skill name or None."""
    lower = prompt.lower()
    for keyword, skill in KEYWORD_MAP.items():
        if keyword in lower:
            return skill
    return None


def main() -> None:
    """Entry point: read stdin JSON, check keywords, emit suggestion or pass through."""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError, UnicodeDecodeError):
        sys.exit(0)

    prompt: str = data.get("prompt", "")
    if not isinstance(prompt, str) or not prompt.strip():
        sys.exit(0)

    if is_informational(prompt):
        sys.exit(0)

    skill = find_skill(prompt)
    if skill:
        msg = f"[keyword-router] Suggested: /{skill} — activate with /{skill} or proceed normally."
        print(json.dumps({"result": "info", "message": msg}))

    # WHY: no output on miss — silent pass-through keeps the hook invisible
    # when there is nothing useful to say, avoiding notification fatigue.
    sys.exit(0)


if __name__ == "__main__":
    main()
