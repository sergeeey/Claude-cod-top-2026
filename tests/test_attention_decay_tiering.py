"""Unit tests for HOT/WARM/COLD attention decay layer in knowledge_librarian.py.

WHY: this is the layer that decides what knowledge enters Claude's context
at SessionStart. If tier classification breaks (over-promoting irrelevant
entries to HOT, or quietly demoting relevant ones to COLD) the agent loses
exactly the pre-task context this hook was built to provide. Pinning the
contract here.

Threshold rationale:
- HOT >=0.65: at least ~50% keyword overlap on a recent or frequent entry
- WARM 0.35..0.65: partial match or stale frequency-only match
- COLD <0.35: drop entirely
"""

from __future__ import annotations

import sys
from pathlib import Path

# WHY: hooks/ isn't a package, so import via sys.path manipulation
HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from knowledge_librarian import (  # noqa: E402
    HOT_BUDGET_CHARS,
    HOT_THRESHOLD,
    TIER_CANDIDATE_LIMIT,
    WARM_THRESHOLD,
    _classify_and_render_wiki,
    _classify_tier,
    _full_relevance_score,
    _keyword_overlap_score,
    _render_hot,
    _render_warm,
)


class TestKeywordOverlapScore:
    def test_no_keywords_returns_zero(self) -> None:
        assert _keyword_overlap_score("any content", []) == 0.0

    def test_full_overlap(self) -> None:
        score = _keyword_overlap_score("alpha beta gamma", ["alpha", "beta", "gamma"])
        assert score == 1.0

    def test_partial_overlap(self) -> None:
        # 2 of 4 keywords present
        score = _keyword_overlap_score("alpha beta", ["alpha", "beta", "gamma", "delta"])
        assert score == 0.5

    def test_zero_overlap(self) -> None:
        score = _keyword_overlap_score("foo bar", ["alpha", "beta"])
        assert score == 0.0

    def test_substring_match(self) -> None:
        # "validate" contains "valid" — substring counts as match (cheap, OK).
        # WHY: documenting current behavior. If we tighten to word-boundary later,
        # this test fails on purpose to flag the contract change.
        score = _keyword_overlap_score("validation theater", ["valid"])
        assert score == 1.0


class TestClassifyTier:
    def test_hot_at_threshold(self) -> None:
        assert _classify_tier(HOT_THRESHOLD) == "HOT"
        assert _classify_tier(HOT_THRESHOLD + 0.01) == "HOT"

    def test_warm_band(self) -> None:
        assert _classify_tier(WARM_THRESHOLD) == "WARM"
        assert _classify_tier(0.5) == "WARM"
        assert _classify_tier(HOT_THRESHOLD - 0.01) == "WARM"

    def test_cold_below_warm(self) -> None:
        assert _classify_tier(WARM_THRESHOLD - 0.01) == "COLD"
        assert _classify_tier(0.0) == "COLD"

    def test_thresholds_ordered(self) -> None:
        # WHY: pin the invariant — HOT must always be stricter than WARM.
        assert HOT_THRESHOLD > WARM_THRESHOLD


class TestRenderers:
    def test_hot_includes_title_and_snippet(self) -> None:
        out = _render_hot("2026-05-06_test", "First line of content. Second line.")
        assert "2026-05-06_test" in out
        assert "First line" in out
        # Single-line for clean injection
        assert "\n" not in out

    def test_hot_truncates_long_content(self) -> None:
        long = "x" * 5000
        out = _render_hot("title", long)
        # Truncated + ellipsis marker
        assert "…" in out
        # Length under 400 chars (300 max + title + emoji + brackets)
        assert len(out) < 400

    def test_warm_is_minimal(self) -> None:
        out = _render_warm("2026-05-06_test")
        assert "[[2026-05-06_test]]" in out
        # Compact: no snippet, no extra text after title
        assert len(out) < 60


class TestClassifyAndRenderWiki:
    """Integration of scoring + tiering + budget enforcement."""

    def test_empty_input(self) -> None:
        hot, warm = _classify_and_render_wiki([], ["any"])
        assert hot == []
        assert warm == []

    def test_no_keywords(self) -> None:
        hot, warm = _classify_and_render_wiki(["title-1"], [])
        assert hot == []
        assert warm == []

    def test_candidate_limit_caps_io(self, tmp_path, monkeypatch) -> None:
        """At most TIER_CANDIDATE_LIMIT files are read, regardless of input."""
        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        # Create more files than the limit.
        for i in range(TIER_CANDIDATE_LIMIT + 5):
            (tmp_path / f"entry-{i:02d}.md").write_text(f"alpha content {i}", encoding="utf-8")
        candidates = [f"entry-{i:02d}" for i in range(TIER_CANDIDATE_LIMIT + 5)]

        hot, warm = _classify_and_render_wiki(candidates, ["alpha"])
        # Total tiered output (HOT + WARM) MUST NOT exceed the candidate limit
        # — otherwise we read more files than promised in the docstring.
        assert len(hot) + len(warm) <= TIER_CANDIDATE_LIMIT

    def test_high_overlap_promotes_to_hot(self, tmp_path, monkeypatch) -> None:
        from datetime import date

        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        # Recent date in stem to maximize recency component.
        today = date.today().isoformat()
        title = f"{today}_perfect-match"
        (tmp_path / f"{title}.md").write_text(
            "alpha beta gamma delta — full content of the entry " * 5,
            encoding="utf-8",
        )

        hot, warm = _classify_and_render_wiki([title], ["alpha", "beta", "gamma", "delta"])
        # 4/4 keyword overlap + high recency → must land in HOT, not WARM.
        assert len(hot) == 1
        assert "🔥" in hot[0] or "[[" in hot[0]
        assert warm == []

    def test_low_overlap_demoted_to_warm_not_cold(self, tmp_path, monkeypatch) -> None:
        """Candidates that already passed the keyword filter at query stage
        land at minimum in WARM — not COLD. Reason: _query_wiki_raw_titles
        is the COLD-filter; orchestration only chooses HOT vs WARM among
        accepted candidates. Pin the design contract here so a future
        refactor doesn't reintroduce double-filtering."""
        from datetime import date, timedelta

        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        old_date = (date.today() - timedelta(days=365)).isoformat()
        title = f"{old_date}_weakly-related"
        (tmp_path / f"{title}.md").write_text("xxxx yyyy zzzz", encoding="utf-8")

        hot, warm = _classify_and_render_wiki([title], ["alpha", "beta"])
        # Already a candidate → at least WARM. Never silently dropped.
        assert hot == []
        assert len(warm) == 1
        assert title in warm[0]

    def test_hot_budget_overflow_demotes(self, tmp_path, monkeypatch) -> None:
        """Once HOT_BUDGET_CHARS is consumed, additional HOT-eligible entries
        must demote to WARM rather than blowing past budget silently."""
        from datetime import date

        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        today = date.today().isoformat()
        # Each entry has full keyword overlap and is recent — all eligible for HOT.
        # Make content long enough that each HOT line approaches 300 chars.
        long_content = "alpha beta " * 80  # ~880 chars
        candidates = []
        for i in range(10):
            t = f"{today}_match-{i:02d}"
            (tmp_path / f"{t}.md").write_text(long_content, encoding="utf-8")
            candidates.append(t)

        hot, warm = _classify_and_render_wiki(candidates, ["alpha", "beta"])
        # Sum of HOT line lengths must respect the budget.
        hot_chars = sum(len(line) for line in hot)
        assert hot_chars <= HOT_BUDGET_CHARS
        # Overflow eligible entries should appear in WARM (not silently dropped).
        assert len(hot) + len(warm) >= 5  # at least 5 of 10 surfaced somehow

    def test_missing_file_does_not_crash(self, tmp_path, monkeypatch) -> None:
        """Title without backing file: scored on recency only, never raises."""
        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        # No file written.
        hot, warm = _classify_and_render_wiki(["2026-05-06_phantom"], ["any"])
        # Either tier is acceptable; the contract is "no exception".
        assert isinstance(hot, list)
        assert isinstance(warm, list)


class TestFullRelevanceScore:
    def test_keyword_dominates(self, tmp_path, monkeypatch) -> None:
        """An exact-keyword stale entry should out-score a no-keyword fresh entry.

        WHY: the documented goal of adding keyword overlap was exactly this —
        a 1-year-old entry that matches 5/5 keywords is more useful than a
        today's entry that matches 0.
        """
        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        from datetime import date, timedelta

        old_match = f"{(date.today() - timedelta(days=365)).isoformat()}_old"
        new_nomatch = f"{date.today().isoformat()}_new"
        (tmp_path / f"{old_match}.md").write_text("alpha beta gamma", encoding="utf-8")
        (tmp_path / f"{new_nomatch}.md").write_text("nothing relevant here", encoding="utf-8")

        kws = ["alpha", "beta", "gamma"]
        old_score = _full_relevance_score(old_match, "alpha beta gamma", kws)
        new_score = _full_relevance_score(new_nomatch, "nothing relevant here", kws)

        assert old_score > new_score, (
            f"old keyword-match ({old_score:.2f}) should beat new no-match ({new_score:.2f})"
        )
