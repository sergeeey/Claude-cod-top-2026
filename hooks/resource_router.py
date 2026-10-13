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

import json
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

# Recursion guard -- this hook must never re-enter when Claude spawns subagents.
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

import re

from lib.classification_signals import match_destructive_signal, match_security_signal
from lib.runtime import emit_hook_result, hook_main, parse_stdin, strip_non_user_content
from lib.state import rotate_log_if_large


# T3 reuses routing_floor_classifier.py's own SECURITY/DESTRUCTIVE signals (via
# lib/classification_signals.py) rather than re-deriving them -- a task already flagged
# SECURITY/DESTRUCTIVE by that hook is T3 by definition (a risk floor implies the highest
# cognitive tier too: you don't want a cheap model reasoning about auth/PII/migrations
# even if the diff itself looks simple). See that module's docstring for the drift
# incident (PR #383/#386/#392) that motivated centralizing these signals in one place.
def _match_t3(text: str) -> re.Match[str] | None:
    return match_security_signal(text) or match_destructive_signal(text)


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

# (tier, signal matcher, role_hint, model_hint, agent_budget)
_TIERS: list[tuple[str, Callable[[str], re.Match[str] | None], str, str, str]] = [
    (
        "T3",
        _match_t3,
        "reviewer + security-audit path (never builder-solo -- see routing_floor_classifier)",
        "opus (planner/judge) -- builder/tester stay sonnet even at T3, only the "
        "decision-making role needs the strongest model",
        "as needed for the security-floor path, not capped by tier alone",
    ),
    (
        "T2",
        _T2_RE.search,
        "explorer (facts) -> builder/tester (fix) -> reviewer (verify)",
        "sonnet, high effort",
        "up to 2 agents, 1 retry before treating the approach itself as suspect",
    ),
    (
        "T1",
        _T1_RE.search,
        "builder (implement) -> tester (verify)",
        "sonnet, medium effort",
        "1 agent, up to ~8 turns",
    ),
    (
        "T0",
        _T0_RE.search,
        "explorer (read-only)",
        "haiku, or no subagent at all -- a direct Read/Glob/Grep may be cheaper than "
        "spawning an agent for a single lookup",
        "0-1 agent, up to 3 tool calls",
    ),
]


def _prediction_log() -> Path:
    """Resolve the log path, honouring CLAUDE_HOME / CLAUDE_CONFIG_DIR.

    WHY resolved per call and not a module constant: tests/test_resource_router.py
    runs this hook as a SUBPROCESS, so a constant bound at import time cannot be
    monkeypatched, and every one of those tests would append a row -- carrying
    session_id "test" -- to the maintainer's real telemetry. A measurement
    corrupted by its own test suite is worse than no measurement, so the path has
    to be redirectable from the environment. The same two variables are already
    the convention here; see live_drift_guard.resolve_claude_home.
    """
    env = os.environ.get("CLAUDE_HOME") or os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(env) if env else Path.home() / ".claude"
    return base / "logs" / "router_predictions.jsonl"


def _log_prediction(data: dict, prompt: str, tier: str, model_hint: str) -> None:
    """Record the tier this hook predicted, so the prediction becomes checkable.

    WHY this exists (2026-09-10): this hook has always emitted its verdict as
    advisory prose and written it nowhere. A recommendation that gets followed
    and one that gets ignored therefore produced the identical text and the
    identical trace -- none -- so the router's accuracy has never been
    measurable, only asserted. `hooks/model_switch_tracker.py` records which
    model a session ACTUALLY ran on; this is the predicted side of that pair.

    WHY `sid` is truncated to 8 characters here too: it is the join key against
    model_switches.jsonl, which truncates identically. Two logs that disagree
    about their own key cannot be joined at all, so the duplication is
    deliberate, not accidental.

    WHY the prompt is NOT stored, only its length: a prompt is arbitrary user
    text and can carry anything -- paths, tokens, personal data. The router's
    accuracy question needs the tier and the outcome, never the wording, so
    storing it would take on a data-handling risk that buys nothing.

    Fail-open by construction: telemetry never justifies failing a session.
    """
    try:
        log_path = _prediction_log()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        rotate_log_if_large(log_path)
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "sid": (data.get("session_id") or "")[:8],
            "tier": tier,
            "model_hint": model_hint,
            "cwd": data.get("cwd"),
            "prompt_len": len(prompt),
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def classify(prompt: str) -> tuple[str, str, str, str] | None:
    """Return (tier, role_hint, model_hint, agent_budget) for the highest-priority tier
    matched, or None if nothing matched (routine, unclassified -- stay silent)."""
    for tier, matcher, role_hint, model_hint, agent_budget in _TIERS:
        if matcher(prompt):
            return tier, role_hint, model_hint, agent_budget
    return None


def main() -> None:
    try:
        data = parse_stdin()
    except Exception:
        sys.exit(0)

    # WHY strip: see lib.runtime.strip_non_user_content — harness notifications are not tasks.
    prompt = strip_non_user_content(str(data.get("prompt", "") or ""))
    if not prompt:
        sys.exit(0)

    result = classify(prompt)
    if result is None:
        sys.exit(0)
    tier, role_hint, model_hint, agent_budget = result

    # WHY before emit and not after: emit_hook_result is the last thing this
    # hook does, and a prediction that is only recorded when the advisory
    # happens to succeed would silently under-count exactly the cases worth
    # studying. The write itself cannot raise -- see _log_prediction.
    _log_prediction(data, prompt, tier, model_hint)

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
