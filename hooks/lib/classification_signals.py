#!/usr/bin/env python3
"""Shared task-classification regex signals for UserPromptSubmit keyword hooks.

WHY this module exists (extracted 2026-09-08): hooks/routing_floor_classifier.py
(SAFETY-FLOOR tier: SECURITY / DESTRUCTIVE / RESEARCH) and hooks/resource_router.py
(COGNITIVE tier T0-T3; T3 = "a task already flagged SECURITY/DESTRUCTIVE by the other
hook is T3 by definition") held byte-identical copies of the SECURITY and DESTRUCTIVE
signal regexes. That duplication already cost real drift twice:

  - PR #383 (2026-09-06) fixed a "token"/"токен" homograph false-positive (an LLM/context
    token vs. an auth/API token) in routing_floor_classifier.py's SECURITY pattern only —
    resource_router.py's own copy in _T3_RE kept firing on the same false positive for a
    full day until PR #386 caught it as a separate, second fix.
  - PR #392 (2026-09-08) added health/biometric compound-phrase signals to both files by
    hand, in the same PR this time, but explicitly flagged in its own WHY comments that
    the fix was "kept in sync with routing_floor_classifier.py's own WHY comment" —
    i.e. still two copies, just edited together instead of drifting.

This module is the single source of truth those two hooks now import from. Each
exported `match_*_signal()` function returns `re.Match | None` (never raises, never
blocks) so a caller can both test truthiness and report `m.group(0)` for diagnostics —
matching the pre-refactor call sites' own `pattern.search(text)` usage exactly.

RESEARCH signals are centralized here too (routing_floor_classifier.py's own tier) even
though resource_router.py's T3 does not currently reuse them — that asymmetry predates
this refactor (T3 only composes SECURITY + DESTRUCTIVE) and is preserved as-is; this
module is a structural extraction, not a behavior change.
"""

import re

# ---------------------------------------------------------------------------
# SECURITY signals
# ---------------------------------------------------------------------------
#
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
#
# WHY (?<![\\/])\.env\b (audit, 2026-09-07, live-found): a Windows path
# ("C:\Users\serge\.env") fired SECURITY on the literal substring ".env" embedded
# in a path, not a natural-language mention of a dotenv file. Real prose never
# has a path separator directly before ".env" written out; the lookbehind excludes
# only that adjacency.
SECURITY_RE = re.compile(
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
)

# ---------------------------------------------------------------------------
# DESTRUCTIVE signals
# ---------------------------------------------------------------------------
#
# WHY (?<!-)...(?!-) around migrat(e|ion) (audit, 2026-09-07, live-found):
# a pasted git-branch-name list ("refactor/migrate-utils-facade-call-sites")
# fired DESTRUCTIVE on the literal substring "migrate" embedded in a kebab-case
# identifier, not a natural-language mention of a migration task. Real prose
# never hyphenates directly against this word ("we migrate the schema", not
# "we-migrate-the-schema"); a git slug or filename constantly does. Excluding
# hyphen-adjacency closes this without narrowing true natural-language coverage
# (plural "migrations" still matches: the lookahead only blocks a literal '-').
DESTRUCTIVE_RE = re.compile(
    r"drop\s+table|drop\s+database|truncate\b|delete\s+from|\brm\s+-rf|alter\s+table"
    r"|(?<!-)\bmigrat(e|ion)(?!-)|reset\s+--hard|force[- ]push|drop\s+index"
    r"|mass[- ]?delete"
    r"|удали(ть)?\s+(таблиц|баз|все)|миграци|снести|дроп",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# RESEARCH signals
# ---------------------------------------------------------------------------
#
# WHY (?<!-)...(?!-) around hypothes(is|es) (audit, 2026-09-07, live-found):
# same slug-adjacency false positive as the DESTRUCTIVE/migrate case above --
# a pasted branch name ("fix/backport-hypothesis-router-fixes") fired RESEARCH
# on "hypothesis" embedded in a kebab-case identifier. See that comment for the
# full asymmetric-cost rationale; same fix, same word class.
RESEARCH_RE = re.compile(
    r"(?<!-)\bhypothes(is|es)\b(?!-)|\bestimand|\bfalsif|\bcausal\b|\bexperiment\b"
    r"|гипотез|фальсифиц|причинн|эксперимент|проверить\s+гипотез",
    re.IGNORECASE,
)


def match_security_signal(text: str) -> re.Match[str] | None:
    """Return the match if `text` contains a SECURITY-tier signal, else None."""
    return SECURITY_RE.search(text)


def match_destructive_signal(text: str) -> re.Match[str] | None:
    """Return the match if `text` contains a DESTRUCTIVE-tier signal, else None."""
    return DESTRUCTIVE_RE.search(text)


def match_research_signal(text: str) -> re.Match[str] | None:
    """Return the match if `text` contains a RESEARCH-tier signal, else None."""
    return RESEARCH_RE.search(text)
