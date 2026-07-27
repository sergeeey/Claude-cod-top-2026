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


def test_never_blocks_even_on_security_prompt():
    """Non-blocking is the safety property: this hook injects, it must never deny/exit(1)."""
    # covered by the exit-0 assertion in _run, but assert explicitly for the security case
    payload = json.dumps({"prompt": "delete the auth secret from the database", "session_id": "t"})
    import os

    r = subprocess.run(
        [sys.executable, str(HOOK)], input=payload, capture_output=True, text=True,
        env={**os.environ, "CLAUDE_INVOKED_BY": ""}, cwd=str(ROOT),
    )
    assert r.returncode == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
