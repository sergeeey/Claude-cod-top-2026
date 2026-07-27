"""Tests for locality_escalation_guard.py — nudge on repeated local edits."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from locality_escalation_guard import (
    _TRACKED_TOOLS,
    THRESHOLD,
    _nudge_message,
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
