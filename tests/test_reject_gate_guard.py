"""Tests for reject_gate_guard.py — the NULL Exploitation Gate."""

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

import reject_gate_guard
from reject_gate_guard import (
    _check_reason_specific,
    _check_relaxation_map,
    _check_what_killed,
    _check_what_survived,
    _has_reject,
    _is_decision_md,
    _is_placeholder,
    _section,
    main,
)

# ── path / verdict helpers ────────────────────────────────────────────────────


class TestIsDecisionMd:
    def test_valid(self):
        assert _is_decision_md("experiments/20260101-x/decision.md")

    def test_nested(self):
        assert _is_decision_md("D:/repo/experiments/20260101-x/decision.md")

    def test_wrong_name(self):
        assert not _is_decision_md("experiments/20260101-x/claim.md")

    def test_no_experiments(self):
        assert not _is_decision_md("docs/decision.md")


class TestHasReject:
    def test_detects_checked(self):
        assert _has_reject("- [x] REJECT — claim falsified")

    def test_ignores_unchecked(self):
        assert not _has_reject("- [ ] REJECT — claim falsified")

    def test_case_insensitive(self):
        assert _has_reject("- [X] reject")

    def test_promote_is_not_reject(self):
        assert not _has_reject("- [x] PROMOTE — holds")


class TestIsPlaceholder:
    def test_empty(self):
        assert _is_placeholder("")
        assert _is_placeholder("{  }")
        assert _is_placeholder("A_")
        assert _is_placeholder("V1:")

    def test_real_value(self):
        assert not _is_placeholder("spinor index argument")


# ── section extraction ────────────────────────────────────────────────────────


class TestSection:
    def test_extracts_until_same_level(self):
        md = "### What Was Killed\nbody1\n### What Was NOT Killed\nbody2\n"
        sec = _section(md, "What Was Killed")
        assert "body1" in sec
        assert "body2" not in sec

    def test_missing_returns_none(self):
        assert _section("## Other\n", "Nonexistent") is None

    def test_stops_at_higher_level(self):
        md = "### Relaxation Map\nrow\n## Rescue Review\nother\n"
        sec = _section(md, "Relaxation Map")
        assert "row" in sec
        assert "other" not in sec


# ── condition 1: what was killed ──────────────────────────────────────────────


class TestWhatKilled:
    def test_empty_template_fails(self):
        md = (
            "### What Was Killed\n"
            "_instruction_\n"
            "- The claim as stated under: {  }\n"
            "- Specifically, assumption(s) killed: {  }\n"
            "### What Was NOT Killed\n"
        )
        passed, _ = _check_what_killed(md)
        assert not passed

    def test_filled_passes(self):
        md = (
            "### What Was Killed\n"
            "- The claim as stated under: single-bundle ansatz on S6\n"
            "### What Was NOT Killed\n"
        )
        passed, _ = _check_what_killed(md)
        assert passed

    def test_missing_section_fails(self):
        passed, detail = _check_what_killed("## Rationale\nx\n")
        assert not passed
        assert "missing" in detail

    def test_tbd_placeholder_fails(self):
        """Regression (HIGH): "What Was Killed: TBD" previously passed as
        filled content because "tbd"/"todo" weren't in _PLACEHOLDERS."""
        md = "### What Was Killed\n- The claim as stated under: TBD\n### Next\n"
        passed, _ = _check_what_killed(md)
        assert not passed

    def test_todo_placeholder_fails(self):
        md = "### What Was Killed\n- The claim as stated under: TODO\n### Next\n"
        passed, _ = _check_what_killed(md)
        assert not passed


# ── condition 2: what survived ────────────────────────────────────────────────


class TestWhatSurvived:
    def test_empty_template_fails(self):
        md = (
            "### What Was NOT Killed\n"
            "- [ ] Core mechanism / theoretical basis:\n"
            "- [ ] Assumption [A_]: (survived because: )\n"
            "### Relaxation Map\n"
        )
        passed, _ = _check_what_survived(md)
        assert not passed

    def test_checked_survivor_passes(self):
        md = (
            "### What Was NOT Killed\n"
            "- [x] Core mechanism / theoretical basis: Atiyah-Singer index argument\n"
            "### Relaxation Map\n"
        )
        passed, _ = _check_what_survived(md)
        assert passed

    def test_colon_value_passes(self):
        md = (
            "### What Was NOT Killed\n"
            "- Assumption A1: lambda stays constant across the fibre\n"
            "### Relaxation Map\n"
        )
        passed, _ = _check_what_survived(md)
        assert passed


# ── condition 3: relaxation map ───────────────────────────────────────────────


class TestRelaxationMap:
    def test_only_placeholders_fails(self):
        md = (
            "### Relaxation Map\n"
            "| Assumption | Modification | New Path | Known kill-evidence? | Cheapest test |\n"
            "|---|---|---|---|---|\n"
            "| A_ | Remove | V1: | No | [test, N days] |\n"
            "| A_ | Weaken | V2: | No | [test, N days] |\n"
            "### Escape Point\n"
        )
        passed, _ = _check_relaxation_map(md)
        assert not passed

    def test_real_row_passes(self):
        md = (
            "### Relaxation Map\n"
            "| Assumption | Modification | New Path | Known kill-evidence? | Cheapest test |\n"
            "|---|---|---|---|---|\n"
            "| equal radii | Weaken | V2: unequal S3/S6 radii | No | spectral recompute, 1d |\n"
            "### Escape Point\n"
        )
        passed, _ = _check_relaxation_map(md)
        assert passed

    def test_missing_section_fails(self):
        passed, detail = _check_relaxation_map("## Rationale\n")
        assert not passed
        assert "missing" in detail


# ── condition 4: reason specificity ───────────────────────────────────────────


class TestReasonSpecific:
    def test_vague_reason_fails(self):
        md = "## Rationale\nThe experiment didn't work, moving on.\n## Next\n"
        passed, detail = _check_reason_specific(md)
        assert not passed
        assert "vague" in detail

    def test_russian_vague_fails(self):
        md = "## Rationale\nНе получилось добиться результата.\n## Next\n"
        passed, _ = _check_reason_specific(md)
        assert not passed

    def test_structural_reason_passes(self):
        md = (
            "## Rationale\n"
            "χ(S6)=2 forbids a single bundle with c3=6 giving index 3; the "
            "topological obstruction is exact.\n"
            "## Next\n"
        )
        passed, _ = _check_reason_specific(md)
        assert passed

    def test_empty_rationale_fails(self):
        """Regression (HIGH): an empty/missing Rationale section trivially
        contains none of the VAGUE_REASONS phrases, so it previously passed
        this condition despite having no reason at all -- absence of a bad
        signal was being treated as presence of a good one."""
        md = "## Rationale\n\n## Next\n"
        passed, detail = _check_reason_specific(md)
        assert not passed
        assert "no kill reason found" in detail

    def test_missing_rationale_section_fails(self):
        md = "## Next\nsomething else\n"
        passed, detail = _check_reason_specific(md)
        assert not passed
        assert "no kill reason found" in detail

    def test_reason_in_what_was_killed_passes_without_rationale_section(self):
        # A real reason stated under "What Was Killed" alone should still count.
        md = "## What Was Killed\nχ(S6)=2 forbids the ansatz; exact obstruction.\n"
        passed, _ = _check_reason_specific(md)
        assert passed


# ── integration: a fully filled REJECT passes all four ────────────────────────


COMPLETE_REJECT = (
    "- [x] REJECT — claim falsified\n"
    "## Rationale\n"
    "χ(S6)=2 is an exact topological obstruction; no single bundle works.\n"
    "## If REJECT: Kill Analysis\n"
    "### What Was Killed\n"
    "- The claim as stated under: single-bundle ansatz, c3=6\n"
    "### What Was NOT Killed\n"
    "- [x] Core mechanism: multi-bundle index decomposition survives\n"
    "### Relaxation Map\n"
    "| Assumption | Modification | New Path | Known kill-evidence? | Cheapest test |\n"
    "|---|---|---|---|---|\n"
    "| single bundle | Replace | V3: split into 3 line bundles | No | index calc, 1d |\n"
    "### Escape Point\n"
)

INCOMPLETE_REJECT = "- [x] REJECT — claim falsified\n## Rationale\nit didn't work\n"


class TestFullDecisionPasses:
    def test_complete_kill_analysis(self):
        for fn in (
            _check_what_killed,
            _check_what_survived,
            _check_relaxation_map,
            _check_reason_specific,
        ):
            passed, detail = fn(COMPLETE_REJECT)
            assert passed, f"{fn.__name__} failed: {detail}"


# ── main() ─────────────────────────────────────────────────────────────────────
#
# WHY these classes exist: the tests above cover every _check_* helper
# individually but never exercise the hook entrypoint that wires stdin
# parsing, path/verdict filtering, and the pass/fail message assembly
# together.


def _stdin(monkeypatch, payload):
    text = (
        "" if payload is None else json.dumps(payload) if not isinstance(payload, str) else payload
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))


class TestMain:
    def test_recursion_guard_skips_when_invoked_by_subagent(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_INVOKED_BY", "some-agent")
        _stdin(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "experiments/x/decision.md",
                    "content": COMPLETE_REJECT,
                },
            },
        )
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_invalid_json_stdin_exits_quietly(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        _stdin(monkeypatch, "not json")
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_wrong_tool_name_exits_quietly(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        _stdin(
            monkeypatch,
            {
                "tool_name": "Read",
                "tool_input": {"file_path": "experiments/x/decision.md"},
            },
        )
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_missing_file_path_exits_quietly(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        _stdin(monkeypatch, {"tool_name": "Write", "tool_input": {}})
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_non_decision_md_path_exits_quietly(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        _stdin(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "experiments/x/claim.md",
                    "content": COMPLETE_REJECT,
                },
            },
        )
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_unreadable_file_with_no_inline_content_exits_quietly(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        missing = tmp_path / "experiments" / "x" / "decision.md"
        _stdin(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(missing)},
            },
        )
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_content_falls_back_to_reading_file_when_absent(self, monkeypatch, tmp_path, capsys):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        decision = tmp_path / "experiments" / "x" / "decision.md"
        decision.parent.mkdir(parents=True)
        decision.write_text(COMPLETE_REJECT, encoding="utf-8")
        _stdin(
            monkeypatch,
            {"tool_name": "Edit", "tool_input": {"file_path": str(decision)}},
        )
        main()  # falls through to print, no sys.exit
        out = capsys.readouterr().out
        assert "null-gate" in out

    def test_content_from_new_string_key(self, monkeypatch, capsys):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        _stdin(
            monkeypatch,
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": "experiments/x/decision.md",
                    "new_string": COMPLETE_REJECT,
                },
            },
        )
        main()
        out = capsys.readouterr().out
        assert "null-gate" in out

    def test_non_reject_content_exits_quietly(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        _stdin(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "experiments/x/decision.md",
                    "content": "- [x] PROMOTE — claim holds\n",
                },
            },
        )
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_complete_reject_passes_all_conditions(self, monkeypatch, capsys):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        _stdin(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "experiments/x/decision.md",
                    "content": COMPLETE_REJECT,
                },
            },
        )
        main()
        out = capsys.readouterr().out
        payload = json.loads(out)
        msg = payload["hookSpecificOutput"]["additionalContext"]
        assert "NULL Exploitation Gate passed" in msg
        assert payload["hookSpecificOutput"]["hookEventName"] == "PostToolUse"

    def test_incomplete_reject_reports_failed_conditions(self, monkeypatch, capsys):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        _stdin(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "experiments/x/decision.md",
                    "content": INCOMPLETE_REJECT,
                },
            },
        )
        main()
        out = capsys.readouterr().out
        payload = json.loads(out)
        msg = payload["hookSpecificOutput"]["additionalContext"]
        assert "NOT met" in msg
        assert "dead end, not a fork" in msg

    def test_a_raising_check_is_caught_and_reported_as_failed(self, monkeypatch, capsys):
        # WHY: main() wraps each check call in try/except so a bug in one
        # checker can't break the write itself -- must verify that branch.
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        _stdin(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "experiments/x/decision.md",
                    "content": COMPLETE_REJECT,
                },
            },
        )
        with patch.object(
            reject_gate_guard, "_check_what_killed", side_effect=RuntimeError("boom")
        ):
            main()
        out = capsys.readouterr().out
        payload = json.loads(out)
        msg = payload["hookSpecificOutput"]["additionalContext"]
        assert "check failed: boom" in msg
        assert "NOT met" in msg
