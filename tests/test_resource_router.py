#!/usr/bin/env python3
"""Tests for hooks/resource_router.py — the deterministic cognitive-tier (T0-T3)
classifier that recommends a model without depending on the unverified
updatedInput-on-Agent mechanism (see plan Phase B1).

Key properties:
- deterministic detection of T0-T3 signals (bilingual);
- T3 takes priority over lower tiers when signals overlap (security floor implies
  highest cognitive tier too);
- NO false injection on prompts with no matching signal (over-injecting is noise);
- injects context only, never blocks.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
HOOK = ROOT / "hooks" / "resource_router.py"


def _run(prompt: str) -> str:
    """Run the hook with a prompt, return its stdout (the injected context, if any)."""
    payload = json.dumps({"prompt": prompt, "session_id": "test"})
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_INVOKED_BY": ""},
        cwd=str(ROOT),
    )
    assert r.returncode == 0, f"hook must never crash / block (exit {r.returncode}): {r.stderr}"
    return r.stdout


@pytest.mark.parametrize(
    "prompt,tier",
    [
        ("find where this function is defined", "T0"),
        ("what is this config option for", "T0"),
        ("найди где определена эта функция", "T0"),
        ("implement a retry wrapper for the api client", "T1"),
        ("fix bug in the login handler", "T1"),
        ("добавь фичу для экспорта в CSV", "T1"),
        ("debug why the tests are flaky", "T2"),
        ("review this module's architecture", "T2"),
        ("разбери почему падает тест", "T2"),
        ("add oauth token refresh to the auth flow", "T3"),
        ("drop table users and migrate the schema", "T3"),
        ("переделай платёжный модуль", "T3"),
    ],
)
def test_detects_tier(prompt, tier):
    out = _run(prompt)
    assert f"[resource-router] {tier}" in out, f"expected {tier} for: {prompt!r}\ngot: {out!r}"


def test_t3_wins_over_t1_when_both_signals_present():
    """Mutation-style: a prompt that would ALSO match T1 ("implement") must still resolve
    to T3 when it also touches a security signal -- the safety floor must not be
    downgraded by an otherwise-routine-sounding verb."""
    out = _run("implement password reset using a new secret token")
    assert "[resource-router] T3" in out
    assert "[resource-router] T1" not in out


def test_t2_wins_over_t0_when_both_signals_present():
    out = _run("find and explain why this function is slow, investigate the cause")
    assert "[resource-router] T2" in out


@pytest.mark.parametrize(
    "prompt",
    [
        "rename this variable to foo",
        "add a docstring to the function",
        "format the readme table",
    ],
)
def test_unclassified_prompt_injects_nothing(prompt):
    """A prompt matching none of the tier signals must NOT inject -- silence, not a
    forced guess, matches routing_floor_classifier.py's own convention."""
    out = _run(prompt).strip()
    assert "[resource-router]" not in out, f"false injection on {prompt!r}: {out!r}"


def test_empty_prompt_is_silent():
    assert "[resource-router]" not in _run("")


def test_never_blocks_even_on_t3_prompt():
    """Non-blocking is the safety property: this hook injects, it must never deny/exit(1)."""
    payload = json.dumps({"prompt": "delete the auth secret from the database", "session_id": "t"})
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_INVOKED_BY": ""},
        cwd=str(ROOT),
    )
    assert r.returncode == 0


def test_message_is_advisory_not_a_claim_of_enforcement():
    """Regression against overclaiming (external review, 2026-07-21, caught exactly this
    class of bug in false_pass_rate.py's naming): the injected message must not imply this
    hook silently rewrites the subagent's model -- that mechanism is unverified."""
    out = _run("fix bug in the login handler")
    assert "does not and cannot silently rewrite" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
