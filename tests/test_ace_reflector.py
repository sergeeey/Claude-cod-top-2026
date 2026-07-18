"""Tests for ace_reflector.py — outcome detection via commit_test_gate state.

WHY these tests exist now (2026-07-09): the hook previously had zero test
coverage. The rewrite replaces keyword-matching on the agent's own message
with an externally-verified signal (commit_test_gate.py's HookState), so
these tests focus on that boundary: PreToolUse(Agent) stamping, and
SubagentStop reading commit_test_gate's already-verified timestamps.
"""

import io
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

import ace_reflector
from ace_reflector import (
    _classify_approach,
    _determine_outcome,
    _load_playbook,
    _save_playbook,
    main,
)
from hook_state import HookState


def _stdin(data: dict) -> io.StringIO:
    return io.StringIO(json.dumps(data))


def _agent_call(session_id: str = "sess1") -> dict:
    return {
        "tool_name": "Agent",
        "tool_input": {"subagent_type": "builder"},
        "session_id": session_id,
    }


def _subagent_stop(message: str, session_id: str = "sess1") -> dict:
    return {"last_assistant_message": message, "session_id": session_id}


class TestClassifyApproach:
    def test_test_driven_takes_priority(self):
        assert _classify_approach("Ran pytest and grep to find the bug") == "test-driven"

    def test_search_first(self):
        assert _classify_approach("Used grep to locate the function") == "search-first"

    def test_direct_implementation(self):
        assert _classify_approach("Edited the file to add the feature") == "direct-implementation"

    def test_general_fallback(self):
        assert _classify_approach("Something unrelated happened") == "general"


class TestDetermineOutcome:
    def test_no_turn_start_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert _determine_outcome("sess1") is None

    def test_verified_test_pass_after_turn_start_is_helpful(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        turn_state = HookState("ace_reflector_turns")
        turn_state["sess1"] = time.time()
        turn_state.save()

        ct_state = HookState("commit_test_gate")
        ct_state["last_test"] = time.time() + 10  # verified pass AFTER turn started
        ct_state.save()

        assert _determine_outcome("sess1") == "helpful"

    def test_unverified_edit_after_turn_start_is_harmful(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        turn_state = HookState("ace_reflector_turns")
        turn_state["sess1"] = time.time()
        turn_state.save()

        ct_state = HookState("commit_test_gate")
        ct_state["last_edit"] = time.time() + 10  # edit after turn, no test pass
        ct_state.save()

        assert _determine_outcome("sess1") == "harmful"

    def test_test_pass_wins_over_stale_edit(self, tmp_path, monkeypatch):
        """A verified test pass after the edit means the edit WAS validated."""
        monkeypatch.chdir(tmp_path)
        turn_state = HookState("ace_reflector_turns")
        turn_state["sess1"] = time.time()
        turn_state.save()

        ct_state = HookState("commit_test_gate")
        ct_state["last_edit"] = time.time() + 5
        ct_state["last_test"] = time.time() + 10
        ct_state.save()

        assert _determine_outcome("sess1") == "helpful"

    def test_no_activity_this_turn_returns_none(self, tmp_path, monkeypatch):
        """Read-only/research turn — no source edit, no test run. Stay silent,
        don't fabricate a verdict from message text."""
        monkeypatch.chdir(tmp_path)
        turn_state = HookState("ace_reflector_turns")
        turn_state["sess1"] = time.time() + 100  # turn started AFTER any stale state
        turn_state.save()

        ct_state = HookState("commit_test_gate")
        ct_state["last_test"] = time.time()  # stale — before this turn started
        ct_state["last_edit"] = time.time()
        ct_state.save()

        assert _determine_outcome("sess1") is None

    def test_sessions_are_isolated(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        turn_state = HookState("ace_reflector_turns")
        turn_state["sess1"] = time.time()
        turn_state.save()
        # sess2 never stamped
        assert _determine_outcome("sess2") is None

    def test_known_limitation_cross_session_test_pass_is_misattributed(self, tmp_path, monkeypatch):
        """Documents a known, accepted limitation (reviewer finding, 2026-07-09):
        commit_test_gate.json's last_test/last_edit are GLOBAL per-cwd, not
        session-scoped. A test pass from an unrelated session B can get
        credited to session A's turn if both share a cwd. This test exists so
        a future change to this behavior is a deliberate decision, not an
        accidental regression discovered the hard way."""
        monkeypatch.chdir(tmp_path)
        turn_state = HookState("ace_reflector_turns")
        turn_state["session_a"] = time.time()
        turn_state["session_b"] = time.time()
        turn_state.save()

        # Only session B's agent actually ran pytest -- but commit_test_gate
        # has no session dimension, so this is indistinguishable from A's.
        ct_state = HookState("commit_test_gate")
        ct_state["last_test"] = time.time() + 10
        ct_state.save()

        assert _determine_outcome("session_a") == "helpful"  # misattributed, by design gap
        assert _determine_outcome("session_b") == "helpful"  # correctly attributed


class TestPlaybookIO:
    def test_save_then_load_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ace_reflector, "PLAYBOOK_PATH", tmp_path / "playbook.md")
        entries = {"test-driven": {"helpful": 3, "harmful": 1, "example": "did a thing"}}
        _save_playbook(entries)
        loaded = _load_playbook()
        assert loaded["test-driven"]["helpful"] == 3
        assert loaded["test-driven"]["harmful"] == 1

    def test_load_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ace_reflector, "PLAYBOOK_PATH", tmp_path / "does_not_exist.md")
        assert _load_playbook() == {}

    def test_sorted_by_net_score_descending(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ace_reflector, "PLAYBOOK_PATH", tmp_path / "playbook.md")
        entries = {
            "low": {"helpful": 1, "harmful": 5, "example": ""},
            "high": {"helpful": 10, "harmful": 0, "example": ""},
        }
        _save_playbook(entries)
        text = (tmp_path / "playbook.md").read_text(encoding="utf-8")
        assert text.index("### high") < text.index("### low")


class TestPlaybookConcurrency:
    """Regression (F-09, security audit 2026-07-12): main()'s load-mutate-save
    on PLAYBOOK_PATH (a GLOBAL, machine-wide path) was unlocked -- concurrent
    Claude Code sessions could race and silently lose one side's counter
    increment. Exercises the same file_lock()-wrapped load/mutate/save
    sequence main() uses, directly (not through main()'s stdin/sys.exit
    plumbing, which isn't thread-safe to patch concurrently)."""

    def test_six_concurrent_increments_all_persisted(self, tmp_path, monkeypatch):
        import threading

        from utils import file_lock

        monkeypatch.setattr(ace_reflector, "PLAYBOOK_PATH", tmp_path / "playbook.md")

        def increment_one(i: int) -> None:
            approach = f"approach-{i}"
            with file_lock(ace_reflector.PLAYBOOK_PATH.with_suffix(".lock"), timeout=15.0) as ok:
                assert ok
                entries = _load_playbook()
                entries.setdefault(approach, {"helpful": 0, "harmful": 0, "example": ""})
                entries[approach]["helpful"] += 1
                _save_playbook(entries)

        threads = [threading.Thread(target=increment_one, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final = _load_playbook()
        for i in range(6):
            assert final.get(f"approach-{i}", {}).get("helpful") == 1, (
                f"approach-{i}'s increment was lost to a lost-update race"
            )


class TestMainEndToEnd:
    def _run(self, monkeypatch, tmp_path, data: dict) -> int:
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        monkeypatch.setattr("sys.stdin", _stdin(data))
        monkeypatch.setattr(ace_reflector, "PLAYBOOK_PATH", tmp_path / "playbook.md")
        with pytest.raises(SystemExit) as exc_info:
            main()
        return exc_info.value.code or 0

    def test_pre_tool_use_agent_stamps_turn_and_does_not_touch_playbook(
        self, monkeypatch, tmp_path
    ):
        self._run(monkeypatch, tmp_path, _agent_call("sess1"))
        turn_state = HookState("ace_reflector_turns")
        assert "sess1" in turn_state._data
        assert not (tmp_path / "playbook.md").exists()

    def test_pre_tool_use_non_agent_tool_is_ignored(self, monkeypatch, tmp_path):
        data = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "session_id": "sess1"}
        self._run(monkeypatch, tmp_path, data)
        turn_state = HookState("ace_reflector_turns")
        assert "sess1" not in turn_state._data

    def test_subagent_stop_with_verified_pass_records_helpful(self, monkeypatch, tmp_path, capsys):
        # Simulate PreToolUse(Agent) already having stamped this turn.
        monkeypatch.chdir(tmp_path)
        turn_state = HookState("ace_reflector_turns")
        turn_state["sess1"] = time.time()
        turn_state.save()
        ct_state = HookState("commit_test_gate")
        ct_state["last_test"] = time.time() + 10
        ct_state.save()

        self._run(
            monkeypatch,
            tmp_path,
            _subagent_stop("Ran pytest, all green. Completed the fix.", "sess1"),
        )
        loaded = _load_playbook()
        assert loaded["test-driven"]["helpful"] == 1
        assert "helpful+1" in capsys.readouterr().err

    def test_subagent_stop_without_verification_signal_records_nothing(self, monkeypatch, tmp_path):
        """No commit_test_gate activity this turn -- e.g. a confident-sounding
        but never-verified claim must NOT be recorded, unlike the old
        keyword-matching behavior."""
        monkeypatch.chdir(tmp_path)
        turn_state = HookState("ace_reflector_turns")
        turn_state["sess1"] = time.time()
        turn_state.save()
        # commit_test_gate has no state at all this turn.

        self._run(
            monkeypatch,
            tmp_path,
            _subagent_stop("Completed the fix! Everything works perfectly.", "sess1"),
        )
        assert not (tmp_path / "playbook.md").exists()

    def test_subagent_stop_honest_failure_report_not_penalized_without_bad_edit(
        self, monkeypatch, tmp_path
    ):
        """An agent that honestly reports an error, with no source edit and no
        test run this turn, should NOT be scored harmful just for the word
        'error' appearing in its message -- that was the old bug."""
        monkeypatch.chdir(tmp_path)
        turn_state = HookState("ace_reflector_turns")
        turn_state["sess1"] = time.time()
        turn_state.save()

        self._run(
            monkeypatch,
            tmp_path,
            _subagent_stop("error: file not found, could not proceed", "sess1"),
        )
        assert not (tmp_path / "playbook.md").exists()

    def test_subagent_stop_unverified_edit_is_deferred_not_immediate_harmful(
        self, monkeypatch, tmp_path, capsys
    ):
        """UPDATED (2026-07-17 fix): an edit-only turn with no verified test
        pass YET no longer records "harmful" immediately -- see module
        docstring's "FIXED" section. It's deferred to the pending queue
        instead, so a clean builder-only turn (this repo's own build-squad
        pattern) isn't punished just for finishing before tester runs."""
        monkeypatch.chdir(tmp_path)
        turn_state = HookState("ace_reflector_turns")
        turn_state["sess1"] = time.time()
        turn_state.save()
        ct_state = HookState("commit_test_gate")
        ct_state["last_edit"] = time.time() + 10
        ct_state.save()

        self._run(
            monkeypatch,
            tmp_path,
            _subagent_stop("Created the new file and added the feature.", "sess1"),
        )
        loaded = _load_playbook()
        assert (
            "direct-implementation" not in loaded or loaded["direct-implementation"]["harmful"] == 0
        )
        pending = HookState("ace_reflector_pending").get("entries", [])
        assert len(pending) == 1
        assert pending[0]["approach"] == "direct-implementation"
        assert "deferred" in capsys.readouterr().err

    def test_deferred_entry_resolves_helpful_when_a_later_turn_verifies(
        self, monkeypatch, tmp_path
    ):
        """The build-squad pattern this fix targets: builder edits (turn 1,
        deferred), tester verifies separately (turn 2) -- builder's deferred
        entry must resolve to helpful once tester's SubagentStop sees a
        verified pass, even though it happened in a DIFFERENT turn/session."""
        monkeypatch.chdir(tmp_path)

        # Turn 1 (builder): edit, no test yet -- defers.
        turn_state = HookState("ace_reflector_turns")
        turn_state["builder-turn"] = time.time()
        turn_state.save()
        ct_state = HookState("commit_test_gate")
        ct_state["last_edit"] = time.time() + 1
        ct_state.save()
        self._run(
            monkeypatch,
            tmp_path,
            _subagent_stop("Created the new file and added the feature.", "builder-turn"),
        )
        assert len(HookState("ace_reflector_pending").get("entries", [])) == 1

        # Turn 2 (tester): different session, runs a verified test AFTER
        # builder's turn started.
        turn_state = HookState("ace_reflector_turns")
        turn_state["tester-turn"] = time.time()
        turn_state.save()
        ct_state = HookState("commit_test_gate")
        ct_state["last_test"] = time.time() + 10
        ct_state.save()
        self._run(
            monkeypatch,
            tmp_path,
            _subagent_stop("Ran pytest, all green, everything passes now.", "tester-turn"),
        )

        loaded = _load_playbook()
        assert loaded["direct-implementation"]["helpful"] == 1
        assert loaded["direct-implementation"]["harmful"] == 0
        assert HookState("ace_reflector_pending").get("entries", []) == []

    def test_deferred_entry_expires_to_harmful_after_window(self, monkeypatch, tmp_path):
        """An edit that NEVER gets verified (no tester turn, ever) must still
        eventually resolve to harmful -- deferred is not the same as
        forgiven forever."""
        monkeypatch.chdir(tmp_path)
        turn_state = HookState("ace_reflector_turns")
        turn_state["sess1"] = time.time()
        turn_state.save()
        ct_state = HookState("commit_test_gate")
        ct_state["last_edit"] = time.time() + 1
        ct_state.save()
        self._run(
            monkeypatch,
            tmp_path,
            _subagent_stop("Created the new file and added the feature.", "sess1"),
        )

        # Manually age the pending entry past the expiry window instead of
        # sleeping in the test.
        pending_state = HookState("ace_reflector_pending")
        entries = pending_state.get("entries", [])
        entries[0]["stamped_at"] = time.time() - ace_reflector.PENDING_EXPIRY_SECONDS - 1
        pending_state["entries"] = entries
        pending_state.save()

        # A later, unrelated turn triggers the sweep that expires it. WHY no
        # turn_start stamp for sess2: any real timestamp risks a flaky race
        # against the stale last_edit set above (both are real wall-clock
        # values a fast test run could land on either side of). An
        # unstamped session deterministically returns outcome=None from
        # _determine_outcome, which is exactly what's being tested here --
        # a turn with zero verifiable signal of its OWN still must sweep
        # pending for everyone else.
        self._run(monkeypatch, tmp_path, _subagent_stop("ok, nothing to do here", "sess2"))

        loaded = _load_playbook()
        assert loaded["direct-implementation"]["harmful"] == 1
        assert loaded["direct-implementation"]["helpful"] == 0
        assert HookState("ace_reflector_pending").get("entries", []) == []

    def test_short_message_with_verified_pass_still_records_helpful(self, monkeypatch, tmp_path):
        """Regression test (cross-model review, 2026-07-09): outcome detection
        must not be defeated by message length. A terse "Done." after a REAL
        verified test pass must still count as helpful -- only the approach
        classification falls back to "general" for text too short to classify."""
        monkeypatch.chdir(tmp_path)
        turn_state = HookState("ace_reflector_turns")
        turn_state["sess1"] = time.time()
        turn_state.save()
        ct_state = HookState("commit_test_gate")
        ct_state["last_test"] = time.time() + 10
        ct_state.save()

        self._run(monkeypatch, tmp_path, _subagent_stop("Done.", "sess1"))
        loaded = _load_playbook()
        assert loaded["general"]["helpful"] == 1

    def test_short_message_with_no_verification_signal_records_nothing(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        turn_state = HookState("ace_reflector_turns")
        turn_state["sess1"] = time.time()
        turn_state.save()
        # no commit_test_gate activity this turn at all

        self._run(monkeypatch, tmp_path, _subagent_stop("ok", "sess1"))
        assert not (tmp_path / "playbook.md").exists()
