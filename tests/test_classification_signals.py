"""Tests for lib.classification_signals — the SECURITY/DESTRUCTIVE/RESEARCH regex
signals shared between hooks/routing_floor_classifier.py's safety-floor tiers and
hooks/resource_router.py's T3 cognitive tier.

This is the single regression corpus for the signals themselves (previously duplicated
almost verbatim across tests/test_routing_floor_classifier.py and
tests/test_resource_router.py — see lib/classification_signals.py's own docstring for
the drift incidents, PR #383/#386/#392, that motivated centralizing both the signals and
their test coverage in one place). Tests specific to each HOOK's own wiring (message
format, tier priority, harness-notification stripping, non-blocking behavior) stay in
those two files.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from lib.classification_signals import (  # noqa: E402
    match_destructive_signal,
    match_research_signal,
    match_security_signal,
)

_MATCHERS = {
    "SECURITY": match_security_signal,
    "DESTRUCTIVE": match_destructive_signal,
    "RESEARCH": match_research_signal,
}


@pytest.mark.parametrize(
    "text,signal",
    [
        ("add oauth token refresh to the auth flow", "SECURITY"),
        ("store the api_key in the config", "SECURITY"),
        ("переделай платёжный модуль", "SECURITY"),
        ("drop table users and migrate the schema", "DESTRUCTIVE"),
        ("run rm -rf on the cache dir", "DESTRUCTIVE"),
        ("снести миграцию и пересоздать таблицу", "DESTRUCTIVE"),
        ("test the hypothesis that X causes Y", "RESEARCH"),
        ("проверить гипотезу о причинной связи", "RESEARCH"),
    ],
)
def test_detects_signal(text, signal):
    assert _MATCHERS[signal](text), f"expected {signal} signal in: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "rename this variable to foo",
        "add a docstring to the function",
        "what does this regex match",
        "format the readme table",
    ],
)
def test_benign_text_matches_nothing(text):
    for signal, matcher in _MATCHERS.items():
        assert not matcher(text), f"false {signal} match on benign text: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "this response cost about 150 tokens",
        "сколько токенов осталось в контексте",
        "the context window holds 200k tokens",
        "у нас ушло ~2000 токенов на этот ответ",
    ],
)
def test_bare_llm_token_mention_does_not_fire_security(text):
    """Regression (audit, 2026-09-06, live-found): bare "token"/"токен" is a genuine
    homograph -- an auth/API token and an LLM/context token -- and SECURITY previously
    fired on ordinary LLM-cost discussion with zero actual security content. Real
    auth-token prompts still fire via the other words already in the pattern (auth,
    credential, secret, api key, oauth, jwt) -- see test_detects_signal above."""
    assert not match_security_signal(text), f"false SECURITY fire on: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "refresh the oauth token before it expires",
        "the api token needs rotation, check the credential store",
        "обнови токен авторизации в конфиге",
    ],
)
def test_token_mention_with_auth_context_still_fires_security(text):
    """The fix removes the STANDALONE token/токен alternative, not security coverage
    overall -- a real auth-token prompt still fires via the other words already in
    the pattern (auth, credential, oauth, авторизац)."""
    assert match_security_signal(text), f"expected SECURITY signal in: {text!r}"


@pytest.mark.parametrize(
    "text,signal",
    [
        # Windows path pasted verbatim -- ".env" is part of a file path, not a mention.
        ("[env] Loaded 33 keys from C:\\Users\\serge\\.env", "SECURITY"),
        # git branch names pasted verbatim -- the words are slug fragments, not prose.
        ("git branch -D refactor/migrate-utils-facade-call-sites", "DESTRUCTIVE"),
        ("git log fix/backport-hypothesis-router-fixes", "RESEARCH"),
    ],
)
def test_slug_or_path_embedded_word_does_not_fire(text, signal):
    """Regression (audit, 2026-09-07, live-found): pasting a PowerShell transcript
    containing a Windows path and a list of git branch names fired SECURITY on ".env"
    (part of "C:\\Users\\serge\\.env"), DESTRUCTIVE on "migrate" (part of
    "refactor/migrate-utils-facade-call-sites"), and RESEARCH on "hypothesis" (part of
    "fix/backport-hypothesis-router-fixes") -- three literal substring matches inside
    path/identifier tokens, none of them an actual mention of the concept in natural
    language. See test_detects_signal and test_env_migrate_hypothesis_prose_still_fires
    for the coverage this must not lose."""
    assert not _MATCHERS[signal](text), f"false {signal} fire on slug/path text: {text!r}"


@pytest.mark.parametrize(
    "text,signal",
    [
        ("check the .env file for leaked secrets", "SECURITY"),
        ("don't commit your .env to git", "SECURITY"),
        ("we need to migrate the database this weekend", "DESTRUCTIVE"),
        ("plan the migration of user data", "DESTRUCTIVE"),
        ("I have two hypotheses to compare", "RESEARCH"),
    ],
)
def test_env_migrate_hypothesis_prose_still_fires(text, signal):
    """The fix only excludes hyphen/path-adjacent slug embedding -- real natural-language
    mentions of .env, migrate/migration, and hypothesis/hypotheses (including plural)
    must still fire exactly as before."""
    assert _MATCHERS[signal](text), f"expected {signal} signal in: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "store wearable health data and biometric readings",
        "need HIPAA compliance for this health app",
        "import patient data from the medical record system",
        "track the user's mental health over time",
        "psychiatric evaluation notes go in this table",
        "помогать людям отслеживать своё психоэмоциональное состояние и данные о здоровье",
        "нужна биометрическая аутентификация по отпечатку пальца",
        "выгрузи медицинские данные пациента в отчёт",
    ],
)
def test_health_biometric_data_fires_security(text):
    """Health/biometric data is special-category PII (GDPR Art.9) and was previously
    entirely unmatched by this tier -- added 2026-09-08 after a live gap was found:
    a real mental-health-tracking app idea produced zero floor injection."""
    assert match_security_signal(text), f"expected SECURITY signal in: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "run vault-health skill to audit the obsidian vault",
        "какие узкие места, покажи project health check проекта",
        "the research_health_loop.py hook fired at session start, system healthy",
        "add a healthcheck endpoint to the API",
        "как здоровье архитектуры проекта после рефакторинга",
    ],
)
def test_bare_health_mention_does_not_fire_security(text):
    """Regression guard for the health/biometric alternative: this repo's own catalog
    uses bare "health"/"здоровье" heavily for architecture/CI meaning (vault-health
    skill, research_health_loop.py, "project health check", "System healthy" in
    pattern_escalation_review.py) -- the alternative is deliberately scoped to compound
    health-DATA phrases, not the bare word, to avoid repeating the exact false-positive
    class the "token" removal above already fixed once."""
    assert not match_security_signal(text), f"false SECURITY fire on: {text!r}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
