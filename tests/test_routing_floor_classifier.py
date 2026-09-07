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
