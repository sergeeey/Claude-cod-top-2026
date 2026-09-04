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
    _query_wiki_raw_titles,
    _read_wiki_content,
    _render_hot,
    _render_warm,
)
from lib.wiki_types import SearchHit, WikiRef  # noqa: E402


def _kw_hit(rel_path: str, title: str | None = None) -> SearchHit:
    """Build a keyword-sourced SearchHit the way _query_wiki_raw_titles()
    does, for tests that only care about _classify_and_render_wiki()'s
    scoring/tiering logic, not the query-side extraction itself."""
    return SearchHit(ref=WikiRef(rel_path, title or rel_path), score=0.0, source="keyword")


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
        hot, warm = _classify_and_render_wiki([_kw_hit("title-1")], [])
        assert hot == []
        assert warm == []

    def test_candidate_limit_caps_io(self, tmp_path, monkeypatch) -> None:
        """At most TIER_CANDIDATE_LIMIT files are read, regardless of input."""
        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        # Create more files than the limit.
        for i in range(TIER_CANDIDATE_LIMIT + 5):
            (tmp_path / f"entry-{i:02d}.md").write_text(f"alpha content {i}", encoding="utf-8")
        candidates = [_kw_hit(f"entry-{i:02d}") for i in range(TIER_CANDIDATE_LIMIT + 5)]

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

        hot, warm = _classify_and_render_wiki([_kw_hit(title)], ["alpha", "beta", "gamma", "delta"])
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

        hot, warm = _classify_and_render_wiki([_kw_hit(title)], ["alpha", "beta"])
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
            candidates.append(_kw_hit(t))

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
        hot, warm = _classify_and_render_wiki([_kw_hit("2026-05-06_phantom")], ["any"])
        # Either tier is acceptable; the contract is "no exception".
        assert isinstance(hot, list)
        assert isinstance(warm, list)

    def test_title_ne_stem_via_para_alias_reads_real_content(self, tmp_path, monkeypatch) -> None:
        """Regression (memory-retrieval-repair-tz.md PR-2, fixes 0.2): the
        exact `_read_wiki_content("AUC Red Flags") -> None` reproduction.
        Before PR-2, a candidate title with no relation to its filename
        (the normal case for dated slugs) could never be opened for
        HOT-tier rendering -- _read_wiki_content guessed
        WIKI_DIR/{title}.md, which does not exist when title != stem.
        raw_to_wiki.update_wiki_index() now writes real
        [[rel_path|Title]] alias syntax, so the candidate string carries
        the real path. This must now land in HOT with real content, not
        fall back to the recency-only no-content path."""
        from datetime import date

        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        today = date.today().isoformat()
        (tmp_path / "projects").mkdir()
        real_file = tmp_path / "projects" / f"{today}_auc_red_flags.md"
        real_file.write_text(
            "alpha beta gamma delta — full content of the entry " * 5,
            encoding="utf-8",
        )
        # This is exactly what _query_wiki_raw_titles now builds from
        # index.md's [[projects/2026-..._auc_red_flags.md|AUC Red Flags]] --
        # rel_path and display title already split apart into WikiRef,
        # not a "rel_path|Title" compound string (memory-retrieval-repair-
        # tz.md PR-5's list[SearchHit] contract).
        candidate = SearchHit(
            ref=WikiRef(f"projects/{today}_auc_red_flags.md", "AUC Red Flags"),
            score=0.0,
            source="keyword",
        )

        hot, warm = _classify_and_render_wiki([candidate], ["alpha", "beta", "gamma", "delta"])
        assert len(hot) == 1
        assert warm == []
        assert "AUC Red Flags" in hot[0]

    def test_two_files_sharing_title_both_individually_retrievable(
        self, tmp_path, monkeypatch
    ) -> None:
        """Regression (memory-retrieval-repair-tz.md PR-2, fixes 0.2): before
        PR-2, two files sharing an H1 title collided (both were keyed as
        WIKI_DIR/{title}.md by _read_wiki_content's stem-guessing, and
        vector_store keyed both under the same `title` in its index). Each
        file's own rel_path is now its own key -- both must read back their
        own distinct content, not the same one twice, and not None."""
        from datetime import date

        from knowledge_librarian import _read_wiki_content

        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        today = date.today().isoformat()
        (tmp_path / "areas").mkdir()
        (tmp_path / "resources").mkdir()
        (tmp_path / "areas" / f"{today}_a.md").write_text("unique content one", encoding="utf-8")
        (tmp_path / "resources" / f"{today}_b.md").write_text(
            "unique content two", encoding="utf-8"
        )

        content_a = _read_wiki_content(f"areas/{today}_a.md|Duplicate Title".split("|")[0])
        content_b = _read_wiki_content(f"resources/{today}_b.md|Duplicate Title".split("|")[0])

        assert content_a is not None and "unique content one" in content_a
        assert content_b is not None and "unique content two" in content_b
        assert content_a != content_b


class TestSecurityHardening:
    """Pin sec-auditor findings from PR #106 review (H1 + H2 + L3).

    Each test below maps to one finding so a future refactor that breaks
    the defense fails loudly with a named expectation, not as a generic
    test-name collision.
    """

    def test_read_wiki_content_rejects_path_traversal(self, tmp_path, monkeypatch) -> None:
        """H2: stems containing `..` MUST NOT escape WIKI_DIR.

        Verified empirically by sec-auditor — `WIKI_DIR / "../etc/hosts.md"`
        resolves to a real path outside the wiki root. Boundary check via
        resolve() + relative_to MUST close this.
        """
        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        # Plant a file outside the boundary so we'd notice if we read it.
        outside = tmp_path.parent / "secret-outside.md"
        outside.write_text("THIS_MUST_NOT_LEAK", encoding="utf-8")
        try:
            for hostile_stem in (
                "../secret-outside",
                "..\\secret-outside",
                "../../etc/passwd",
                "/etc/passwd",
                "C:\\Windows\\System32\\drivers\\etc\\hosts",
                "subdir/../../../etc/passwd",
            ):
                result = _read_wiki_content(hostile_stem)
                assert result is None, (
                    f"hostile stem {hostile_stem!r} returned content — path traversal not blocked"
                )
        finally:
            outside.unlink(missing_ok=True)

    def test_read_wiki_content_rejects_oversized_file(self, tmp_path, monkeypatch) -> None:
        """L3: files > 256 KB MUST be skipped to avoid OOM at SessionStart.

        WHY: SessionStart reads up to 10 wiki files; a single 1 GB hostile
        entry would freeze the hook. Cap is 256 KB (~50× normal entry).
        """
        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        big = tmp_path / "huge.md"
        big.write_text("x" * 300_000, encoding="utf-8")  # > 256 KB cap
        assert _read_wiki_content("huge") is None

    def test_read_wiki_content_accepts_normal_file(self, tmp_path, monkeypatch) -> None:
        """Sanity: stem with no path separators + size under cap = read OK.

        Pinned alongside the rejection tests so a future overzealous
        validator that rejects ALL stems fails this test loudly.
        """
        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        normal = tmp_path / "normal-entry.md"
        normal.write_text("legitimate content", encoding="utf-8")
        result = _read_wiki_content("normal-entry")
        assert result == "legitimate content"

    def test_missing_explicit_rel_path_does_not_fall_back_to_wrong_para_dir(
        self, tmp_path, monkeypatch
    ) -> None:
        """Regression (P2, Codex review on PR #334): when a candidate names
        an explicit rel_path (e.g. "resources/foo.md") and that exact file
        is missing/stale, the PARA-subdir fallback must NOT guess at a
        same-named file sitting in a DIFFERENT category ("areas/foo.md") --
        that would silently attribute the wrong file's content to the
        original candidate's title, defeating PR-2's whole point of
        rel_path being an unambiguous key. The fallback is only safe for a
        genuine legacy bare stem with no directory component at all."""
        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        (tmp_path / "areas").mkdir()
        # A DIFFERENT, unrelated file that merely happens to share a basename.
        (tmp_path / "areas" / "foo.md").write_text("WRONG unrelated content", encoding="utf-8")
        # resources/foo.md itself does not exist.

        result = _read_wiki_content("resources/foo.md")
        assert result is None

    def test_render_hot_redacts_secrets(self) -> None:
        """H1: HOT-tier inlining MUST scrub secrets before injection.

        Wiki files can contain artifacts of past sessions (.env dumps,
        tracebacks with API keys, copy-pasted curl examples). HOT inlines
        them verbatim into Claude context — a single forgotten secret
        would land in every subsequent session.
        """
        content_with_secret = (
            "Notes from earlier session.\n"
            "export AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE\n"
            "Found this issue in our pipeline."
        )
        out = _render_hot("2026-05-06_session-leak", content_with_secret)
        # Pin contract: literal AWS key MUST NOT survive into HOT line.
        assert "AKIAIOSFODNN7EXAMPLE" not in out
        # Token replacement marker MUST appear so we know redaction ran.
        assert "[REDACTED" in out

    def test_render_hot_passes_through_safe_content(self) -> None:
        """Regression guard: clean content (no secret patterns) MUST be
        rendered unchanged so we don't over-redact.
        """
        clean = "F1=1.000 detected on synthetic test data — flagged."
        out = _render_hot("2026-05-06_clean", clean)
        # The whole clean snippet survives in the output.
        assert "F1=1.000" in out
        assert "synthetic test data" in out


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

    def test_dense_score_substitutes_for_keyword_overlap(self, tmp_path, monkeypatch) -> None:
        """Regression (memory-retrieval-repair-tz.md PR-5, fixes 0.3): a
        dense (semantic) hit has zero literal keyword overlap by
        definition -- it was found by MEANING, not by matching any of the
        `keywords` list. Before this fix, such a hit could score at most
        0.5 (the recency/frequency half alone) and could never cross
        HOT_THRESHOLD=0.65, so a synonym query would always render WARM
        (title-only), never HOT (full snippet) -- defeating the point of
        adding semantic search. `dense_score` must let a strong dense
        match cross HOT_THRESHOLD on its own, the same way strong keyword
        overlap already can."""
        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        from datetime import date

        today = date.today().isoformat()
        title = f"{today}_dense-match"
        (tmp_path / f"{title}.md").write_text("no keyword overlap here at all", encoding="utf-8")

        keywords = ["totally", "unrelated", "keywords"]
        content_lower = "no keyword overlap here at all"

        without_dense = _full_relevance_score(title, content_lower, keywords)
        with_dense = _full_relevance_score(title, content_lower, keywords, dense_score=0.9)

        assert without_dense < HOT_THRESHOLD, (
            "sanity check: with zero keyword overlap and no dense_score, "
            "this entry must NOT already be HOT-eligible on its own"
        )
        assert with_dense >= HOT_THRESHOLD, (
            f"a strong dense_score (0.9) must be able to cross HOT_THRESHOLD "
            f"({HOT_THRESHOLD}) on its own -- got {with_dense:.3f}"
        )


class TestSemanticTopUp:
    """PR-5's actual acceptance criterion: a synonym query with zero
    literal keyword overlap must still surface the right entry."""

    def test_tops_up_when_keyword_results_are_thin(self, tmp_path, monkeypatch) -> None:
        """Regression (memory-retrieval-repair-tz.md PR-5, fixes 0.3,
        acceptance criterion): keyword search alone finds nothing for a
        paraphrased query; semantic_search_paths() must fill the gap."""
        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        # WHY WIKI_INDEX is patched too, not just WIKI_DIR (real bug, caught
        # running this test before this fix): WIKI_INDEX is a module-level
        # constant computed once at import time from the REAL WIKI_DIR --
        # patching WIKI_DIR alone leaves WIKI_INDEX pointing at whatever
        # index.md actually exists on the machine running the tests,
        # leaking real personal wiki content into this test's assertions.
        monkeypatch.setattr("knowledge_librarian.WIKI_INDEX", tmp_path / "index.md")

        fake_hit = SearchHit(
            ref=WikiRef("areas/semantic-only.md", "Semantic Only"), score=0.8, source="dense"
        )

        def fake_semantic_search_paths(query, top_k=3):
            return [fake_hit]

        monkeypatch.setattr(
            "knowledge_librarian.vector_store.semantic_search_paths", fake_semantic_search_paths
        )

        # No index.md, no files matching these keywords -> keyword path
        # returns nothing on its own.
        result = _query_wiki_raw_titles(["zzzznomatch"], top_n=10, query="a paraphrased query")

        assert len(result) == 1
        assert result[0].ref.rel_path == "areas/semantic-only.md"
        assert result[0].source == "dense"

    def test_still_tops_up_when_keyword_results_already_fill_top_n(
        self, tmp_path, monkeypatch
    ) -> None:
        """Regression (memory-retrieval-repair-tz.md PR-5, design
        correction made DURING this PR's own §5.3 gate measurement, not
        before it -- see _query_wiki_raw_titles's own WHY comment for the
        full reproduction): an earlier version of this function only
        consulted semantic search when `len(result) < top_n`, mirroring
        the deleted _query_wiki()'s threshold. Measuring against the
        frozen benchmark showed this defeats the point whenever GENERIC
        query words spuriously fill top_n with unrelated keyword matches
        (index.md keyword matching runs against condensed title lines, not
        full content) -- once full, semantic search never got a chance to
        contribute even one candidate. Fixed: semantic search is now
        ALWAYS consulted and merged in (deduplicated by rel_path), letting
        scoring decide the final ranking instead of a pre-filter deciding
        semantic search is unneeded."""
        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        monkeypatch.setattr("knowledge_librarian.WIKI_INDEX", tmp_path / "index.md")
        (tmp_path / "match.md").write_text("alpha content", encoding="utf-8")

        calls = []

        def fake_semantic_search_paths(query, top_k=3):
            calls.append((query, top_k))
            return [SearchHit(ref=WikiRef("should-appear-too.md", "X"), score=0.9, source="dense")]

        monkeypatch.setattr(
            "knowledge_librarian.vector_store.semantic_search_paths", fake_semantic_search_paths
        )

        result = _query_wiki_raw_titles(["alpha"], top_n=1, query="alpha")
        rel_paths = {hit.ref.rel_path for hit in result}

        assert calls, (
            "semantic_search_paths must be called even when keyword results already fill top_n"
        )
        assert "match.md" in rel_paths, "the keyword hit must still be present"
        assert "should-appear-too.md" in rel_paths, (
            "the dense hit must be merged in too, not discarded because keyword "
            "results already reached top_n"
        )

    def test_semantic_topup_deduplicates_by_rel_path(self, tmp_path, monkeypatch) -> None:
        """A dense hit for a rel_path the keyword path already found must
        not be added a second time."""
        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        monkeypatch.setattr("knowledge_librarian.WIKI_INDEX", tmp_path / "index.md")
        (tmp_path / "match.md").write_text("alpha content", encoding="utf-8")

        def fake_semantic_search_paths(query, top_k=3):
            return [SearchHit(ref=WikiRef("match.md", "Match"), score=0.9, source="dense")]

        monkeypatch.setattr(
            "knowledge_librarian.vector_store.semantic_search_paths", fake_semantic_search_paths
        )

        result = _query_wiki_raw_titles(["alpha"], top_n=10, query="alpha")

        assert len(result) == 1
        assert result[0].ref.rel_path == "match.md"
        # WHY source stays "keyword" (first-writer-wins by construction):
        # the keyword path populates `result` before the semantic top-up
        # loop runs, and the dedup check skips a rel_path already present
        # -- the keyword hit is never overwritten by the dense one.
        assert result[0].source == "keyword"

    def test_fallback_scan_excludes_auto_capture_dir(self, tmp_path, monkeypatch) -> None:
        """WHY: the keyword-path fallback (no index.md, or no match in it)
        full-scans WIKI_DIR directly -- it must skip auto_capture/ the same
        way it already skips daily/, or auto_capture.py's commit-capture
        notes leak back into candidates even after being routed out of the
        normal PARA dirs (owner request 2026-09-04, pearl_registry)."""
        monkeypatch.setattr("knowledge_librarian.WIKI_DIR", tmp_path)
        monkeypatch.setattr("knowledge_librarian.WIKI_INDEX", tmp_path / "index.md")
        (tmp_path / "auto_capture").mkdir()
        (tmp_path / "auto_capture" / "note.md").write_text(
            "alpha content #auto-capture", encoding="utf-8"
        )
        (tmp_path / "real.md").write_text("alpha content", encoding="utf-8")

        monkeypatch.setattr(
            "knowledge_librarian.vector_store.semantic_search_paths", lambda query, top_k=3: []
        )

        result = _query_wiki_raw_titles(["alpha"], top_n=10, query="")

        rel_paths = {hit.ref.rel_path for hit in result}
        assert rel_paths == {"real.md"}
