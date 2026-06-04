"""Tests for estimand_guard.py — EstimandOps SessionStart nudge hook.

WHY: this hook nudges when an estimand.md has unfilled MCID/ICE, or when
claim.md exists without any estimand.md. It must fire only for research
projects (silent otherwise) and never block session start on error.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
)

import estimand_guard as eg  # noqa: E402

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


# ── main() ──────────────────────────────────────────────────────────────────


class TestMain:
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

    def test_never_raises_on_error(self, tmp_path, monkeypatch, capsys):
        def boom(_root):
            raise RuntimeError("simulated")

        monkeypatch.setattr(eg, "find_estimands", boom)
        monkeypatch.chdir(tmp_path)
        # Must not raise — SessionStart never blocks
        eg.main()
        captured = capsys.readouterr()
        assert "skipped" in captured.err or captured.out == ""
