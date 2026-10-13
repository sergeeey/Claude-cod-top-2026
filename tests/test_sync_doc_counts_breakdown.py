"""The wired / dormant / library BREAKDOWN of the hook total is synced and gated, not hand-copied.

Found 2026-10-02 by an external review of the public repo: README prose said "83 of the 95 are
wired; 6 are dormant", a badge title said "88 wired, 2 dormant, 6 internal library modules" under a
badge saying 102 defined (96 != 102), and the generated matrix said 94 / 2 / 6. `sync_doc_counts`
synced only the total, so the parts drifted unseen.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import gen_hook_matrix  # noqa: E402
import sync_doc_counts  # noqa: E402
from sync_doc_counts import (  # noqa: E402
    _ANCHORS,
    REPO,
    _apply_anchor,
    actual_counts,
    wiring_breakdown,
)

BREAKDOWN_KINDS = {"hooks_wired", "hooks_dormant", "hooks_library"}


def breakdown_anchors():
    return [a for a in _ANCHORS if BREAKDOWN_KINDS & set(a[2])]


def readme_text() -> str:
    with (REPO / "README.md").open(encoding="utf-8", newline="") as f:
        return f.read()


class TestWiringBreakdown:
    def test_it_comes_from_the_classifier_that_generates_the_matrix(self):
        _text, counts = gen_hook_matrix.build_matrix()
        assert wiring_breakdown() == {
            "hooks_wired": counts["wired"],
            "hooks_dormant": counts["dormant"],
            "hooks_library": counts["library"],
        }

    def test_the_parts_add_up_to_the_total_so_nothing_is_orphaned_or_mismatched(self):
        parts = wiring_breakdown()
        assert sum(parts.values()) == actual_counts()["hooks"], (
            "wired + dormant + library != hook total: some registry entries are orphaned or "
            "their class disagrees with settings.json -- the README would state a breakdown that "
            "does not add up"
        )

    def test_values_are_plain_non_negative_ints(self):
        for key, value in wiring_breakdown().items():
            assert key in BREAKDOWN_KINDS and isinstance(value, int) and value >= 0


class TestReadmeBreakdownIsAnchored:
    def test_both_places_that_state_the_breakdown_are_covered(self):
        assert len(breakdown_anchors()) == 2  # the prose sentence and the badge title

    def test_every_anchor_is_found_in_the_real_readme(self):
        text = readme_text()
        for _file, pattern, kinds in breakdown_anchors():
            _new, _changed, error = _apply_anchor(text, pattern, kinds, self.actual())
            assert error is None, error

    def test_the_real_readme_already_matches_the_matrix(self):
        text = readme_text()
        for _file, pattern, kinds in breakdown_anchors():
            _new, changed, error = _apply_anchor(text, pattern, kinds, self.actual())
            assert error is None and not changed, f"README drifted from the matrix: {pattern}"

    def test_no_second_unanchored_breakdown_remains_in_the_readme(self):
        """Any other 'N wired' / 'N dormant' phrase in the README would be an unguarded copy."""
        import re

        text = readme_text()
        stated = re.findall(r"(\d+) (?:of the \d+ are )?(?:wired|dormant)\b", text)
        parts = wiring_breakdown()
        allowed = {str(parts["hooks_wired"]), str(parts["hooks_dormant"])}
        assert set(stated) <= allowed, (
            f"unanchored breakdown numbers in README: {sorted(set(stated) - allowed)}"
        )

    @staticmethod
    def actual():
        actual = actual_counts()
        actual.update(wiring_breakdown())
        return actual


class TestStaleBreakdownIsDetectedAndFixed:
    PROSE = (
        "> probabilistic instructions. 83 of the 95 are wired; 6 are dormant (defined, not yet\n"
        "> triggered) and 6 are internal library modules other hooks import.\n"
    )
    BADGE = '<img alt="102 hooks defined" title="88 wired, 2 dormant, 6 internal library modules — see x"/>'
    FAKE = {"hooks": 102, "hooks_wired": 94, "hooks_dormant": 2, "hooks_library": 6}

    def anchor(self, fragment: str):
        return next(a for a in breakdown_anchors() if fragment in a[1])

    def test_the_stale_prose_is_corrected_in_all_four_numbers(self):
        _f, pattern, kinds = self.anchor("probabilistic")
        new, changed, error = _apply_anchor(self.PROSE, pattern, kinds, self.FAKE)
        assert error is None and changed
        assert "94 of the 102 are wired; 2 are dormant" in new and "and 6 are internal" in new
        assert "83" not in new and "of the 95" not in new

    def test_the_stale_badge_title_is_corrected(self):
        _f, pattern, kinds = self.anchor("title=")
        new, changed, error = _apply_anchor(self.BADGE, pattern, kinds, self.FAKE)
        assert error is None and changed and 'title="94 wired, 2 dormant, 6 internal' in new

    def test_correct_text_is_left_alone(self):
        _f, pattern, kinds = self.anchor("probabilistic")
        fixed, _c, _e = _apply_anchor(self.PROSE, pattern, kinds, self.FAKE)
        again, changed, error = _apply_anchor(fixed, pattern, kinds, self.FAKE)
        assert error is None and not changed and again == fixed

    def test_reflowed_prose_is_reported_not_silently_ignored(self):
        """If someone re-wraps the sentence the anchor stops matching: that must be an ERROR that
        needs a human, never a silent no-op that lets the numbers rot again."""
        _f, pattern, kinds = self.anchor("probabilistic")
        reflowed = self.PROSE.replace("not yet\n> triggered", "not yet triggered")
        _new, changed, error = _apply_anchor(reflowed, pattern, kinds, self.FAKE)
        assert not changed and error is not None and "anchor not found" in error


class TestGateFailsOnStaleBreakdown:
    def run_main(self, tmp_path, monkeypatch, readme_text_value, argv):
        readme = tmp_path / "README.md"
        readme.write_bytes(readme_text_value.encode("utf-8"))
        monkeypatch.setattr(sync_doc_counts, "REPO", tmp_path)
        monkeypatch.setattr(sync_doc_counts, "_ANCHORS", breakdown_anchors())
        monkeypatch.setattr(
            sync_doc_counts, "actual_counts", lambda: {"hooks": 102, "agents": 13, "skills": 135}
        )
        monkeypatch.setattr(
            sync_doc_counts,
            "wiring_breakdown",
            lambda: {"hooks_wired": 94, "hooks_dormant": 2, "hooks_library": 6},
        )
        monkeypatch.setattr(sync_doc_counts, "event_count", lambda: 25)
        monkeypatch.setattr(
            sync_doc_counts, "maturity_counts", lambda: {"dogfooded": 1, "benchmarked": 0}
        )
        monkeypatch.setattr("sys.argv", ["sync_doc_counts.py", *argv])
        return sync_doc_counts.main(), readme

    STALE = (
        "> probabilistic instructions. 83 of the 95 are wired; 6 are dormant (defined, not yet\n"
        "> triggered) and 6 are internal library modules other hooks import.\n"
        '<img title="88 wired, 2 dormant, 6 internal library modules — see x"/>\n'
    )

    def test_check_mode_exits_nonzero_and_writes_nothing(self, tmp_path, monkeypatch):
        rc, readme = self.run_main(tmp_path, monkeypatch, self.STALE, ["--check"])
        assert rc == 1
        assert readme.read_bytes().decode("utf-8") == self.STALE

    def test_write_mode_repairs_it_and_keeps_lf(self, tmp_path, monkeypatch):
        rc, readme = self.run_main(tmp_path, monkeypatch, self.STALE, [])
        data = readme.read_bytes()
        assert rc == 0 and b"\r\n" not in data
        text = data.decode("utf-8")
        assert (
            "94 of the 102 are wired; 2 are dormant" in text
            and 'title="94 wired, 2 dormant, 6' in text
        )

    @pytest.mark.parametrize("argv", [["--check"], []])
    def test_a_correct_readme_passes(self, tmp_path, monkeypatch, argv):
        good = (
            "> probabilistic instructions. 94 of the 102 are wired; 2 are dormant (defined, not yet\n"
            "> triggered) and 6 are internal library modules other hooks import.\n"
            '<img title="94 wired, 2 dormant, 6 internal library modules — see x"/>\n'
        )
        rc, _ = self.run_main(tmp_path, monkeypatch, good, argv)
        assert rc == 0
