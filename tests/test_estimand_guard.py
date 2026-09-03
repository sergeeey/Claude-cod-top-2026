"""Tests for estimand_guard.py — EstimandOps SessionStart nudge hook.

WHY: this hook nudges when an estimand.md has unfilled MCID/ICE, or when
claim.md exists without any estimand.md. It must fire only for research
projects (silent otherwise) and never block session start on error.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
)

import estimand_guard as eg

# ── find_estimands ──────────────────────────────────────────────────────────


class TestFindEstimands:
    def test_finds_estimand(self, tmp_path):
        exp = tmp_path / "experiments" / "e1"
        exp.mkdir(parents=True)
        (exp / "estimand.md").write_text("# Estimand", encoding="utf-8")
        found = eg.find_estimands(tmp_path)
        assert len(found) == 1

    def test_skips_template(self, tmp_path):
        tpl = tmp_path / "experiments" / "_template"
        tpl.mkdir(parents=True)
        (tpl / "estimand.md").write_text("# Template", encoding="utf-8")
        # _template path is excluded
        assert eg.find_estimands(tmp_path) == []

    def test_empty_when_none(self, tmp_path):
        assert eg.find_estimands(tmp_path) == []


# ── field_unfilled ──────────────────────────────────────────────────────────


class TestFieldUnfilled:
    def test_filled_value_returns_false(self):
        text = "MCID: 0.05 absolute risk difference"
        assert eg.field_unfilled(text, "MCID") is False

    def test_empty_value_returns_true(self):
        text = "MCID:"
        assert eg.field_unfilled(text, "MCID") is True

    def test_placeholder_returns_true(self):
        text = "MCID: [value]"
        assert eg.field_unfilled(text, "MCID") is True

    def test_tbd_placeholder_returns_true(self):
        text = "ICE: TBD"
        assert eg.field_unfilled(text, "ICE") is True

    def test_missing_label_returns_true(self):
        text = "Population: adults\nEndpoint: mortality"
        assert eg.field_unfilled(text, "MCID") is True

    def test_heading_is_skipped(self):
        # The '### MCID (...)' heading is NOT the value line; real value below is filled
        text = "### MCID (Minimum Clinically Important Difference)\nMCID: 0.1 RR"
        assert eg.field_unfilled(text, "MCID") is False


# ── _has_filled_ice_table ────────────────────────────────────────────────────


class TestHasFilledIceTable:
    def test_no_heading_returns_false(self):
        assert eg._has_filled_ice_table("MCID: 0.1\nEndpoint: mortality") is False

    def test_real_data_row_returns_true(self):
        """Regression (found 2026-07-29): the actual estimand.md template
        documents ICE as a table under '## Intercurrent Events (ICE)', not a
        flat 'ICE: value' line -- real experiments following that template
        were flagged as unfilled even with a complete table."""
        text = (
            "## Intercurrent Events (ICE)\n\n"
            "| Event | Strategy | Rationale |\n"
            "|---|---|---|\n"
            "| Patient discontinues treatment | treatment-policy | "
            "counted as part of the intervention effect |\n"
        )
        assert eg._has_filled_ice_table(text) is True

    def test_template_placeholder_row_returns_false(self):
        """The template's own literal unfilled row (bracketed placeholders)
        must NOT count as filled just because a table exists."""
        text = (
            "## Intercurrent Events (ICE)\n\n"
            "| Event | Strategy | Rationale |\n"
            "|---|---|---|\n"
            "| [event name] | treatment-policy / hypothetical / composite | [why this strategy] |\n"
        )
        assert eg._has_filled_ice_table(text) is False

    def test_header_only_no_data_rows_returns_false(self):
        text = "## Intercurrent Events (ICE)\n\n| Event | Strategy | Rationale |\n|---|---|---|\n"
        assert eg._has_filled_ice_table(text) is False

    def test_stops_at_next_heading(self):
        """A table belonging to a LATER, unrelated section must not be
        misread as this section's ICE table."""
        text = (
            "## Intercurrent Events (ICE)\n\n"
            "no table here, just prose\n\n"
            "## No-Collapse Tests\n\n"
            "| Test | Result |\n|---|---|\n| Data swap | PASS |\n"
        )
        assert eg._has_filled_ice_table(text) is False


# ── _has_ice_pointer ─────────────────────────────────────────────────────────


class TestHasIcePointer:
    def test_pointer_to_another_file_returns_true(self):
        """Regression (found 2026-07-29): a deliberate cross-reference to
        another file's ICE table (avoiding duplication) is a real, filled
        strategy, not a gap -- see
        20260727-config-effectiveness-opportunistic/estimand.md."""
        text = "See `claim.md` ICE table (task-abandoned / copy-crashed / ground-truth-ambiguous)."
        assert eg._has_ice_pointer(text) is True

    def test_unrelated_md_mention_does_not_trigger(self):
        text = "See `decisions.md` for architectural context.\nICE: [value]"
        assert eg._has_ice_pointer(text) is False

    def test_no_mention_returns_false(self):
        assert eg._has_ice_pointer("MCID: 0.1\nEndpoint: mortality") is False


# ── main() ──────────────────────────────────────────────────────────────────


class TestMain:
    def test_skips_walk_when_cwd_is_home_directory(self, monkeypatch, capsys):
        """Regression (2026-08-09, found via boyko-scientific-consortium
        dogfood run): a session with cwd == home directory made the
        unbounded root.glob("**/estimand.md") walk 66k+ dirs / 340k+ files,
        measured hanging up to the ~600s hook timeout ceiling. Home is never
        a real project for this guard -- must skip the walk entirely rather
        than let find_estimands() even attempt it."""
        monkeypatch.chdir(Path.home())

        def boom(_root):
            raise AssertionError("find_estimands() must not be called when cwd is home")

        monkeypatch.setattr(eg, "find_estimands", boom)
        eg.main()
        assert capsys.readouterr().out == ""

    def test_silent_for_non_research(self, tmp_path, monkeypatch, capsys):
        # No estimand.md, no claim.md → silent (non-research project)
        monkeypatch.chdir(tmp_path)
        eg.main()
        assert capsys.readouterr().out == ""

    def test_warns_claim_without_estimand(self, tmp_path, monkeypatch, capsys):
        exp = tmp_path / "experiments" / "e1"
        exp.mkdir(parents=True)
        (exp / "claim.md").write_text("# Claim", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        eg.main()
        out = capsys.readouterr().out
        assert "claim.md" in out and "estimand" in out

    def test_warns_unfilled_fields(self, tmp_path, monkeypatch, capsys):
        exp = tmp_path / "experiments" / "e1"
        exp.mkdir(parents=True)
        (exp / "estimand.md").write_text("MCID: [value]\nICE: TBD", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        eg.main()
        out = capsys.readouterr().out
        assert "unfilled" in out.lower() or "MCID" in out

    def test_silent_when_fields_filled(self, tmp_path, monkeypatch, capsys):
        exp = tmp_path / "experiments" / "e1"
        exp.mkdir(parents=True)
        (exp / "estimand.md").write_text(
            "MCID: 0.05 risk difference\nICE strategy: treatment-policy",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        eg.main()
        # All fields filled → no nudge
        assert capsys.readouterr().out == ""

    def test_strategy_heading_does_not_suppress_ice_warning(self, tmp_path, monkeypatch, capsys):
        # WHY (Codex regression): a bare "## Strategy notes" heading used to
        # suppress the ICE warning even with ICE: empty (false negative).
        exp = tmp_path / "experiments" / "e1"
        exp.mkdir(parents=True)
        (exp / "estimand.md").write_text(
            "MCID: 0.05 risk difference\nICE:\n\n## Strategy notes\nsome prose",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        eg.main()
        # ICE field is empty → warning MUST still fire despite 'Strategy' heading
        assert "ICE" in capsys.readouterr().out

    def test_silent_when_ice_is_a_filled_table(self, tmp_path, monkeypatch, capsys):
        """Regression (found 2026-07-29): the guard's own real template shape
        (table under a heading) must silence the warning, same as a filled
        flat line does."""
        exp = tmp_path / "experiments" / "e1"
        exp.mkdir(parents=True)
        (exp / "estimand.md").write_text(
            "MCID: 0.05 risk difference\n\n"
            "## Intercurrent Events (ICE)\n\n"
            "| Event | Strategy | Rationale |\n|---|---|---|\n"
            "| Dropout | treatment-policy | counted as part of the effect |\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        eg.main()
        assert capsys.readouterr().out == ""

    def test_silent_when_ice_is_a_pointer(self, tmp_path, monkeypatch, capsys):
        exp = tmp_path / "experiments" / "e1"
        exp.mkdir(parents=True)
        (exp / "estimand.md").write_text(
            "MCID: 0.05 risk difference\nSee `claim.md` ICE table (dropout / crash).\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        eg.main()
        assert capsys.readouterr().out == ""

    def test_table_with_only_placeholder_row_still_warns(self, tmp_path, monkeypatch, capsys):
        exp = tmp_path / "experiments" / "e1"
        exp.mkdir(parents=True)
        (exp / "estimand.md").write_text(
            "MCID: 0.05 risk difference\n\n"
            "## Intercurrent Events (ICE)\n\n"
            "| Event | Strategy | Rationale |\n|---|---|---|\n"
            "| [event name] | treatment-policy | [why this strategy] |\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        eg.main()
        assert "ICE" in capsys.readouterr().out

    def test_never_raises_on_error(self, tmp_path, monkeypatch, capsys):
        def boom(_root):
            raise RuntimeError("simulated")

        monkeypatch.setattr(eg, "find_estimands", boom)
        monkeypatch.chdir(tmp_path)
        # Must not raise — SessionStart never blocks
        eg.main()
        captured = capsys.readouterr()
        assert "skipped" in captured.err or captured.out == ""
