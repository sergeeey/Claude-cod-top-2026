"""Tests for iteration_guard.py — enforce Evaluator-Optimizer cap=3."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from hook_state import HookState
from iteration_guard import (
    CAP,
    _extract_verdict,
    _next_count,
    _should_escalate,
)


class TestExtractVerdict:
    def test_lgtm(self):
        assert _extract_verdict("VERDICT: LGTM") == "LGTM"

    def test_needs_work(self):
        assert _extract_verdict("...\nVERDICT: NEEDS_WORK\nSEVERITY: P1") == "NEEDS_WORK"

    def test_block(self):
        assert _extract_verdict("VERDICT: BLOCK") == "BLOCK"

    def test_case_insensitive(self):
        assert _extract_verdict("verdict: lgtm") == "LGTM"

    def test_none_when_absent(self):
        assert _extract_verdict("just some agent output") is None

    def test_none_on_empty(self):
        assert _extract_verdict("") is None


class TestNextCount:
    def test_lgtm_resets(self):
        assert _next_count(2, "LGTM") == 0

    def test_needs_work_increments(self):
        assert _next_count(1, "NEEDS_WORK") == 2

    def test_block_increments(self):
        assert _next_count(0, "BLOCK") == 1


class TestShouldEscalate:
    def test_below_cap(self):
        assert not _should_escalate(2)

    def test_at_cap(self):
        assert _should_escalate(3)

    def test_above_cap(self):
        assert _should_escalate(4)

    def test_cap_value(self):
        assert CAP == 3


class TestStateRoundTrip:
    def test_save_load(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("eo_loop")
        state["sess1"] = 2
        state.save()
        assert HookState("eo_loop")["sess1"] == 2

    def test_missing_empty(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert HookState("eo_loop").get("anything") is None


class TestFullLoop:
    """Three consecutive NEEDS_WORK -> escalate; LGTM mid-way resets."""

    def test_three_failures_escalate(self):
        count = 0
        for _ in range(3):
            count = _next_count(count, "NEEDS_WORK")
        assert _should_escalate(count)

    def test_lgtm_breaks_the_chain(self):
        count = 0
        count = _next_count(count, "NEEDS_WORK")  # 1
        count = _next_count(count, "NEEDS_WORK")  # 2
        count = _next_count(count, "LGTM")  # 0 — fixed
        assert not _should_escalate(count)
        count = _next_count(count, "NEEDS_WORK")  # 1 again
        assert not _should_escalate(count)

    def test_per_session_isolation(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("eo_loop")
        state["a"] = 3
        state["b"] = 1
        state.save()
        loaded = HookState("eo_loop")
        assert _should_escalate(int(loaded["a"]))
        assert not _should_escalate(int(loaded["b"]))
