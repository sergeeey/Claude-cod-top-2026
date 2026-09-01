"""Tests for scripts/evidence_marker_audit.py.

WHY: this script exists to mechanically count evidence markers (a `sorry`-
counter for prose claims, see the script's own module docstring) -- it needs
its own test coverage like any other script, not a free pass for being small.
"""

from __future__ import annotations

from scripts.evidence_marker_audit import (
    INFO_MARKERS,
    RESOLVED_MARKERS,
    UNRESOLVED_MARKERS,
    count_markers,
    main,
)


class TestCountMarkers:
    def test_bare_marker_form(self):
        counts = count_markers("This claim is [VERIFIED] and this one is [HYPOTHESIS].")
        assert counts["VERIFIED"] == 1
        assert counts["HYPOTHESIS"] == 1

    def test_cited_marker_form(self):
        """Real usage in this repo: `[VERIFIED: git log -1]`, not bare."""
        counts = count_markers("[VERIFIED: `git log -1`, `git branch --show-current`]")
        assert counts["VERIFIED"] == 1

    def test_hyphenated_marker_form(self):
        """Real usage in integrity.md: `[VERIFIED-REAL]`, `[VERIFIED-SYNTHETIC]`."""
        counts = count_markers("Result confirmed [VERIFIED-REAL] on 3 real sources.")
        assert counts["VERIFIED"] == 1

    def test_no_markers_present(self):
        counts = count_markers("No markers here at all.")
        assert sum(counts.values()) == 0

    def test_multiple_distinct_markers_counted_separately(self):
        text = "[UNKNOWN] then [WEAKENED] then another [UNKNOWN] and [VERIFIED]."
        counts = count_markers(text)
        assert counts["UNKNOWN"] == 2
        assert counts["WEAKENED"] == 1
        assert counts["VERIFIED"] == 1

    def test_does_not_match_unrelated_bracket_text(self):
        counts = count_markers("See [some link](url) and [Table 3] for details.")
        assert sum(counts.values()) == 0

    def test_marker_lists_are_disjoint(self):
        """A marker must not appear in more than one of the three groups --
        otherwise counts double up silently."""
        all_lists = RESOLVED_MARKERS + UNRESOLVED_MARKERS + INFO_MARKERS
        assert len(all_lists) == len(set(all_lists))


class TestMainCli:
    def test_reports_resolved_marker_and_exits_zero(self, tmp_path, capsys):
        f = tmp_path / "claim.md"
        f.write_text("Confirmed [VERIFIED] against real data.", encoding="utf-8")
        exit_code = main([str(f)])
        out = capsys.readouterr().out
        assert exit_code == 0
        assert "VERIFIED" in out

    def test_strict_mode_exits_nonzero_on_unresolved_marker(self, tmp_path):
        f = tmp_path / "claim.md"
        f.write_text("Still [HYPOTHESIS], not yet checked.", encoding="utf-8")
        exit_code = main([str(f), "--strict"])
        assert exit_code == 1

    def test_strict_mode_exits_zero_when_only_resolved_markers_present(self, tmp_path):
        f = tmp_path / "claim.md"
        f.write_text("Fully [VERIFIED] and [CONFIRMED-REAL].", encoding="utf-8")
        exit_code = main([str(f), "--strict"])
        assert exit_code == 0

    def test_without_strict_flag_always_exits_zero_even_with_unresolved(self, tmp_path):
        """This script reports, promotion_gate_guard.py decides -- --strict
        is opt-in, matching this repo's own soft-nudge-vs-hard-gate split."""
        f = tmp_path / "claim.md"
        f.write_text("[UNKNOWN] whether this holds.", encoding="utf-8")
        exit_code = main([str(f)])
        assert exit_code == 0

    def test_no_matching_files_exits_with_error_code(self, tmp_path):
        missing = tmp_path / "does_not_exist.md"
        exit_code = main([str(missing)])
        assert exit_code == 2

    def test_glob_pattern_audits_multiple_files(self, tmp_path, capsys):
        (tmp_path / "a.md").write_text("[VERIFIED] here.", encoding="utf-8")
        (tmp_path / "b.md").write_text("[WEAKENED] there.", encoding="utf-8")
        exit_code = main([str(tmp_path / "*.md")])
        out = capsys.readouterr().out
        assert exit_code == 0
        assert "a.md" in out
        assert "b.md" in out
