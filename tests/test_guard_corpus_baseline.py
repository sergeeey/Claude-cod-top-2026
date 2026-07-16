#!/usr/bin/env python3
"""Baseline measurement for the prompt-injection guard, against a labelled corpus.

WHY (Sprint 2.2, experiment 20260716-response-guard-fp-calibration): the guard
scoring shared by input_guard/web_response_guard/mcp_response_guard warns on ANY
pattern hit. Measured against tests/corpus/prompt_injection/, that produces:
  - 8/13 benign security/scientific texts FALSE-POSITIVE (4 at HIGH severity), and
  - 2/12 real injections FALSE-NEGATIVE (missed because they are phrased around,
    not on, the guard's exact keywords).

This module is the FL baseline: it PINS those numbers as the state the calibration
PR must beat. The two target properties (benign stays silent; every malicious warns)
are marked xfail today -- they are the documented RED. When the calibration PR lands
and drives FP/FN toward zero, the strict xfail turns into an unexpected pass and
forces the marker's removal. That is the RED->GREEN handoff across two PRs, on purpose.

It changes NO guard behavior. The behavior change is a separate, skeptic-reviewed PR
(security code -> doubt-driven-development Trigger 3).
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
CORPUS = ROOT / "tests" / "corpus" / "prompt_injection"
sys.path.insert(0, str(ROOT / "hooks"))


def _load(name: str) -> list[dict]:
    lines = (CORPUS / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(ln) for ln in lines if ln.strip()]


def _current_verdict(text: str) -> str:
    """Reproduce the response-guards' decision: warn if ANY pattern hits.

    Mirrors web_response_guard.main()'s `if not hits: sys.exit(0)` -> otherwise warn.
    """
    from input_guard import collect_strings, is_high_threat, scan

    hits = scan(collect_strings({"output": text}))
    if not hits:
        return "silent"
    return "warn-high" if is_high_threat(hits) else "warn-low"


# --- always-green sanity: the corpus itself must be well-formed -----------------


class TestCorpusWellFormed:
    @pytest.mark.parametrize("name", ["benign", "malicious", "heldout"])
    def test_corpus_loads_and_is_labelled(self, name):
        rows = _load(name)
        floor = 8 if name == "heldout" else 10
        assert len(rows) >= floor, f"{name} corpus too small to measure a rate"
        for r in rows:
            assert r["text"].strip()
            assert r["expect"] in {"silent", "warn", "ambiguous"}
            assert r["source"] and r["why"], "every corpus row must cite a source + rationale"


# --- the documented RED: target behaviour the calibration PR must reach ---------


class TestGuardCalibrationTargets:
    """Both currently fail. Marked xfail so CI stays green while the defect is on
    record. The calibration PR removes these markers once the targets are met."""

    @pytest.mark.xfail(
        strict=True,
        reason="baseline defect: 8/13 benign texts false-positive; "
        "see experiments/20260716-response-guard-fp-calibration",
    )
    def test_benign_security_text_stays_silent(self):
        offenders = [
            r["text"][:70]
            for r in _load("benign")
            if r["expect"] == "silent" and _current_verdict(r["text"]).startswith("warn")
        ]
        assert not offenders, f"{len(offenders)} benign texts wrongly warned: {offenders}"

    @pytest.mark.xfail(
        strict=True,
        reason="baseline defect: 2/12 real injections silently missed; "
        "see experiments/20260716-response-guard-fp-calibration",
    )
    def test_every_malicious_injection_warns(self):
        missed = [
            r["text"][:70]
            for r in _load("malicious")
            if r["expect"] == "warn" and _current_verdict(r["text"]) == "silent"
        ]
        assert not missed, f"{len(missed)} real injections silently missed: {missed}"


# --- the pinned baseline numbers, asserted exactly (regression tripwire) ---------


class TestBaselinePinned:
    """If these move, the guard changed -- update them together with the experiment's
    result_summary, never silently. Green today: they assert the measured DEFECT."""

    def test_false_positive_count_matches_recorded_baseline(self):
        fp = sum(
            1
            for r in _load("benign")
            if r["expect"] == "silent" and _current_verdict(r["text"]).startswith("warn")
        )
        assert fp == 8, (
            f"benign false-positive count is {fp}, recorded baseline is 8. If a guard "
            f"change moved it, update the experiment's result_summary and this pin together."
        )

    def test_false_negative_count_matches_recorded_baseline(self):
        fn = sum(
            1
            for r in _load("malicious")
            if r["expect"] == "warn" and _current_verdict(r["text"]) == "silent"
        )
        assert fn == 2, (
            f"malicious false-negative count is {fn}, recorded baseline is 2. If a guard "
            f"change moved it, update the experiment's result_summary and this pin together."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
