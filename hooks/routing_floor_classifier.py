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

# RESEARCH: strong terms are unambiguous on their own. The weak words "эксперимент" and
# "experiment" count only with intent: an affirmative action verb whose object they are
# (plan, start, run, design), or result/statistics words nearby. Negation is scoped to the
# verb ("не можем провести"); quoted spans and identifiers ("validate_experiment",
# "пилот-эксперименты", "эксперимент.py") never count; "какой результат" alone is not intent.
# WHY 2026-11-18: prohibitions ("не запускай эксперименты") and dev work that mentions the
# word were routed as RESEARCH; a plain word match cannot tell them from real requests.
_RESEARCH_STRONG = re.compile(
    r"\bhypothes(is|es)\b|\bestimand|\bfalsif|\bcausal\b"
    r"|гипотез|фальсифиц|причинн|проверить\s+гипотез",
    re.IGNORECASE,
)
_RESEARCH_WEAK = re.compile(r"эксперимент|experiment", re.IGNORECASE)
_INTENT_VERB = re.compile(
    r"^(?:(?:запуст|запуск|провед|провес|провел|произвел|спланир|постав|сдела|начин|начн"
    r"|нужен|нужна|хочу|давай)\w*|(?:build|design|plan|launch|conduct|set|start|run)$)",
    re.IGNORECASE,
)
_NEGATION = frozenset(
    {"не", "нет", "нельзя", "без", "ни", "never", "not", "no", "without", "avoid", "don", "cannot"}
)
_RESULT_VOCAB = re.compile(
    r"эффект|интервал|p-value|p значени|выборк|рандомиз|контрольн"
    r"|effect size|confidence interval|sample|randomi[sz]",
    re.IGNORECASE,
)
_QUOTED = re.compile(r"\"[^\"\n]*\"|«[^»\n]*»|`[^`\n]*`|(?<!\w)'[^'\n]*'(?!\w)")
_WORD = re.compile(r"[^\W_]+")

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
        _RESEARCH_STRONG,  # weak words are gated in _research_match(), not here
        "RESEARCH/HYPOTHESIS-TIER task detected. MANDATORY first step: EstimandOps L0 gate "
        "(classify Descriptive / Predictive / Causal) BEFORE choosing a Falsification "
        "Ladder tier — never offer L0 as one menu option among many. Deterministic tier.",
    ),
]


def _mask_quoted(text: str) -> str:
    """Blank quoted spans (length kept) so a quoted word cannot trigger the weak word."""
    return _QUOTED.sub(lambda m: " " * len(m.group(0)), text)


def _is_identifier(text: str, m: re.Match[str]) -> bool:
    """Weak word glued to a file name, path, identifier or hyphen compound."""
    before = text[m.start() - 1] if m.start() > 0 else " "
    after = text[m.end()] if m.end() < len(text) else " "
    after2 = text[m.end() + 1] if m.end() + 1 < len(text) else " "
    return before in "_-./\\" or after in "_-/\\" or (after == "." and after2.isalpha())


def _negated(*spans: list[str]) -> bool:
    return any(t in _NEGATION or t.startswith("никак") for span in spans for t in span)


def _has_intent_verb(words: list[str], j: int) -> bool:
    """True if an affirmative intent verb has the weak word at words[j] as its object."""
    # The verb must govern the weak word directly (at most 3 words between them). A wider
    # window matched dev prompts such as "run the unit tests and fix the experiment script".
    for k in range(j - 1, max(-1, j - 5), -1):
        if _INTENT_VERB.match(words[k]) and not _negated(
            words[k + 1 : j], words[max(0, k - 2) : k]
        ):
            return True
    for k in range(j + 1, min(len(words), j + 4)):  # verb up to 2 words after the object
        if _INTENT_VERB.match(words[k]) and not _negated(
            words[j + 1 : k], words[max(0, k - 2) : k]
        ):
            return True
    return False


def _research_match(prompt: str) -> re.Match[str] | None:
    """Return the RESEARCH signal match, or None. Weak words need intent around them."""
    strong = _RESEARCH_STRONG.search(prompt)
    if strong:
        return strong
    text = _mask_quoted(prompt)
    tokens = list(_WORD.finditer(text))
    words = [t.group(0).lower() for t in tokens]
    for m in _RESEARCH_WEAK.finditer(text):
        if _is_identifier(text, m):
            continue
        j = next((i for i, t in enumerate(tokens) if t.end() > m.start()), None)
        if j is None:
            continue
        window = text[max(0, m.start() - 80) : m.end() + 80]
        if _has_intent_verb(words, j) or _RESULT_VOCAB.search(window):
            return m
    return None


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
        m = _research_match(prompt) if name == "RESEARCH" else pattern.search(prompt)
        if m:
            matched.append(f"[routing-floor] {name} (matched: {m.group(0)!r}) — {floor}")

    if matched:
        emit_hook_result("UserPromptSubmit", "\n".join(matched))
    sys.exit(0)


if __name__ == "__main__":
    hook_main(main)
