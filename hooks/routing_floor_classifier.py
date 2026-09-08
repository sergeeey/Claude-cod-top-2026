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

from lib.runtime import emit_hook_result, hook_main, parse_stdin, strip_non_user_content

# Each tier: (regex of task signals, the mandatory floor text). Signals are bilingual.
_TIERS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "SECURITY",
        # WHY bare "token"/"токен" removed (audit, 2026-09-06, live-found): both are
        # genuine homographs -- an auth/API token and an LLM/context token -- and this
        # hook fired SECURITY-tier on ordinary LLM-cost discussion ("~150 tokens",
        # "стоит N токенов") with zero actual security content. Real auth-token
        # discussions overwhelmingly co-occur with one of the other words already in
        # this pattern (auth, credential, secret, api key, oauth, jwt) -- removing the
        # standalone alternative closes the common false-positive without meaningfully
        # narrowing true-positive coverage. Same asymmetric-cost reasoning already
        # applied to resolve_route.py's weak-signal split: a missed floor injection is
        # cheap (the model's own judgment still applies), a false SECURITY-tier
        # injection on an unrelated ML discussion is the more expensive failure mode.
        #
        # WHY health/biometric terms are COMPOUND phrases, not bare "health"/"здоровье"
        # (added 2026-09-08, live-found: this exact repo's own catalog uses "health" for
        # architecture/CI meaning -- `research_health_loop.py`, the `vault-health` skill,
        # "project health check", "System healthy" in pattern_escalation_review.py -- a
        # bare "health" alternative would fire SECURITY-tier on ordinary meta-discussion
        # about this repo's own tooling. Same asymmetric-cost reasoning as the "token"
        # removal above, applied in the opposite direction: scope the new alternative to
        # phrases that only occur in a genuine health-DATA context (grep-verified against
        # this repo before adding: zero hits for "biometric"/"psychiatric"/"mental health"/
        # "медицинск"/"биометри"/"психиатр"/"психоэмоц" outside the one skill that is
        # already, correctly, a compliance skill -- data-breach-blast-radius's own HIPAA
        # trigger). Health/biometric data is special-category PII under GDPR Art.9 and
        # was previously entirely unmatched by this tier.
        re.compile(
            r"\bauth(entication|orization)?\b|\bpassword|\bsecret|\bcredential"
            r"|\bapi[ _-]?key|\bpayment|\bbilling|\boauth|\bjwt\b|(?<![\\/])\.env\b"
            r"|private key|\bssh\b"
            r"|\bpii\b|\bencrypt|\bpepper\b|\bhmac\b"
            r"|\bbiometric|\bhipaa\b|\bpsychiatric\b|medical\s+record|patient\s+data"
            r"|mental\s+health|health\s+data"
            r"|пароль|секрет|учётн|учетн|шифрован|платёж|платеж|аутентифик|авторизац"
            r"|биометри|психиатр|психоэмоц|медицинск\w*\s+(данн\w*|карт\w*|запис\w*)"
            r"|данн\w*\s+о\s+здоровье",
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
            # WHY (?<!-)...(?!-) around migrat(e|ion) (audit, 2026-09-07, live-found):
            # a pasted git-branch-name list ("refactor/migrate-utils-facade-call-sites")
            # fired DESTRUCTIVE on the literal substring "migrate" embedded in a kebab-case
            # identifier, not a natural-language mention of a migration task. Real prose
            # never hyphenates directly against this word ("we migrate the schema", not
            # "we-migrate-the-schema"); a git slug or filename constantly does. Excluding
            # hyphen-adjacency closes this without narrowing true natural-language coverage
            # (plural "migrations" still matches: the lookahead only blocks a literal '-').
            r"drop\s+table|drop\s+database|truncate\b|delete\s+from|\brm\s+-rf|alter\s+table"
            r"|(?<!-)\bmigrat(e|ion)(?!-)|reset\s+--hard|force[- ]push|drop\s+index"
            r"|mass[- ]?delete"
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
            # WHY (?<!-)...(?!-) around hypothes(is|es) (audit, 2026-09-07, live-found):
            # same slug-adjacency false positive as the DESTRUCTIVE/migrate case above --
            # a pasted branch name ("fix/backport-hypothesis-router-fixes") fired RESEARCH
            # on "hypothesis" embedded in a kebab-case identifier. See that comment for the
            # full asymmetric-cost rationale; same fix, same word class.
            r"(?<!-)\bhypothes(is|es)\b(?!-)|\bestimand|\bfalsif|\bcausal\b|\bexperiment\b"
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
    except Exception:
        sys.exit(0)

    # WHY strip: agent completion notifications arrive through this same event; classifying
    # their text produced 2/3 of this hook's false firings in the Y-17 pilot (2026-09-06).
    prompt = strip_non_user_content(str(data.get("prompt", "") or ""))
    if not prompt:
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
