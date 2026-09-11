#!/usr/bin/env python3
"""Tests for hooks/routing_floor_classifier.py — the deterministic task-tier safety-floor
classifier that makes the routing floor code-enforced instead of LLM-discretionary.

Key properties:
- deterministic detection of SECURITY / DESTRUCTIVE / RESEARCH task signals (bilingual);
- NO false injection on benign prompts (over-injecting would be noise);
- injects context only, never blocks (a shadow-safe enforcement of the CLASSIFICATION).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
HOOK = ROOT / "hooks" / "routing_floor_classifier.py"


def _run(prompt: str) -> str:
    """Run the hook with a prompt, return its stdout (the injected context, if any)."""
    payload = json.dumps({"prompt": prompt, "session_id": "test"})
    env = {"CLAUDE_INVOKED_BY": ""}  # bypass recursion guard is NOT wanted; empty = proceed
    import os

    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        cwd=str(ROOT),
    )
    assert r.returncode == 0, f"hook must never crash / block (exit {r.returncode}): {r.stderr}"
    return r.stdout


@pytest.mark.parametrize(
    "prompt,tier",
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
def test_detects_tier(prompt, tier):
    out = _run(prompt)
    assert f"[routing-floor] {tier}" in out, f"expected {tier} tier for: {prompt!r}\ngot: {out!r}"


@pytest.mark.parametrize(
    "prompt",
    [
        "rename this variable to foo",
        "add a docstring to the function",
        "what does this regex match",
        "format the readme table",
    ],
)
def test_benign_prompt_injects_nothing(prompt):
    """A benign prompt must NOT trigger a floor injection -- over-injecting is noise that
    would train the reader to ignore the signal."""
    out = _run(prompt).strip()
    assert "[routing-floor]" not in out, f"false injection on benign prompt {prompt!r}: {out!r}"


def test_empty_prompt_is_silent():
    assert "[routing-floor]" not in _run("")


@pytest.mark.parametrize(
    "prompt",
    [
        # pure agent-completion notification carrying RESEARCH signal words — not a user task
        "<system-reminder>\n[SYSTEM NOTIFICATION - NOT USER INPUT]\n<task-notification>"
        '<summary>Agent "Falsify H-B1-1a hypothesis" finished</summary>'
        "<result>experiment falsified the causal claim</result></task-notification>"
        "</system-reminder>",
        # benign user text + a trailing harness block that contains a SECURITY word
        "rename this variable to foo\n<system-reminder>hooks: password rotation reminder"
        "</system-reminder>",
    ],
)
def test_harness_injected_text_is_ignored(prompt):
    """Regression (Y-17 pilot 2026-09-06): 2 of 3 NOISE firings of this hook were on
    <task-notification> text from finished subagents, not on anything the user typed."""
    out = _run(prompt).strip()
    assert "[routing-floor]" not in out, f"fired on harness text: {out!r}"


def test_user_text_still_classified_when_reminder_attached():
    out = _run("test the hypothesis that X causes Y\n<system-reminder>ctx</system-reminder>")
    assert "[routing-floor] RESEARCH" in out


@pytest.mark.parametrize(
    "prompt",
    [
        "this response cost about 150 tokens",
        "сколько токенов осталось в контексте",
        "the context window holds 200k tokens",
        "у нас ушло ~2000 токенов на этот ответ",
    ],
)
def test_bare_llm_token_mention_does_not_fire_security(prompt):
    """Regression (audit, 2026-09-06, live-found in this exact session): bare
    "token"/"токен" is a genuine homograph -- an auth/API token and an
    LLM/context token -- and the SECURITY tier previously fired on ordinary
    LLM-cost discussion with zero actual security content. Real auth-token
    prompts still fire via the other words already in the pattern (auth,
    credential, secret, api key, oauth, jwt) -- see test_detects_tier above."""
    out = _run(prompt).strip()
    assert "[routing-floor] SECURITY" not in out, (
        f"false SECURITY fire on: {prompt!r}\ngot: {out!r}"
    )


@pytest.mark.parametrize(
    "prompt,tier",
    [
        ("refresh the oauth token before it expires", "SECURITY"),
        ("the api token needs rotation, check the credential store", "SECURITY"),
        ("обнови токен авторизации в конфиге", "SECURITY"),
    ],
)
def test_token_mention_with_auth_context_still_fires_security(prompt, tier):
    """The fix removes the STANDALONE token/токен alternative, not security
    coverage overall -- a real auth-token prompt still fires via the other
    words already in the pattern (auth, credential, oauth, авторизац)."""
    out = _run(prompt)
    assert f"[routing-floor] {tier}" in out, f"expected {tier} tier for: {prompt!r}\ngot: {out!r}"


@pytest.mark.parametrize(
    "prompt",
    [
        # Windows path pasted verbatim -- ".env" is part of a file path, not a mention.
        "[env] Loaded 33 keys from C:\\Users\\serge\\.env",
        # git branch names pasted verbatim -- the words are slug fragments, not prose.
        "git branch -D refactor/migrate-utils-facade-call-sites",
        "git log fix/backport-hypothesis-router-fixes",
    ],
)
def test_slug_or_path_embedded_word_does_not_fire(prompt):
    """Regression (audit, 2026-09-07, live-found in this exact session): pasting a
    PowerShell transcript containing a Windows path and a list of git branch names
    fired SECURITY on ".env" (part of "C:\\Users\\serge\\.env"), DESTRUCTIVE on
    "migrate" (part of "refactor/migrate-utils-facade-call-sites"), and RESEARCH on
    "hypothesis" (part of "fix/backport-hypothesis-router-fixes") -- three literal
    substring matches inside path/identifier tokens, none of them an actual mention
    of the concept in natural language. See test_detects_tier and
    test_env_migrate_hypothesis_prose_still_fires for the coverage this must not lose."""
    out = _run(prompt).strip()
    assert "[routing-floor]" not in out, f"false fire on slug/path text: {prompt!r}\ngot: {out!r}"


@pytest.mark.parametrize(
    "prompt,tier",
    [
        ("check the .env file for leaked secrets", "SECURITY"),
        ("don't commit your .env to git", "SECURITY"),
        ("we need to migrate the database this weekend", "DESTRUCTIVE"),
        ("plan the migration of user data", "DESTRUCTIVE"),
        ("I have two hypotheses to compare", "RESEARCH"),
    ],
)
def test_env_migrate_hypothesis_prose_still_fires(prompt, tier):
    """The fix only excludes hyphen/path-adjacent slug embedding -- real natural-language
    mentions of .env, migrate/migration, and hypothesis/hypotheses (including plural)
    must still fire exactly as before."""
    out = _run(prompt)
    assert f"[routing-floor] {tier}" in out, f"expected {tier} tier for: {prompt!r}\ngot: {out!r}"


@pytest.mark.parametrize(
    "prompt,tier",
    [
        ("store wearable health data and biometric readings", "SECURITY"),
        ("need HIPAA compliance for this health app", "SECURITY"),
        ("import patient data from the medical record system", "SECURITY"),
        ("track the user's mental health over time", "SECURITY"),
        ("psychiatric evaluation notes go in this table", "SECURITY"),
        (
            "помогать людям отслеживать своё психоэмоциональное состояние и данные о здоровье",
            "SECURITY",
        ),
        ("нужна биометрическая аутентификация по отпечатку пальца", "SECURITY"),
        ("выгрузи медицинские данные пациента в отчёт", "SECURITY"),
    ],
)
def test_health_biometric_data_fires_security(prompt, tier):
    """Health/biometric data is special-category PII (GDPR Art.9) and was previously
    entirely unmatched by this tier — added 2026-09-08 after a live gap was found:
    a real mental-health-tracking app idea produced zero floor injection."""
    out = _run(prompt)
    assert f"[routing-floor] {tier}" in out, f"expected {tier} tier for: {prompt!r}\ngot: {out!r}"


@pytest.mark.parametrize(
    "prompt",
    [
        "run vault-health skill to audit the obsidian vault",
        "какие узкие места, покажи project health check проекта",
        "the research_health_loop.py hook fired at session start, system healthy",
        "add a healthcheck endpoint to the API",
        "как здоровье архитектуры проекта после рефакторинга",
    ],
)
def test_bare_health_mention_does_not_fire_security(prompt):
    """Regression guard for the new health/biometric alternative: this repo's own
    catalog uses bare "health"/"здоровье" heavily for architecture/CI meaning
    (vault-health skill, research_health_loop.py, "project health check", "System
    healthy" in pattern_escalation_review.py) — the new alternative is deliberately
    scoped to compound health-DATA phrases, not the bare word, to avoid repeating
    the exact false-positive class the "token" removal above already fixed once."""
    out = _run(prompt).strip()
    assert "[routing-floor] SECURITY" not in out, (
        f"false SECURITY fire on: {prompt!r}\ngot: {out!r}"
    )


# === quoted-content suppression (added 2026-09-12) ===
#
# WHY end-to-end tests here too, not just in test_classification_signals.py's
# unit tests for is_likely_quoted_occurrence: this hook's main() re-checks the
# trailing window against the SAME matcher before honoring suppression --
# that composition is only exercised by running the actual hook.

# WHY varied section text, not one block repeated N times: an earlier draft
# repeated a single "credential"-containing block to reach length, which put
# a SECOND occurrence of the same word inside the suppression check's own
# trailing re-scan window purely from the repeat cadence -- a fixture
# artifact, not the real incident shape, and it defeated the very regression
# test it was meant to support (found live: replaced repetition with varied
# section text and the false failure disappeared). Real pasted analyses
# don't repeat a paragraph; each section here is distinct so the buried
# SECURITY word occurs exactly once, nowhere near the tail.
_PASTED_DOC = (
    "# Architecture comparison\n\n"
    "## Section 1 — Overview\n\n"
    "This section lays out the general shape of the third-party system under "
    "discussion, its major components, and how they relate to one another in "
    "broad strokes before any detailed comparison begins. ([Some Source][1])\n\n"
    "## Section 2 — Deep dive\n\n"
    "Here the analysis goes further into specifics: how each subsystem "
    "communicates, what assumptions it makes about its environment, and where "
    "the credential handling in that other system fits into the larger flow. "
    "([Some Source][2])\n\n"
    "## Section 3 — Prior art\n\n"
    "A survey of related approaches from other projects, comparing tradeoffs "
    "across several dimensions and citing the sources each claim rests on. "
    "([Some Source][3])\n\n"
    "## Section 4 — Open questions\n\n"
    "Several open questions remain about how well this generalizes, what the "
    "failure modes look like under load, and whether the same design would "
    "hold up outside its original context. ([Some Source][4])\n\n"
    "## Section 5 — Summary table\n\n"
    "| Aspect | This system | Alternative |\n|---|---|---|\n"
    "| Latency | low | medium |\n| Complexity | medium | high |\n"
    "| Maturity | new | established |\n\n"
    "## Section 6 — Closing thoughts\n\n"
    "Taken together, the comparison suggests a mixed picture: some ideas "
    "transfer cleanly, others depend heavily on assumptions that may not hold "
    "in a different setting, and a few remain genuinely open. ([Some Source][5])\n\n"
    "## Section 7 — Recommendations\n\n"
    "Given everything above, the most defensible next step is a small, "
    "reversible experiment rather than a wholesale adoption of the compared "
    "design, since the evidence so far only supports a narrow claim about "
    "where the two systems actually differ in practice. ([Some Source][6])\n\n"
)
assert len(_PASTED_DOC) > 1500  # must clear the quoted-content length threshold


def test_keyword_buried_in_long_pasted_document_does_not_fire():
    """The real incident this session hit four times: a tier keyword sitting
    deep inside a long pasted analysis, followed by an unrelated short live
    instruction. Must not inject the SECURITY floor."""
    prompt = _PASTED_DOC + "оцень внимательно изучи и сравни с нашей реализацией"
    out = _run(prompt).strip()
    assert "[routing-floor] SECURITY" not in out, f"false fire on pasted-document tail: {out!r}"


def test_live_security_ask_after_a_long_paste_still_fires():
    """The regression this heuristic must never cause: a genuine live security
    ask that happens to follow a long paste must still inject the floor."""
    prompt = _PASTED_DOC + "now go check the credential store for this repo"
    out = _run(prompt)
    assert "[routing-floor] SECURITY" in out, f"suppressed a genuine live ask: {out!r}"


def test_never_blocks_even_on_security_prompt():
    """Non-blocking is the safety property: this hook injects, it must never deny/exit(1)."""
    # covered by the exit-0 assertion in _run, but assert explicitly for the security case
    payload = json.dumps({"prompt": "delete the auth secret from the database", "session_id": "t"})
    import os

    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_INVOKED_BY": ""},
        cwd=str(ROOT),
    )
    assert r.returncode == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
