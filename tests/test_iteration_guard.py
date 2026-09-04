"""Tests for iteration_guard.py — enforce Evaluator-Optimizer cap=3."""

import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from hook_state import HookState, commit_test_gate_state
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
    signature stored alongside the count, checked on read.

    CORRECTED 2026-08-29 (independent security-audit review): this is a
    checksum against accidental/casual corruption, NOT a security boundary
    against the agent whose behavior it constrains. `_SIG_SALT` is a literal
    string in iteration_guard.py's source, and this repo's own settings.json
    grants Read(*)/Bash(*) globally -- an agent can read the salt, compute a
    valid signature for any count, and write an indistinguishable forgery.
    Deletion of the session's key is an even simpler bypass (no salt
    knowledge needed at all): `_get_session_count` treats a missing entry as
    a legitimate fresh session at count 0. See iteration_guard.py's own
    `_SIG_SALT` comment for the full correction and why no cheap in-scope
    fix (chmod, a monotonic external counter) closes this: any signal
    derivable through the same Read/Bash surface the cap constrains isn't
    an independent boundary."""

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


class TestLgtmStaleTestWarning:
    """Regression for bottleneck #1 (/boyko-project-radar autonomy-subsystem
    scan, 2026-08-29): iteration_guard.py and commit_test_gate.py were
    independent silos -- an LGTM on code edited after the last test run reset
    the cycle counter with zero signal. This cross-checks commit_test_gate's
    own state file (read-only) and surfaces the staleness via
    additionalContext, without overriding the reviewer's LGTM."""

    def _run(self, monkeypatch, tmp_path, message: str):
        # WHY (tmp_path / ".git").mkdir(): commit_test_gate_state() (used by
        # both this test's setup AND iteration_guard's own
        # _lgtm_follows_stale_tests()) anchors to git_root(cwd()), which walks
        # UPWARD looking for a .git. On this exact machine C:/Users/<user> (an
        # ancestor of every pytest tmp_path) is itself a git repo, so without
        # a .git marker right here, state would silently escape tmp_path and
        # land in the REAL live ~/.claude/state/commit_test_gate.json instead
        # of this test's isolated directory (same class of issue already
        # fixed in test_commit_test_gate.py's _run_main helper).
        (tmp_path / ".git").mkdir(exist_ok=True)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys.stdin", _stdin(_subagent_stop(message)))
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)

        import iteration_guard

        with pytest.raises(SystemExit):
            iteration_guard.main()

    def test_warns_when_lgtm_follows_stale_tests(self, monkeypatch, tmp_path, capsys):
        # WHY chdir + .git FIRST: commit_test_gate_state() resolves its path
        # at construction time from the CURRENT cwd's git root (same reason
        # TestPreToolUseBlocking._set_count above chdirs first for HookState).
        (tmp_path / ".git").mkdir(exist_ok=True)
        monkeypatch.chdir(tmp_path)
        cts_state = commit_test_gate_state()
        cts_state["last_edit"] = 200.0
        cts_state["last_test"] = 100.0  # edited AFTER the last test run
        cts_state.save()

        self._run(monkeypatch, tmp_path, "VERDICT: LGTM")

        out = capsys.readouterr().out
        assert "LGTM verdict follows source changes" in out
        assert "additionalContext" in out

    def test_no_warning_when_tests_are_current(self, monkeypatch, tmp_path, capsys):
        (tmp_path / ".git").mkdir(exist_ok=True)
        monkeypatch.chdir(tmp_path)
        cts_state = commit_test_gate_state()
        cts_state["last_edit"] = 100.0
        cts_state["last_test"] = 200.0  # tested AFTER the last edit — current
        cts_state.save()

        self._run(monkeypatch, tmp_path, "VERDICT: LGTM")

        assert capsys.readouterr().out == ""

    def test_no_warning_when_sibling_state_missing(self, monkeypatch, tmp_path, capsys):
        """No commit_test_gate.json at all (e.g. no commit attempted yet in
        this session) must fail safe -- silent, not a false-positive warning."""
        self._run(monkeypatch, tmp_path, "VERDICT: LGTM")

        assert capsys.readouterr().out == ""

    def test_no_warning_on_corrupted_sibling_state(self, monkeypatch, tmp_path, capsys):
        """A non-numeric last_edit/last_test (corrupted state, hand-edited
        file, or a future schema change) must fail safe -- silent, not a
        crash and not a false-positive warning."""
        (tmp_path / ".git").mkdir(exist_ok=True)
        monkeypatch.chdir(tmp_path)
        cts_state = commit_test_gate_state()
        cts_state["last_edit"] = "not-a-number"
        cts_state["last_test"] = 100.0
        cts_state.save()

        self._run(monkeypatch, tmp_path, "VERDICT: LGTM")

        assert capsys.readouterr().out == ""

    def test_no_warning_for_non_lgtm_verdicts(self, monkeypatch, tmp_path, capsys):
        """The staleness check only applies to LGTM (which silently resets
        the counter) -- NEEDS_WORK/BLOCK already produce their own signal via
        the counter increment, so this check must not fire redundantly."""
        (tmp_path / ".git").mkdir(exist_ok=True)
        monkeypatch.chdir(tmp_path)
        cts_state = commit_test_gate_state()
        cts_state["last_edit"] = 200.0
        cts_state["last_test"] = 100.0
        cts_state.save()

        self._run(monkeypatch, tmp_path, "VERDICT: NEEDS_WORK — see comments")

        out = capsys.readouterr().out
        assert "LGTM verdict follows source changes" not in out

    def test_state_written_at_root_is_seen_from_a_subdirectory_reader(
        self, monkeypatch, tmp_path, capsys
    ):
        """Real cross-hook regression (Codex review, PR #364): commit_test_gate.py
        writes its state anchored to the git ROOT regardless of its own cwd (so
        its own 4 event types agree with each other despite shell cwd drift).
        iteration_guard.py's SubagentStop check previously read via a bare
        HookState("commit_test_gate") anchored to Path.cwd() instead -- so a
        session whose fixed cwd happens to be a SUBDIRECTORY of the repo root
        would look for state at `<subdir>/.claude/state/...`, never finding
        what commit_test_gate.py actually wrote at the root, silently disabling
        the stale-test warning. Both must now agree via the shared
        commit_test_gate_state() accessor, independent of either hook's cwd."""
        (tmp_path / ".git").mkdir(exist_ok=True)

        # commit_test_gate.py writes from the repo root -- always anchors to
        # git_root(cwd()), which for the root itself is just the root.
        monkeypatch.chdir(tmp_path)
        import commit_test_gate

        writer_state = commit_test_gate.commit_test_gate_state()
        writer_state["last_edit"] = 200.0
        writer_state["last_test"] = 100.0  # edited AFTER the last test run
        writer_state.save()

        # iteration_guard's SubagentStop fires from a SUBDIRECTORY (with no
        # .git of its own -- it must find the root's via upward walk) -- a
        # bare Path.cwd()-scoped HookState would look in the wrong place here.
        # NOT reusing self._run(): that helper deliberately creates its OWN
        # .git in whatever directory it's given, which would make the
        # subdirectory its own (wrong) git root instead of testing the
        # upward-walk case this test exists to cover.
        subdir = tmp_path / "some" / "nested" / "dir"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)
        monkeypatch.setattr("sys.stdin", _stdin(_subagent_stop("VERDICT: LGTM")))
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)

        import iteration_guard

        with pytest.raises(SystemExit):
            iteration_guard.main()

        out = capsys.readouterr().out
        assert "LGTM verdict follows source changes" in out
