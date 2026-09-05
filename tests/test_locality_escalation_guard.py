"""Tests for locality_escalation_guard.py — nudge on repeated local edits."""

import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from locality_escalation_guard import (
    _TRACKED_TOOLS,
    THRESHOLD,
    _nudge_message,
    main,
    process_edit,
)


class TestProcessEditCounting:
    def test_first_edit_counts_one_no_nudge(self):
        state, nudge = process_edit({}, "a.py", THRESHOLD)
        assert state["counts"]["a.py"] == 1
        assert nudge is False

    def test_increments_existing_count(self):
        state = {"counts": {"a.py": 2}, "nudged": []}
        new_state, _ = process_edit(state, "a.py", THRESHOLD)
        assert new_state["counts"]["a.py"] == 3

    def test_does_not_mutate_input_state(self):
        # WHY: pure function contract — caller's dict must be untouched so a
        # save failure can't leave half-mutated in-memory state.
        original = {"counts": {"a.py": 1}, "nudged": []}
        process_edit(original, "a.py", THRESHOLD)
        assert original["counts"]["a.py"] == 1


class TestThresholdNudge:
    def test_nudge_fires_exactly_at_threshold(self):
        state: dict = {}
        results = []
        for _ in range(THRESHOLD):
            state, nudge = process_edit(state, "a.py", THRESHOLD)
            results.append(nudge)
        # only the edit that first reaches THRESHOLD nudges
        assert results == [False] * (THRESHOLD - 1) + [True]

    def test_nudge_fires_only_once_per_file(self):
        state: dict = {}
        fired = 0
        for _ in range(THRESHOLD + 3):
            state, nudge = process_edit(state, "a.py", THRESHOLD)
            fired += int(nudge)
        assert fired == 1

    def test_path_recorded_in_nudged_after_firing(self):
        state: dict = {}
        for _ in range(THRESHOLD):
            state, _ = process_edit(state, "a.py", THRESHOLD)
        assert "a.py" in state["nudged"]


class TestMultiFileIsolation:
    def test_separate_files_counted_independently(self):
        state: dict = {}
        state, _ = process_edit(state, "a.py", THRESHOLD)
        state, nudge_b = process_edit(state, "b.py", THRESHOLD)
        assert state["counts"] == {"a.py": 1, "b.py": 1}
        assert nudge_b is False

    def test_one_file_at_threshold_does_not_nudge_another(self):
        state: dict = {}
        for _ in range(THRESHOLD):
            state, _ = process_edit(state, "a.py", THRESHOLD)
        state, nudge_b = process_edit(state, "b.py", THRESHOLD)
        assert nudge_b is False
        assert "b.py" not in state["nudged"]


class TestCorruptionResilience:
    # WHY: state files in this repo do get corrupted/hand-edited (a legacy
    # bare-int eo_loop.json fail-closed iteration_guard). A malformed prior
    # value must fail OPEN (treated as fresh), never crash the hook.
    def test_counts_not_a_dict_is_treated_as_fresh(self):
        state, nudge = process_edit({"counts": "garbage"}, "x", THRESHOLD)
        assert state["counts"]["x"] == 1
        assert nudge is False

    def test_nudged_not_a_list_is_treated_as_empty(self):
        state, _ = process_edit({"nudged": 42}, "x", THRESHOLD)
        assert state["nudged"] == []
        assert state["counts"]["x"] == 1

    def test_per_file_count_not_an_int_resets_to_one(self):
        state, _ = process_edit({"counts": {"x": "5"}}, "x", THRESHOLD)
        assert state["counts"]["x"] == 1

    def test_bool_count_resets_not_coerced_to_int(self):
        # WHY: bool is a subclass of int in Python — a JSON `true` must reset to
        # 1, not silently become 2 (True + 1). Reviewer P2, 2026-07-19.
        assert process_edit({"counts": {"x": True}}, "x", THRESHOLD)[0]["counts"]["x"] == 1
        assert process_edit({"counts": {"x": False}}, "x", THRESHOLD)[0]["counts"]["x"] == 1


class TestConstantsAndMessage:
    def test_threshold_is_conservative(self):
        # WHY: guard against a future edit lowering this to a nagging value.
        assert THRESHOLD >= 4

    def test_tracked_tools_are_edit_and_write(self):
        assert _TRACKED_TOOLS == frozenset({"Edit", "Write"})

    def test_message_points_at_macro_locality_and_marks_weak(self):
        msg = _nudge_message("hooks/x.py", THRESHOLD)
        assert "macro-locality" in msg
        assert "[WEAK]" in msg
        assert "hooks/x.py" in msg


# ── main() ─────────────────────────────────────────────────────────────────────
#
# WHY every early-return path is wrapped in pytest.raises(SystemExit): main()
# calls sys.exit(0) explicitly on every branch except the one that reaches
# emit_hook_result() after a nudge -- confirmed by running the naive
# (non-wrapped) version first and letting pytest's own traceback point at each
# exact sys.exit() call site, not assumed from reading the source alone.


def _stdin(monkeypatch, payload: dict | None):
    text = "" if payload is None else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))


class TestMain:
    def test_recursion_guard_skips_when_invoked_by_subagent(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CLAUDE_INVOKED_BY", "some-agent")
        (tmp_path / ".git").mkdir(exist_ok=True)
        monkeypatch.chdir(tmp_path)
        _stdin(monkeypatch, {"tool_name": "Edit", "tool_input": {"file_path": "a.py"}})

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        assert not (tmp_path / ".claude" / "state").exists()

    def test_empty_stdin_exits_quietly(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        (tmp_path / ".git").mkdir(exist_ok=True)
        monkeypatch.chdir(tmp_path)
        _stdin(monkeypatch, None)

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_untracked_tool_is_ignored(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        (tmp_path / ".git").mkdir(exist_ok=True)
        monkeypatch.chdir(tmp_path)
        _stdin(monkeypatch, {"tool_name": "Read", "tool_input": {"file_path": "a.py"}})

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        assert not (tmp_path / ".claude" / "state").exists()

    def test_missing_file_path_is_ignored(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        (tmp_path / ".git").mkdir(exist_ok=True)
        monkeypatch.chdir(tmp_path)
        _stdin(monkeypatch, {"tool_name": "Edit", "tool_input": {}})

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        assert not (tmp_path / ".claude" / "state").exists()

    def test_single_edit_below_threshold_persists_state_no_output(
        self, monkeypatch, tmp_path, capsys
    ):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        (tmp_path / ".git").mkdir(exist_ok=True)
        monkeypatch.chdir(tmp_path)
        _stdin(
            monkeypatch,
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": "a.py"},
                "session_id": "sess1",
            },
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        state_file = tmp_path / ".claude" / "state" / "locality_escalation_guard.json"
        assert state_file.exists()
        saved = json.loads(state_file.read_text(encoding="utf-8"))
        assert saved["sess1"]["counts"]["a.py"] == 1
        assert capsys.readouterr().out == ""

    def test_reaching_threshold_emits_nudge_and_persists(self, monkeypatch, tmp_path, capsys):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        (tmp_path / ".git").mkdir(exist_ok=True)
        monkeypatch.chdir(tmp_path)

        for i in range(THRESHOLD):
            _stdin(
                monkeypatch,
                {
                    "tool_name": "Edit",
                    "tool_input": {"file_path": "a.py"},
                    "session_id": "sess1",
                },
            )
            if i < THRESHOLD - 1:
                with pytest.raises(SystemExit) as exc:
                    main()
                assert exc.value.code == 0
            else:
                main()  # the threshold-reaching call falls through, no sys.exit

        out = capsys.readouterr().out
        assert "locality-escalation" in out
        payload = json.loads(out)
        assert payload["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert "a.py" in payload["hookSpecificOutput"]["additionalContext"]

    def test_nudge_fires_only_once_across_repeated_main_calls(self, monkeypatch, tmp_path, capsys):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        (tmp_path / ".git").mkdir(exist_ok=True)
        monkeypatch.chdir(tmp_path)

        outputs = []
        for i in range(THRESHOLD + 2):
            _stdin(
                monkeypatch,
                {
                    "tool_name": "Write",
                    "tool_input": {"file_path": "b.py"},
                    "session_id": "sess1",
                },
            )
            if i == THRESHOLD - 1:
                main()  # exactly the nudge call -- no sys.exit
            else:
                with pytest.raises(SystemExit):
                    main()
            outputs.append(capsys.readouterr().out)

        nudges = [o for o in outputs if o]
        assert len(nudges) == 1

    def test_default_session_id_used_when_absent(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        (tmp_path / ".git").mkdir(exist_ok=True)
        monkeypatch.chdir(tmp_path)
        _stdin(monkeypatch, {"tool_name": "Edit", "tool_input": {"file_path": "a.py"}})

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        state_file = tmp_path / ".claude" / "state" / "locality_escalation_guard.json"
        saved = json.loads(state_file.read_text(encoding="utf-8"))
        assert "default" in saved

    def test_non_dict_tool_input_is_ignored(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        (tmp_path / ".git").mkdir(exist_ok=True)
        monkeypatch.chdir(tmp_path)
        _stdin(monkeypatch, {"tool_name": "Edit", "tool_input": "not-a-dict"})

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        assert not (tmp_path / ".claude" / "state").exists()

    def test_malformed_prior_session_state_does_not_crash(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        (tmp_path / ".git").mkdir(exist_ok=True)
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "locality_escalation_guard.json").write_text(
            json.dumps({"sess1": "not-a-dict"}), encoding="utf-8"
        )
        _stdin(
            monkeypatch,
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": "a.py"},
                "session_id": "sess1",
            },
        )

        with pytest.raises(SystemExit) as exc:
            main()  # must fail open (treat as fresh state), not raise a real exception

        assert exc.value.code == 0
        saved = json.loads(
            (state_dir / "locality_escalation_guard.json").read_text(encoding="utf-8")
        )
        assert saved["sess1"]["counts"]["a.py"] == 1


class TestGitRootAnchoring:
    # WHY: reproduces the actual bug (2026-09-05, found live) -- a Bash-triggered
    # event sees the drifting shell cwd, which can be a subdirectory several
    # levels below the repo root. Before the fix, state landed nested under
    # that subdirectory instead of at the repo root.
    def test_state_anchored_to_repo_root_not_subdirectory_cwd(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        repo_root = tmp_path
        (repo_root / ".git").mkdir()
        subdir = repo_root / "scripts" / "collectors"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)

        _stdin(
            monkeypatch,
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": "a.py"},
                "session_id": "sess1",
            },
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        root_state = repo_root / ".claude" / "state" / "locality_escalation_guard.json"
        nested_state = subdir / ".claude" / "state" / "locality_escalation_guard.json"
        assert root_state.exists(), "state must be written at the repo root"
        assert not nested_state.exists(), "state must NOT be nested under the subdirectory cwd"
