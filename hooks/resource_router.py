#!/usr/bin/env python3
"""UserPromptSubmit hook: deterministically classify a task's COGNITIVE-TIER (T0-T3) and
inject a recommended model/agent-count as advisory context -- so model selection stops
being "whatever the orchestrator feels like" and starts being a deterministic recommendation
the orchestrator applies via the already-proven explicit `model=` parameter on Agent().

WHY (plan: partitioned-tumbling-minsky.md, Phase C): an external review proposed a hard
PreToolUse(Agent) enforcer that silently rewrites the model field via updatedInput. That
mechanism's applicability to the Agent tool specifically is UNVERIFIED in this environment
(see the plan's Phase B1 revision history -- a real, good-faith isolated-probe attempt hit an
auth wall specific to this sandboxed session, not a design flaw). This hook does NOT depend
on that unverified mechanism at all: it follows the EXACT same proven pattern as
hooks/routing_floor_classifier.py (deterministic regex classification -> additionalContext
injection, advisory only) and relies on the orchestrator reading the recommendation and
passing model= explicitly to Agent() -- a mechanism already used throughout this session.

Two independent axes, deliberately not conflated (external review, 2026-07-21): this hook
answers "how much cognitive capability does this task need" (T0-T3). It does NOT answer
"is this action allowed" (that's risk/permission gating: permission_policy.py,
pre_vault_write.py, security_verify.py, and routing_floor_classifier.py's own SECURITY/
DESTRUCTIVE/RESEARCH safety-floor tiers -- reused here for T3, not reimplemented).

Fires on: UserPromptSubmit. Non-blocking, fail-open, recursion-guarded.
"""

import os
import re
import sys

# Recursion guard -- this hook must never re-enter when Claude spawns subagents.
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

from utils import emit_hook_result, hook_main, parse_stdin  # noqa: E402

# T3 reuses routing_floor_classifier.py's own SECURITY/DESTRUCTIVE/RESEARCH signals rather
# than re-deriving them -- a task already flagged SECURITY/DESTRUCTIVE/RESEARCH by that hook
# is T3 by definition (a risk floor implies the highest cognitive tier too: you don't want a
# cheap model reasoning about auth/PII/migrations even if the diff itself looks simple).
_T3_RE = re.compile(
    r"\bauth(entication|orization)?\b|\bpassword|\bsecret|\bcredential|\btoken\b"
    r"|\bapi[ _-]?key|\bpayment|\bbilling|\boauth|\bjwt\b|\.env\b|private key|\bssh\b"
    r"|\bpii\b|\bencrypt|\bpepper\b|\bhmac\b"
    r"|drop\s+table|drop\s+database|truncate\b|delete\s+from|\brm\s+-rf|alter\s+table"
    r"|\bmigrat(e|ion)|reset\s+--hard|force[- ]push|drop\s+index|mass[- ]?delete"
    r"|пароль|секрет|токен|учётн|учетн|шифрован|платёж|платеж|аутентифик|авторизац"
    r"|удали(ть)?\s+(таблиц|баз|все)|миграци|снести|дроп",
    re.IGNORECASE,
)

_T2_RE = re.compile(
    r"\bdebug(ging)?\b|\breview\b|\banalyz(e|ing)\b|\banaliz(e|ing)\b|\bcompare\b"
    r"|\binvestigat(e|ing)\b|\boptimiz(e|ing)\b|\bperformance\b|\barchitectur(e|al)\b"
    r"|отладк|дебаг|проверь\s+почему|разбер(и|ись)|сравни|исследуй|оптимизир|производительн"
    r"|архитектур",
    re.IGNORECASE,
)

_T1_RE = re.compile(
    r"\bimplement\b|\badd\s+feature\b|\bfix\s+bug\b|\bwrite\s+test\b|\bupdate\b|\bmodify\b"
    r"|\bcreate\b|\bедит\b|\bcode\s+change\b"
    r"|добавь|исправь|поправь|обнови|измени|создай|напиши\s+тест|реализуй",
    re.IGNORECASE,
)

_T0_RE = re.compile(
    r"\bfind\b|\bsearch\b|\bwhere\s+is\b|\bwhat\s+is\b|\bhow\s+does\b|\bexplain\b|\bread\b"
    r"|найди|поищи|где\s+находится|что\s+такое|как\s+работает|объясни|покажи|прочитай",
    re.IGNORECASE,
)

# (tier, pattern, role_hint, model_hint, agent_budget)
_TIERS: list[tuple[str, re.Pattern[str], str, str, str]] = [
    (
        "T3",
        _T3_RE,
        "reviewer + security-audit path (never builder-solo -- see routing_floor_classifier)",
        "opus (planner/judge) -- builder/tester stay sonnet even at T3, only the "
        "decision-making role needs the strongest model",
        "as needed for the security-floor path, not capped by tier alone",
    ),
    (
        "T2",
        _T2_RE,
        "explorer (facts) -> builder/tester (fix) -> reviewer (verify)",
        "sonnet, high effort",
        "up to 2 agents, 1 retry before treating the approach itself as suspect",
    ),
    (
        "T1",
        _T1_RE,
        "builder (implement) -> tester (verify)",
        "sonnet, medium effort",
        "1 agent, up to ~8 turns",
    ),
    (
        "T0",
        _T0_RE,
        "explorer (read-only)",
        "haiku, or no subagent at all -- a direct Read/Glob/Grep may be cheaper than "
        "spawning an agent for a single lookup",
        "0-1 agent, up to 3 tool calls",
    ),
]


def classify(prompt: str) -> tuple[str, str, str, str] | None:
    """Return (tier, role_hint, model_hint, agent_budget) for the highest-priority tier
    matched, or None if nothing matched (routine, unclassified -- stay silent)."""
    for tier, pattern, role_hint, model_hint, agent_budget in _TIERS:
        if pattern.search(prompt):
            return tier, role_hint, model_hint, agent_budget
    return None


def main() -> None:
    try:
        data = parse_stdin()
    except Exception:  # noqa: BLE001 - fail-open, never crash the harness
        sys.exit(0)

    prompt = str(data.get("prompt", "") or "")
    if not prompt.strip():
        sys.exit(0)

    result = classify(prompt)
    if result is None:
        sys.exit(0)
    tier, role_hint, model_hint, agent_budget = result

    msg = (
        f"[resource-router] {tier} task detected. "
        f"Recommended role chain: {role_hint}. "
        f"Recommended model: {model_hint}. "
        f"Budget: {agent_budget}. "
        f"Advisory only -- pass model= explicitly to Agent() per this recommendation "
        f"(the proven mechanism this session already uses); this hook does not and "
        f"cannot silently rewrite a subagent's model (see plan Phase B1)."
    )
    emit_hook_result("UserPromptSubmit", msg)
    sys.exit(0)


if __name__ == "__main__":
    hook_main(main)
