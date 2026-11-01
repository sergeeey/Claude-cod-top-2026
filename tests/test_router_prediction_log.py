#!/usr/bin/env python3
"""Tests for resource_router.py's prediction log — the predicted half of the
router-calibration pair.

WHY this log exists: the router emitted its tier verdict as advisory prose and
recorded it nowhere, so a recommendation that was followed and one that was
ignored left the identical trace. `hooks/model_switch_tracker.py` records which
model a session actually ran on; this records what was predicted. Neither is
useful alone; together they make the router's accuracy a measurable quantity
instead of an asserted one.

The properties pinned below are the ones that, if they broke silently, would
leave a plausible-looking file that cannot answer the question it was built for:

  - a classified prompt produces exactly one row, with the tier
  - an UNclassified prompt produces no row (otherwise the base rate is wrong)
  - the join key matches model_switches.jsonl's truncation exactly
  - the prompt text is never stored
  - the log honours CLAUDE_HOME, so a test run cannot pollute real telemetry
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
HOOK = ROOT / "hooks" / "resource_router.py"


def _run(prompt: str, home: Path, session_id: str = "abc12345def") -> list[dict]:
    payload = json.dumps({"prompt": prompt, "session_id": session_id, "cwd": "/repo"})
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_INVOKED_BY": "", "CLAUDE_HOME": str(home)},
        cwd=str(ROOT),
    )
    assert r.returncode == 0, f"hook must never block (exit {r.returncode}): {r.stderr}"
    log = home / "logs" / "router_predictions.jsonl"
    if not log.exists():
        return []
    return [json.loads(x) for x in log.read_text(encoding="utf-8").strip().splitlines() if x]


class TestPredictionLog:
    def test_classified_prompt_writes_one_row_with_its_tier(self, tmp_path):
        rows = _run("нужно проверить авторизацию и PII в этом коде", tmp_path)
        assert len(rows) == 1
        assert rows[0]["tier"] == "T3"
        assert rows[0]["model_hint"]
        assert rows[0]["cwd"] == "/repo"
        assert rows[0]["ts"]

    def test_unclassified_prompt_writes_nothing(self, tmp_path):
        """The router stays silent on routine prompts, and the log must agree.

        If a silent classification still wrote a row, the denominator of every
        later "how often was tier X predicted" question would be wrong -- the
        log would report the router firing on prompts where it did not.
        """
        assert _run("привет", tmp_path) == []

    def test_join_key_truncation_matches_model_switches(self, tmp_path):
        """sid is truncated to 8 chars here AND in model_switch_tracker.

        Two append-only logs that disagree about their own join key cannot be
        joined at all, which would quietly defeat the entire point of the pair.
        """
        rows = _run("implement the feature and add tests", tmp_path, session_id="abc12345def")
        assert rows
        assert rows[0]["sid"] == "abc12345"

    def test_prompt_text_is_never_stored(self, tmp_path):
        """Only the length is kept.

        A prompt is arbitrary user text and can carry paths, tokens or personal
        data. The router-accuracy question needs the tier and the outcome, never
        the wording, so storing it would take on a data-handling risk that buys
        nothing.
        """
        secret = "implement login with password hunter2 and add tests"
        rows = _run(secret, tmp_path)
        assert rows
        blob = json.dumps(rows[0], ensure_ascii=False)
        assert "hunter2" not in blob
        assert "login" not in blob
        assert rows[0]["prompt_len"] == len(secret)

    def test_appends_across_invocations(self, tmp_path):
        _run("implement the feature and add tests", tmp_path)
        rows = _run("нужно проверить авторизацию и PII в этом коде", tmp_path)
        assert len(rows) == 2
        assert [r["tier"] for r in rows] == ["T1", "T3"]


class TestIsolation:
    def test_claude_home_redirects_the_log(self, tmp_path):
        """Without this, every subprocess-based router test pollutes real telemetry."""
        home = tmp_path / "sandbox"
        rows = _run("нужно проверить авторизацию и PII в этом коде", home)
        assert rows, "row must land inside the redirected home"
        assert (home / "logs" / "router_predictions.jsonl").is_file()

    def test_hook_still_emits_its_advisory(self, tmp_path):
        """The log is additive: the advisory output must be unchanged.

        This is the invariant the whole change rests on -- adding telemetry to a
        live advisory path must not alter what that path advises.
        """
        payload = json.dumps({"prompt": "нужно проверить авторизацию и PII", "session_id": "s"})
        r = subprocess.run(
            [sys.executable, str(HOOK)],
            input=payload,
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_INVOKED_BY": "", "CLAUDE_HOME": str(tmp_path)},
            cwd=str(ROOT),
        )
        assert r.returncode == 0
        assert "resource-router" in r.stdout
        assert "T3" in r.stdout
