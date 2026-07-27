"""Tests for iteration_guard.py — enforce Evaluator-Optimizer cap=3."""

import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from hook_state import HookState
from iteration_guard import (
    CAP,
    _extract_subagent_type,
    _extract_verdict,
    _next_count,
    _should_escalate,
)


def _stdin(data: dict) -> io.StringIO:
    return io.StringIO(json.dumps(data))


def _agent_call(subagent_type: str, session_id: str = "sess1") -> dict:
    return {
        "tool_name": "Agent",
        "tool_input": {"subagent_type": subagent_type},
        "session_id": session_id,
    }


def _subagent_stop(message: str, session_id: str = "sess1") -> dict:
    return {"last_assistant_message": message, "session_id": session_id}


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


class TestExtractSubagentType:
    def test_subagent_type_key(self):
        assert _extract_subagent_type({"subagent_type": "Reviewer"}) == "reviewer"

    def test_agent_type_fallback(self):
        assert _extract_subagent_type({"agent_type": "builder"}) == "builder"

    def test_missing_returns_empty(self):
        assert _extract_subagent_type({}) == ""

    def test_non_string_ignored(self):
        assert _extract_subagent_type({"subagent_type": 123}) == ""


class TestPreToolUseBlocking:
    """Regression (cross-model audit gap #8, closed per explicit user decision
    "iteration_guard.py cap=3 should block, not just warn"): a 4th
    reviewer<->builder cycle previously only got extra additionalContext, not
    an actual block. PreToolUse(Agent) now denies the call outright while the
    per-session counter is >= CAP."""

    def _set_count(self, monkeypatch, tmp_path, session_id: str, count: int) -> None:
        # WHY chdir FIRST: HookState captures Path.cwd() at construction time,
        # so the state must be written under tmp_path, not whatever the
        # current directory happened to be when the test started.
        # WHY a signed {count, sig} dict, not a bare int (F-04 follow-up):
        # after removing the legacy bare-int trust path (a bare int was
        # indistinguishable from the exact reset-to-zero bypass this fix
        # closes), a bare int here would now ALWAYS fail closed to CAP
        # regardless of the count requested, breaking every test in this
        # class. This helper must go through the same signing path
        # _handle_subagent_stop uses.
        import iteration_guard

        monkeypatch.chdir(tmp_path)
        state = HookState("eo_loop")
        state[session_id] = {"count": count, "sig": iteration_guard._sign(session_id, count)}
        state.save()

    def _run(self, monkeypatch, tmp_path, data: dict):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys.stdin", _stdin(data))
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)

        import iteration_guard

        with pytest.raises(SystemExit) as exc:
            iteration_guard.main()
        return exc.value.code

    def test_denies_reviewer_call_when_cap_reached(self, monkeypatch, tmp_path, capsys):
        self._set_count(monkeypatch, tmp_path, "sess1", CAP)

        code = self._run(monkeypatch, tmp_path, _agent_call("reviewer"))

        assert code == 0
        captured = capsys.readouterr()
        assert '"permissionDecision": "deny"' in captured.out

    def test_denies_builder_call_when_cap_reached(self, monkeypatch, tmp_path, capsys):
        self._set_count(monkeypatch, tmp_path, "sess1", CAP)

        self._run(monkeypatch, tmp_path, _agent_call("builder"))

        captured = capsys.readouterr()
        assert '"permissionDecision": "deny"' in captured.out

    def test_allows_first_three_cycles(self, monkeypatch, tmp_path, capsys):
        """Counts 0, 1, 2 (below CAP=3) must all still be allowed — only
        the 4th cycle (count already at CAP) is denied."""
        for count in range(CAP):
            self._set_count(monkeypatch, tmp_path, "sess1", count)

            self._run(monkeypatch, tmp_path, _agent_call("reviewer"))

            captured = capsys.readouterr()
            assert captured.out == "", f"count={count} should not be blocked yet"

    def test_lgtm_resets_and_unblocks(self, monkeypatch, tmp_path, capsys):
        """The gate is not permanent: an LGTM verdict on SubagentStop resets
        the counter, and the next Agent(reviewer) call is allowed again."""
        self._set_count(monkeypatch, tmp_path, "sess1", CAP)

        # Blocked before the reset.
        self._run(monkeypatch, tmp_path, _agent_call("reviewer"))
        assert '"permissionDecision": "deny"' in capsys.readouterr().out

        # An LGTM verdict resets the counter for this session.
        self._run(monkeypatch, tmp_path, _subagent_stop("VERDICT: LGTM"))
        capsys.readouterr()  # drain SubagentStop's own output, if any

        # Now the same session's next reviewer call is allowed again.
        self._run(monkeypatch, tmp_path, _agent_call("reviewer"))
        assert capsys.readouterr().out == ""

    def test_other_subagent_types_never_blocked(self, monkeypatch, tmp_path, capsys):
        """Only the reviewer<->builder pair is gated — explorer/tester/
        boyko-agent/etc. must never be blocked by this hook, no matter how
        high the counter is."""
        self._set_count(monkeypatch, tmp_path, "sess1", CAP + 5)

        for subagent in ("explorer", "tester", "boyko-agent", "skeptic"):
            self._run(monkeypatch, tmp_path, _agent_call(subagent))
            assert capsys.readouterr().out == "", f"{subagent} should never be blocked"

    def test_non_agent_tool_ignored(self, monkeypatch, tmp_path, capsys):
        self._set_count(monkeypatch, tmp_path, "sess1", CAP)

        data = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "session_id": "sess1"}
        self._run(monkeypatch, tmp_path, data)

        assert capsys.readouterr().out == ""

    def test_different_session_not_affected(self, monkeypatch, tmp_path, capsys):
        """The cap is per-session — a different session_id must not inherit
        another session's blocked state."""
        self._set_count(monkeypatch, tmp_path, "sess1", CAP)

        self._run(monkeypatch, tmp_path, _agent_call("reviewer", session_id="sess2"))

        assert capsys.readouterr().out == ""

    def test_corrupted_state_value_never_crashes_the_hook(self, monkeypatch, tmp_path, capsys):
        """Regression (P2, reviewer-agent pass; behavior revised by F-04,
        security audit 2026-07-12): a non-numeric value in eo_loop.json
        (e.g. a corrupted write) must not CRASH the hook — that guarantee
        is unchanged. What changed: it is no longer treated as count=0
        (allow). F-04's tamper-evidence fix intentionally removed the
        fail-OPEN response to any unsigned value, because "corrupted
        garbage" and "an agent's Write(..., '{\"sess1\": 0}') reset attempt"
        are indistinguishable at this layer -- fail-open for one silently
        fail-opens for both. The hook must still never raise/crash; it now
        fails CLOSED (forces count to CAP) instead of open."""
        monkeypatch.chdir(tmp_path)
        state = HookState("eo_loop")
        state["sess1"] = "not-a-number"
        state.save()

        code = self._run(monkeypatch, tmp_path, _agent_call("reviewer"))

        assert code == 0  # never crashes
        assert '"permissionDecision": "deny"' in capsys.readouterr().out  # fails closed


class TestTamperEvidence:
    """F-04 (security audit 2026-07-12): the cap=3 counter lived in a plain,
    unprotected eo_loop.json -- an agent could reset it to 0 by editing the
    file directly, trivially bypassing the Evaluator-Optimizer cap. Fix: a
    signature stored alongside the count, checked on read. Not a hard
    security boundary against a determined agent with shell access (that's
    inherent to any same-machine guard) -- raises the bar against casual/
    accidental tampering and makes deliberate tampering detectable."""

    def _run(self, monkeypatch, tmp_path, data: dict):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys.stdin", _stdin(data))
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)

        import iteration_guard

        with pytest.raises(SystemExit) as exc:
            iteration_guard.main()
        return exc.value.code

    def test_legitimately_signed_low_count_allows(self, monkeypatch, tmp_path, capsys):
        """A count genuinely written by _handle_subagent_stop (correctly
        signed) below the cap must still allow the call — the fix must not
        make the gate MORE restrictive than before for honest state."""
        import iteration_guard

        monkeypatch.chdir(tmp_path)
        state = HookState("eo_loop")
        state["sess1"] = {"count": 1, "sig": iteration_guard._sign("sess1", 1)}
        state.save()

        code = self._run(monkeypatch, tmp_path, _agent_call("reviewer"))

        assert code == 0
        assert capsys.readouterr().out == ""  # not blocked

    def test_hand_edited_count_is_detected_and_forced_to_cap(self, monkeypatch, tmp_path, capsys):
        """The core regression: an agent (or a casual manual edit) resets
        eo_loop.json's count to 0 without going through the signing path --
        this must NOT silently reset the cap. Detected via signature
        mismatch, forced to CAP (fail closed), not trusted as a fresh 0."""
        monkeypatch.chdir(tmp_path)
        state = HookState("eo_loop")
        # WHY count=0 with NO signature (or a signature for a different
        # count): exactly what `state["sess1"] = 0` (the old bare reset)
        # or a hand-edited JSON file would produce.
        state["sess1"] = {"count": 0, "sig": "not-the-real-signature"}
        state.save()

        code = self._run(monkeypatch, tmp_path, _agent_call("reviewer"))

        assert code == 0  # hook itself never crashes
        captured = capsys.readouterr()
        assert '"permissionDecision": "deny"' in captured.out, (
            "tampered count=0 was trusted instead of being forced to cap"
        )
        assert "integrity check failed" in captured.err

    def test_bare_int_reset_to_zero_does_not_bypass_the_cap(self, monkeypatch, tmp_path, capsys):
        """The exact attack this fix exists to close: an early draft of this
        fix trusted a "legacy bare-int" format for backward compat, which
        turned out to be byte-for-byte indistinguishable from
        `Write(".claude/state/eo_loop.json", '{"sess1": 0}')` -- caught by
        adversarial review before merge. A bare int (0, or any value) must
        now fail CLOSED just like any other unsigned entry, whether it
        looks like a "low, safe" count or not."""
        monkeypatch.chdir(tmp_path)
        state = HookState("eo_loop")
        state["sess1"] = 0  # bare int reset attempt -- must NOT be trusted as allow
        state.save()

        code = self._run(monkeypatch, tmp_path, _agent_call("reviewer"))

        assert code == 0  # never crashes
        assert '"permissionDecision": "deny"' in capsys.readouterr().out  # not bypassed

    def test_subagent_stop_writes_a_verifiable_signature(self, monkeypatch, tmp_path):
        """End-to-end: after a real NEEDS_WORK verdict via SubagentStop, the
        persisted entry must carry a signature that _get_session_count()
        accepts as authentic (round-trips through the real write path, not
        just a hand-constructed test fixture)."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        monkeypatch.setattr(
            "sys.stdin",
            _stdin(
                {
                    "session_id": "sess1",
                    "last_assistant_message": "VERDICT: NEEDS_WORK — needs more tests",
                }
            ),
        )

        import iteration_guard

        with pytest.raises(SystemExit):
            iteration_guard.main()

        state = HookState("eo_loop")
        entry = state["sess1"]
        assert entry["count"] == 1
        assert entry["sig"] == iteration_guard._sign("sess1", 1)
