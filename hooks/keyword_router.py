#!/usr/bin/env python3
"""UserPromptSubmit hook: detect magic keywords and suggest skill activation.

WHY: Users often type "let's do TDD" or "security audit this" without knowing
which skill to activate. Passive suggestion (never blocking) lowers the
activation barrier for skills without interrupting the flow.

Power modes (ralph, autopilot, ultrawork, deep, quick) inject behavioral
instructions directly into the prompt context instead of suggesting a skill.
They take priority over skill routing and bypass the informational-question
guard — a user typing "ralph fix this" is never asking a theoretical question.
"""

import json
import sys
from dataclasses import dataclass

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
    "corpus": "research-corpus",
    "literature review": "research-corpus",
    "analyze papers": "research-corpus",
    "анализ корпуса": "research-corpus",
    "разбери статьи": "research-corpus",
}


@dataclass(frozen=True)
class PowerMode:
    """A named behavioral instruction injected into the prompt context.

    WHY: dataclass keeps name + instruction together so POWER_MODES stays
    readable — a plain dict[str, str] would lose the display name.
    """

    name: str
    instruction: str


# WHY: power modes inject behavioral context rather than pointing at a skill
# file. They change HOW Claude works for the duration of the response, not
# WHAT knowledge it loads. Keeping them separate from KEYWORD_MAP makes the
# distinction explicit and lets priority logic stay simple.
POWER_MODES: dict[str, PowerMode] = {
    "ralph": PowerMode(
        name="Persistent",
        instruction=(
            "Do not stop until the task is fully complete. "
            "On errors: diagnose, fix, retry. No confirmations needed. "
            "Verify result before declaring done."
        ),
    ),
    "autopilot": PowerMode(
        name="Full Autonomy",
        instruction=(
            "Execute the entire task autonomously. Make decisions without asking. "
            "Plan first, then execute all steps. "
            "Only stop if truly blocked after 3 attempts."
        ),
    ),
    "ultrawork": PowerMode(
        name="Max Parallelism",
        instruction=(
            "Use maximum parallelism. Launch agents concurrently where possible. "
            "Batch independent operations. Optimize for speed over caution."
        ),
    ),
    "deep": PowerMode(
        name="Deep Analysis",
        instruction=(
            "Perform thorough analysis. Read all relevant files before acting. "
            "Check edge cases. Consider alternatives. Evidence-mark all claims."
        ),
    ),
    "quick": PowerMode(
        name="Speed",
        instruction="Minimal output. No explanations. Just do it. Skip tips and insights.",
    ),
    "confirm": PowerMode(
        name="Acceptor",
        instruction=(
            "Before executing, state your acceptor in 2 lines:\n"
            "  DONE WHEN: [specific, measurable criterion]\n"
            "  FAIL IF: [what would make this a failure]\n"
            "Then execute. After finishing, check each criterion explicitly: ✓ or ✗. "
            "If ✗ — fix the specific gap, do not rewrite everything."
        ),
    ),
}

# WHY: aliases resolve to canonical power mode keys before any lookup so the
# priority check and POWER_MODES dict stay free of alias noise. Russian aliases
# (авто, быстро) match the CLAUDE.md Speed Mode convention users already know.
POWER_MODE_ALIASES: dict[str, str] = {
    "ulw": "ultrawork",
    "авто": "autopilot",
    "быстро": "quick",
    "акцептор": "confirm",
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


def resolve_alias(token: str) -> str:
    """Resolve a power mode alias to its canonical key, or return the token unchanged."""
    return POWER_MODE_ALIASES.get(token, token)


def find_power_mode(prompt: str) -> PowerMode | None:
    """Return the first matching PowerMode or None.

    WHY: checks the full prompt for every canonical key AND every alias so
    users can write e.g. 'ulw fix the tests' and get ultrawork behaviour.
    Alias resolution happens here, not in the caller, to keep main() clean.
    """
    lower = prompt.lower()
    # Check canonical keys directly
    for key, mode in POWER_MODES.items():
        if key in lower:
            return mode
    # Check aliases and resolve to canonical
    for alias, canonical in POWER_MODE_ALIASES.items():
        if alias in lower:
            return POWER_MODES[canonical]
    return None


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

    # WHY: power modes are checked BEFORE the informational guard because a
    # prompt like "ralph what is TDD and fix my tests" is clearly a task, not
    # a question. Letting the guard block it would silently drop the mode.
    mode = find_power_mode(prompt)
    if mode:
        print(
            json.dumps(
                {
                    "result": "info",
                    "message": f"[keyword-router] 🔥 {mode.name} mode activated",
                    "additionalContext": mode.instruction,
                }
            )
        )
        # WHY: still fall through to skill routing — power modes are additive.
        # A prompt "ralph security audit this" should activate both Persistent
        # mode AND suggest the security-audit skill.

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
