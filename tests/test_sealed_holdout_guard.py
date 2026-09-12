"""Tests for hooks/sealed_holdout_guard.py.

Mirrors tests/test_weakened_test_guard.py's own shape (a PreToolUse hard block
comparing OLD vs NEW content), applied to the sealed-holdout invariant instead
of test assertions.
"""

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from sealed_holdout_guard import (
    _extract_flat_fields,
    _is_sealed_holdout_file,
    _is_true,
    _strip_inline_comment,
    _structural_consumption_signals,
    _weakening_signals,
    main,
)

_CONSUMED = (
    "holdout_ref: sha256:abcd\nsealed_at: 2026-09-12\nopened_at: 2026-09-13\n"
    "opened_by_stage: VERIFY\nconsumed: true\n"
)
_UNSEALED = "holdout_ref: sha256:abcd\nsealed_at: 2026-09-12\nopened_at: null\nconsumed: false\n"


def _stdin(data: dict) -> io.StringIO:
    return io.StringIO(json.dumps(data))


class TestIsSealedHoldoutFile:
    def test_valid_path(self):
        assert _is_sealed_holdout_file("experiments/20260101-test/sealed_holdout.yaml")

    def test_wrong_filename(self):
        assert not _is_sealed_holdout_file("experiments/20260101-test/graph.yaml")

    def test_no_experiments_parent(self):
        assert not _is_sealed_holdout_file("docs/sealed_holdout.yaml")


class TestStripInlineComment:
    """Regression (skeptic-found, 2026-09-12, verified via constructed
    input): without this, a trailing YAML comment on a value line silently
    defeats both _is_true and promotion_gate_guard.py's _to_float, since
    the whole line-remainder (comment included) was extracted as the value."""

    def test_strips_trailing_comment(self):
        assert _strip_inline_comment("true    # opened at VERIFY yesterday") == "true"

    def test_no_comment_unchanged(self):
        assert _strip_inline_comment("sha256:abcd") == "sha256:abcd"

    def test_hash_glued_to_value_not_stripped(self):
        # WHY: only a '#' preceded by whitespace (or at start) is a comment,
        # matching YAML's own rule -- a glued '#' is part of the scalar.
        assert _strip_inline_comment("abc#def") == "abc#def"


class TestExtractFlatFields:
    def test_extracts_flat_values(self):
        fields = _extract_flat_fields(_CONSUMED)
        assert fields["holdout_ref"] == "sha256:abcd"
        assert fields["consumed"] == "true"
        assert fields["opened_at"] == "2026-09-13"

    def test_null_becomes_none(self):
        fields = _extract_flat_fields(_UNSEALED)
        assert fields["opened_at"] is None

    def test_inline_comment_stripped_from_extracted_value(self):
        content = "consumed: true    # opened at VERIFY yesterday\n"
        fields = _extract_flat_fields(content)
        assert fields["consumed"] == "true"


class TestIsTrue:
    def test_true_variants(self):
        assert _is_true("true")
        assert _is_true("True")
        assert _is_true("TRUE")

    def test_yaml_11_boolean_synonyms(self):
        """Regression (skeptic-found, 2026-09-12): yaml.safe_load (used by
        scripts/check_experiment_graph.py) resolves YAML 1.1 'yes'/'on' to
        True too -- without matching that here, consumed: yes would be
        treated as consumed by the offline CI check but NOT by this hook's
        own re-seal guard, a real disagreement between the two validators."""
        assert _is_true("yes")
        assert _is_true("Yes")
        assert _is_true("on")

    def test_false_and_none(self):
        assert not _is_true("false")
        assert not _is_true(None)
        assert not _is_true("")
        assert not _is_true("no")


class TestWeakeningSignals:
    def test_reseal_attempt_flagged(self):
        new_reseal = _CONSUMED.replace("2026-09-13", "2026-09-20")
        signals = _weakening_signals(_CONSUMED, new_reseal)
        assert any("re-seal attempt" in s for s in signals)

    def test_reseal_via_sealed_at_bump_now_flagged(self):
        """Regression (sec-auditor-found, 2026-09-12, live-verified before
        fixing): the original check keyed the re-seal guard on BOTH
        sealed_at AND holdout_ref unchanged -- an author could bump
        sealed_at while keeping the SAME holdout_ref and slip past
        undetected, defeating exactly the reuse this file exists to
        prevent. Now keyed on holdout_ref alone: same holdout_ref + a
        moved opened_at must be flagged regardless of sealed_at."""
        new_reseal_via_sealed_at = _CONSUMED.replace(
            "sealed_at: 2026-09-12", "sealed_at: 2026-09-19"
        ).replace("opened_at: 2026-09-13", "opened_at: 2026-09-20")
        signals = _weakening_signals(_CONSUMED, new_reseal_via_sealed_at)
        assert any("re-seal attempt" in s for s in signals)

    def test_reseal_via_inline_comment_now_flagged(self):
        """Regression (skeptic-found, 2026-09-12, verified via constructed
        input before fixing): an inline comment on `consumed: true`
        previously made _is_true() return False for the OLD content, so
        old_consumed read False and the re-seal branch never armed at all --
        the exact bypass _strip_inline_comment() closes."""
        old_with_comment = _CONSUMED.replace(
            "consumed: true", "consumed: true    # opened at VERIFY yesterday"
        )
        new_reseal = old_with_comment.replace("opened_at: 2026-09-13", "opened_at: 2026-09-20")
        signals = _weakening_signals(old_with_comment, new_reseal)
        assert any("re-seal attempt" in s for s in signals)

    def test_genuinely_new_holdout_not_flagged(self):
        """A DIFFERENT holdout_ref/sealed_at (a genuinely new seal, not a
        reopening of the old one) must not be flagged as a re-seal."""
        new_fresh = (
            "holdout_ref: sha256:zzzz\nsealed_at: 2026-09-20\nopened_at: null\nconsumed: false\n"
        )
        signals = _weakening_signals(_CONSUMED, new_fresh)
        assert signals == []

    def test_invalid_consumption_flagged(self):
        invalid = _UNSEALED.replace("consumed: false", "consumed: true")
        signals = _weakening_signals(_UNSEALED, invalid)
        assert any("structurally invalid consumption" in s for s in signals)

    def test_valid_open_not_flagged(self):
        signals = _weakening_signals(_UNSEALED, _CONSUMED)
        assert signals == []

    def test_no_change_not_flagged(self):
        assert _weakening_signals(_CONSUMED, _CONSUMED) == []

    def test_consumed_reversal_flagged(self):
        """Regression (Codex P1 finding, 2026-09-12, verified via a
        3-edit reproduction before fixing): flipping consumed=true -> false
        alone (opened_at/opened_by_stage/holdout_ref all unchanged) is the
        FIRST step of a bypass -- it disarms old_consumed for the NEXT call,
        letting a follow-up edit move opened_at unflagged, then a third edit
        flip consumed back to true. None of the three individual edits
        triggered a signal before this fix. Blocking the reversal itself
        closes the loophole at its first step."""
        reverted = _CONSUMED.replace("consumed: true", "consumed: false")
        signals = _weakening_signals(_CONSUMED, reverted)
        assert any("consumed-reversal attempt" in s for s in signals)

    def test_three_edit_reopen_bypass_blocked_at_step_one(self):
        """End-to-end reproduction of the exact bypass sequence Codex
        described: step 1 (consumed true->false) must now be blocked, which
        prevents steps 2 (move opened_at while unconsumed) and 3 (re-consume)
        from ever being reachable through this guard."""
        step1 = _CONSUMED.replace("consumed: true", "consumed: false")
        assert _weakening_signals(_CONSUMED, step1) != []  # blocked here

    def test_stage_relabel_while_consumed_flagged_as_reseal(self):
        """Regression (Codex P1 finding, 2026-09-12): opened_by_stage was not
        covered by the original re-seal check at all -- only opened_at was.
        A DEVELOP-stage opening later relabeled to VERIFY (opened_at itself
        unchanged) previously slipped through as an unrelated, unflagged
        field edit."""
        opened_in_develop = _CONSUMED.replace("opened_by_stage: VERIFY", "opened_by_stage: DEVELOP")
        relabeled_to_verify = opened_in_develop.replace(
            "opened_by_stage: DEVELOP", "opened_by_stage: VERIFY"
        )
        signals = _weakening_signals(opened_in_develop, relabeled_to_verify)
        assert any("re-seal attempt" in s for s in signals)

    def test_wrong_stage_at_consumption_flagged(self):
        """Regression (Codex P1 finding, 2026-09-12): a single edit that sets
        opened_at + opened_by_stage=DEVELOP + consumed=true together
        previously passed -- the only check at consumption time was
        "opened_at is set", never "opened_by_stage is VERIFY"."""
        opened_in_develop = (
            "holdout_ref: sha256:abcd\nsealed_at: 2026-09-12\nopened_at: 2026-09-13\n"
            "opened_by_stage: DEVELOP\nconsumed: true\n"
        )
        signals = _weakening_signals(_UNSEALED, opened_in_develop)
        assert any(
            "opened_by_stage" in s and "structurally invalid consumption" in s for s in signals
        )

    def test_structural_consumption_signals_used_for_brand_new_file(self):
        """The same shared helper used inside _weakening_signals's transition
        check must also catch a brand-new file born already consumed at the
        wrong stage -- exercised directly here, and via main()'s Write path
        in TestMainBlocking below."""
        fields = _extract_flat_fields(
            "holdout_ref: sha256:abcd\nopened_at: 2026-09-13\n"
            "opened_by_stage: DEVELOP\nconsumed: true\n"
        )
        signals = _structural_consumption_signals(fields)
        assert any("opened_by_stage" in s for s in signals)


class TestMainBlocking:
    def _run(self, monkeypatch, data: dict):
        monkeypatch.setattr("sys.stdin", _stdin(data))
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        try:
            main()
        except SystemExit as e:
            return e.code
        return None

    def test_edit_reseal_denied(self, monkeypatch, tmp_path, capsys):
        exp_dir = tmp_path / "experiments" / "20260101-test"
        exp_dir.mkdir(parents=True)
        holdout_path = exp_dir / "sealed_holdout.yaml"
        holdout_path.write_text(_CONSUMED, encoding="utf-8")

        data = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(holdout_path),
                "old_string": "opened_at: 2026-09-13",
                "new_string": "opened_at: 2026-09-20",
            },
        }
        self._run(monkeypatch, data)
        captured = capsys.readouterr()
        assert '"permissionDecision": "deny"' in captured.out
        assert "re-seal" in captured.out

    def test_edit_unrelated_field_allowed(self, monkeypatch, tmp_path, capsys):
        """A completely unrelated field edit (e.g. notes) on an ALREADY-consumed
        holdout must not be blocked -- only opened_at/consumed-shape changes are."""
        exp_dir = tmp_path / "experiments" / "20260101-test"
        exp_dir.mkdir(parents=True)
        holdout_path = exp_dir / "sealed_holdout.yaml"
        holdout_path.write_text(_CONSUMED + "internal_delta: 0.1\n", encoding="utf-8")

        data = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(holdout_path),
                "old_string": "internal_delta: 0.1",
                "new_string": "internal_delta: 0.15",
            },
        }
        self._run(monkeypatch, data)
        assert capsys.readouterr().out == ""

    def test_write_invalid_consumption_denied(self, monkeypatch, tmp_path, capsys):
        exp_dir = tmp_path / "experiments" / "20260101-test"
        exp_dir.mkdir(parents=True)
        holdout_path = exp_dir / "sealed_holdout.yaml"
        # Brand-new file (no on-disk content yet) that is already structurally invalid.
        data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(holdout_path),
                "content": "holdout_ref: sha256:abcd\nsealed_at: 2026-09-12\n"
                "opened_at: null\nconsumed: true\n",
            },
        }
        self._run(monkeypatch, data)
        captured = capsys.readouterr()
        assert '"permissionDecision": "deny"' in captured.out
        assert "structurally invalid consumption" in captured.out

    def test_write_valid_new_file_allowed(self, monkeypatch, tmp_path, capsys):
        exp_dir = tmp_path / "experiments" / "20260101-test"
        exp_dir.mkdir(parents=True)
        holdout_path = exp_dir / "sealed_holdout.yaml"
        data = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(holdout_path), "content": _UNSEALED},
        }
        self._run(monkeypatch, data)
        assert capsys.readouterr().out == ""

    def test_unrelated_file_not_gated(self, monkeypatch, tmp_path, capsys):
        other = tmp_path / "notes.txt"
        other.write_text("hello", encoding="utf-8")
        data = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(other), "content": "world"},
        }
        self._run(monkeypatch, data)
        assert capsys.readouterr().out == ""

    def test_malformed_tool_input_does_not_crash_or_deny(self, monkeypatch, capsys):
        """Regression (sec-auditor-found, 2026-09-12, live-verified before
        fixing): a non-dict tool_input previously crashed INSIDE the
        relevance check itself, before _is_sealed_holdout_file() ever ran --
        meaning ANY Edit/Write call with a malformed payload, not just ones
        targeting sealed_holdout.yaml, would raise. get_tool_input()'s own
        fallback plus the isinstance guard on file_path fix this."""
        data = {"tool_name": "Write", "tool_input": None}
        code = self._run(monkeypatch, data)
        assert code in (0, None)
        assert capsys.readouterr().out == ""

    def test_non_dict_top_level_payload_does_not_crash(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(["not", "a", "dict"])))
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        try:
            main()
        except SystemExit as e:
            code = e.code
        else:
            code = None
        assert code in (0, None)
        assert capsys.readouterr().out == ""
