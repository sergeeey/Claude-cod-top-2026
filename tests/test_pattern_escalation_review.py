"""Tests for pattern_escalation_review.py.

WHY: this hook decides whether to surface a "weekly review" of recurring
patterns in patterns.md. The decision depends on (1) when the last review
ran, (2) what entries patterns.md contains. Both are I/O — so we mock the
filesystem and verify the pure logic.
"""

from __future__ import annotations

import io
import json
import os
import sys
from datetime import date, timedelta

import pytest

# WHY: hooks/ lives one level above tests/. Match the other hook tests.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
)

import pattern_escalation_review as per  # noqa: E402

# ── _extract_escalation_candidates ────────────────────────────────────────────


class TestExtractEscalationCandidates:
    def test_returns_empty_on_empty_text(self):
        # ARRANGE: empty patterns.md
        assert per._extract_escalation_candidates("") == []

    def test_skips_below_threshold(self):
        # ARRANGE: pattern at [×2] is BELOW the threshold (3)
        text = "## [AVOID] [Types] something [×2]\n\nbody"
        # ACT / ASSERT
        assert per._extract_escalation_candidates(text) == []

    def test_picks_up_threshold_count(self):
        # ARRANGE: pattern exactly at [×3] qualifies
        text = "## [AVOID] [Types] datetime mix [×3]\n\nbody"
        # ACT
        result = per._extract_escalation_candidates(text)
        # ASSERT
        assert len(result) == 1
        title, count = result[0]
        assert "datetime mix" in title
        assert count == 3

    def test_picks_up_above_threshold(self):
        # ARRANGE
        text = "## [AVOID] [Async] race condition [×7]\n\nbody"
        # ACT / ASSERT
        result = per._extract_escalation_candidates(text)
        assert result == [("[AVOID] [Async] race condition", 7)]

    def test_skips_critical_tagged(self):
        # ARRANGE: pattern is at threshold but ALREADY escalated → skip
        text = "## [AVOID] [CRITICAL] [Types] something [×5]\n\nbody"
        # ACT / ASSERT
        assert per._extract_escalation_candidates(text) == []

    def test_skips_rule_promoted_tagged(self):
        # ARRANGE: previously promoted → skip
        text = "## [AVOID] [RULE-PROMOTED] [Types] thing [×9]\n\nbody"
        # ACT / ASSERT
        assert per._extract_escalation_candidates(text) == []

    def test_sorts_by_count_desc(self):
        # ARRANGE: multiple candidates, mixed counts
        text = (
            "## [AVOID] [Types] low recurrence [×3]\n"
            "body1\n"
            "## [AVOID] [Async] high recurrence [×8]\n"
            "body2\n"
            "## [AVOID] [DB] medium recurrence [×5]\n"
            "body3\n"
        )
        # ACT
        result = per._extract_escalation_candidates(text)
        # ASSERT: ordered by count descending
        counts = [c for _, c in result]
        assert counts == [8, 5, 3]

    def test_handles_mixed_critical_and_normal(self):
        # ARRANGE: one critical-tagged (skip), one normal (keep)
        text = (
            "## [AVOID] [CRITICAL] [Types] tagged [×5]\n"
            "body\n"
            "## [AVOID] [Types] untagged [×4]\n"
            "body\n"
        )
        # ACT
        result = per._extract_escalation_candidates(text)
        # ASSERT: only untagged appears
        assert len(result) == 1
        assert "untagged" in result[0][0]


# ── _is_review_due ────────────────────────────────────────────────────────────


class TestIsReviewDue:
    def test_true_when_no_state_file(self, tmp_path, monkeypatch):
        # ARRANGE: state file doesn't exist
        monkeypatch.setattr(per, "_LAST_REVIEW_FILE", tmp_path / "missing.txt")
        # ACT / ASSERT
        assert per._is_review_due(date.today()) is True

    def test_false_when_last_review_recent(self, tmp_path, monkeypatch):
        # ARRANGE: review was yesterday — within interval
        state = tmp_path / "last.txt"
        state.write_text((date.today() - timedelta(days=1)).isoformat(), encoding="utf-8")
        monkeypatch.setattr(per, "_LAST_REVIEW_FILE", state)
        # ACT / ASSERT: not due yet
        assert per._is_review_due(date.today()) is False

    def test_true_when_interval_elapsed(self, tmp_path, monkeypatch):
        # ARRANGE: review was 7 days ago — exactly at interval
        state = tmp_path / "last.txt"
        state.write_text((date.today() - timedelta(days=7)).isoformat(), encoding="utf-8")
        monkeypatch.setattr(per, "_LAST_REVIEW_FILE", state)
        # ACT / ASSERT: due
        assert per._is_review_due(date.today()) is True

    def test_true_on_unparseable_state(self, tmp_path, monkeypatch):
        # ARRANGE: state file has garbage
        state = tmp_path / "last.txt"
        state.write_text("not-a-date", encoding="utf-8")
        monkeypatch.setattr(per, "_LAST_REVIEW_FILE", state)
        # ACT / ASSERT: defensive default — treat as due
        assert per._is_review_due(date.today()) is True


# ── _format_message ───────────────────────────────────────────────────────────


class TestFormatMessage:
    def test_empty_candidates_returns_healthy_message(self):
        msg = per._format_message([])
        assert "no patterns" in msg.lower() or "healthy" in msg.lower()

    def test_single_candidate_listed(self):
        msg = per._format_message([("[AVOID] [Types] datetime mix", 3)])
        assert "datetime mix" in msg
        assert "×3" in msg

    def test_truncates_at_10(self):
        # ARRANGE: 15 candidates
        cands = [(f"[AVOID] [Cat] item-{i}", 3 + i) for i in range(15)]
        msg = per._format_message(cands)
        # ASSERT: bullet list cap + "more" line
        assert msg.count("•") == 10
        assert "5 more" in msg

    def test_suggests_action(self):
        # ARRANGE: any non-empty list
        msg = per._format_message([("[AVOID] [Types] thing", 4)])
        # ASSERT: tells user what to do
        assert "promote" in msg.lower() or "rule" in msg.lower()


# ── main() ────────────────────────────────────────────────────────────────────


def _make_stdin(payload: dict) -> io.StringIO:
    return io.StringIO(json.dumps(payload))


class TestMain:
    def test_exits_silent_when_not_due(self, tmp_path, monkeypatch, capsys: pytest.CaptureFixture):
        # ARRANGE: state file is from today — not due
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        state = state_dir / "last.txt"
        state.write_text(date.today().isoformat(), encoding="utf-8")
        monkeypatch.setattr(per, "_LAST_REVIEW_FILE", state)
        monkeypatch.setattr(per, "_STATE_DIR", state_dir)
        monkeypatch.setattr("sys.stdin", _make_stdin({}))

        # ACT
        with pytest.raises(SystemExit) as exc:
            per.main()

        # ASSERT: exit 0, no output
        assert exc.value.code == 0 or exc.value.code is None
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_emits_when_due_and_candidates_exist(
        self, tmp_path, monkeypatch, capsys: pytest.CaptureFixture
    ):
        # ARRANGE: state missing → due; patterns.md has 1 escalation candidate
        state_dir = tmp_path / "state"
        monkeypatch.setattr(per, "_STATE_DIR", state_dir)
        monkeypatch.setattr(per, "_LAST_REVIEW_FILE", state_dir / "last.txt")

        patterns = tmp_path / "patterns.md"
        patterns.write_text(
            "## [AVOID] [Types] datetime utcnow naive [×3]\n\nbody\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(per, "_PATTERNS_CANONICAL", patterns)
        monkeypatch.setattr(per, "_PATTERNS_LEGACY", tmp_path / "_auto" / "patterns.md")

        monkeypatch.setattr("sys.stdin", _make_stdin({}))

        # ACT
        per.main()

        # ASSERT: JSON output to stdout contains pattern-escalation context
        captured = capsys.readouterr()
        assert "pattern-escalation" in captured.out
        assert "datetime utcnow naive" in captured.out
        # AND state file was created with today's date
        assert (state_dir / "last.txt").exists()
        recorded = (state_dir / "last.txt").read_text(encoding="utf-8")
        assert recorded.startswith(date.today().isoformat())

    def test_no_patterns_file_anywhere_silent(
        self, tmp_path, monkeypatch, capsys: pytest.CaptureFixture
    ):
        # ARRANGE: no patterns.md exists, review IS due
        monkeypatch.setattr(per, "_LAST_REVIEW_FILE", tmp_path / "never.txt")
        monkeypatch.setattr(per, "_PATTERNS_CANONICAL", tmp_path / "missing1.md")
        monkeypatch.setattr(per, "_PATTERNS_LEGACY", tmp_path / "missing2.md")
        monkeypatch.setattr("sys.stdin", _make_stdin({}))

        # ACT
        with pytest.raises(SystemExit) as exc:
            per.main()

        # ASSERT: exits silent (nothing to review)
        assert exc.value.code == 0 or exc.value.code is None
        assert capsys.readouterr().out == ""


# ── _resolve_patterns_path ────────────────────────────────────────────────────


class TestResolvePatternsPath:
    def test_prefers_canonical_when_exists(self, tmp_path, monkeypatch):
        canonical = tmp_path / "patterns.md"
        legacy = tmp_path / "_auto" / "patterns.md"
        legacy.parent.mkdir()
        canonical.write_text("# canonical", encoding="utf-8")
        legacy.write_text("# legacy", encoding="utf-8")
        monkeypatch.setattr(per, "_PATTERNS_CANONICAL", canonical)
        monkeypatch.setattr(per, "_PATTERNS_LEGACY", legacy)

        result = per._resolve_patterns_path()
        assert result == canonical

    def test_falls_back_to_legacy(self, tmp_path, monkeypatch):
        canonical = tmp_path / "missing.md"
        legacy = tmp_path / "_auto" / "patterns.md"
        legacy.parent.mkdir()
        legacy.write_text("# legacy", encoding="utf-8")
        monkeypatch.setattr(per, "_PATTERNS_CANONICAL", canonical)
        monkeypatch.setattr(per, "_PATTERNS_LEGACY", legacy)

        result = per._resolve_patterns_path()
        assert result == legacy

    def test_returns_none_when_neither(self, tmp_path, monkeypatch):
        monkeypatch.setattr(per, "_PATTERNS_CANONICAL", tmp_path / "x.md")
        monkeypatch.setattr(per, "_PATTERNS_LEGACY", tmp_path / "y.md")
        assert per._resolve_patterns_path() is None
