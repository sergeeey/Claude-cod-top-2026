#!/usr/bin/env python3
"""UserPromptSubmit hook: deterministically classify a task's SAFETY-FLOOR tier and
inject the mandatory routing floor for it — so the floor is enforced by code, not by the
LLM remembering to read routing-policy.

WHY (architecture: routing was soft governance): dispatcher/routing-policy DOCUMENT a
Safety Floor ("security/PII/payments review is mandatory regardless of project type;
destructive/migration ops need tests; research needs the EstimandOps L0 gate"), but
whether that floor is applied was a discretionary LLM decision. This hook is the
`project_classifier` pattern extended to the TASK tier: it runs as code, detects the tier
deterministically from the prompt, and injects the floor EVERY time — the classification
can no longer be forgotten.

HONEST SCOPE: this is *deterministic enforcement of the classification*, not a hard block.
Semantic routing (which skill fits) stays soft — that is inherent. The tool-level hard
blocks (permission_policy deny-list, security_verify on Edit|Write) remain the actual
gate; this hook makes the routing FLOOR that feeds them deterministic instead of
discretionary, closing the "routing is prompt-only" gap without any risk of breaking a
legitimate flow (it only injects context, never blocks).

Fires on: UserPromptSubmit. Non-blocking, fail-open, recursion-guarded.
"""

import os
import re
import sys

# Recursion guard — this hook must never re-enter when Claude spawns subagents.
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

from utils import emit_hook_result, hook_main, parse_stdin  # noqa: E402

# Each tier: (regex of task signals, the mandatory floor text). Signals are bilingual.
_TIERS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "SECURITY",
        re.compile(
            r"\bauth(entication|orization)?\b|\bpassword|\bsecret|\bcredential|\btoken\b"
            r"|\bapi[ _-]?key|\bpayment|\bbilling|\boauth|\bjwt\b|\.env\b|private key|\bssh\b"
            r"|\bpii\b|\bencrypt|\bpepper\b|\bhmac\b"
            r"|пароль|секрет|токен|учётн|учетн|шифрован|платёж|платеж|аутентифик|авторизац",
            re.IGNORECASE,
        ),
        "SECURITY-TIER task detected. Safety Floor is MANDATORY regardless of project "
        "type (even MVP): run the reviewer + security-audit path, never builder-solo; "
        "no secrets in code/logs; confirm before any irreversible action. This tier is "
        "set deterministically by hooks/routing_floor_classifier.py — not a suggestion.",
    ),
    (
        "DESTRUCTIVE",
        re.compile(
            r"drop\s+table|drop\s+database|truncate\b|delete\s+from|\brm\s+-rf|alter\s+table"
            r"|\bmigrat(e|ion)|reset\s+--hard|force[- ]push|drop\s+index|mass[- ]?delete"
            r"|удали(ть)?\s+(таблиц|баз|все)|миграци|снести|дроп",
            re.IGNORECASE,
        ),
        "DESTRUCTIVE/MIGRATION-TIER task detected. Safety Floor: a test is MANDATORY "
        "(even for MVP), take a checkpoint first, and confirm the irreversible step with "
        "the user. Deterministically classified — do not downgrade.",
    ),
    (
        "RESEARCH",
        re.compile(
            r"\bhypothes(is|es)\b|\bestimand|\bfalsif|\bcausal\b|\bexperiment\b"
            r"|гипотез|фальсифиц|причинн|эксперимент|проверить\s+гипотез",
            re.IGNORECASE,
        ),
        "RESEARCH/HYPOTHESIS-TIER task detected. MANDATORY first step: EstimandOps L0 gate "
        "(classify Descriptive / Predictive / Causal) BEFORE choosing a Falsification "
        "Ladder tier — never offer L0 as one menu option among many. Deterministic tier.",
    ),
]


def main() -> None:
    try:
        data = parse_stdin()
    except Exception:  # noqa: BLE001 - fail-open, never crash the harness
        sys.exit(0)

    prompt = str(data.get("prompt", "") or "")
    if not prompt.strip():
        sys.exit(0)

    matched: list[str] = []
    for name, pattern, floor in _TIERS:
        m = pattern.search(prompt)
        if m:
            matched.append(f"[routing-floor] {name} (matched: {m.group(0)!r}) — {floor}")

    if matched:
        emit_hook_result("UserPromptSubmit", "\n".join(matched))
    sys.exit(0)


if __name__ == "__main__":
    hook_main(main)
