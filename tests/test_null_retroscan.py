"""Tests for null_retroscan.py — immediate retroscan on new NULL results."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from null_retroscan import (
    _claim_tokens,
    _has_promote,
    _identifiers,
    _is_null_index,
    _is_strong,
    _new_slugs,
    _overlap_score,
    _scan_active_promotes,
    _scan_deliverables,
    _slug_from_row,
    _tex_sections,
    _tokenize,
)

# ── path / parsing helpers ────────────────────────────────────────────────────


class TestIsNullIndex:
    def test_valid(self):
        assert _is_null_index("null_results/INDEX.md")

    def test_nested(self):
        assert _is_null_index("D:/repo/null_results/INDEX.md")

    def test_wrong_dir(self):
        assert not _is_null_index("experiments/INDEX.md")

    def test_wrong_name(self):
        assert not _is_null_index("null_results/notes.md")


class TestTokenize:
    def test_drops_short_and_stopwords(self):
        toks = _tokenize("the spinor index argument via test")
        assert "spinor" in toks
        assert "argument" in toks
        assert "the" not in toks  # short
        assert "via" not in toks  # stopword
        assert "test" not in toks  # stopword

    def test_russian(self):
        toks = _tokenize("спектральный лапласиан")
        assert "спектральный" in toks

    def test_includes_identifiers(self):
        # Regression: the alpha-only pass alone would drop the ratio entirely.
        toks = _tokenize("79-17-rg-boundary-condition")
        assert "num:7917" in toks
        assert "boundary" in toks
        assert "condition" in toks


class TestSlugFromRow:
    def test_extracts_slug(self):
        assert (
            _slug_from_row("| g85b | 2026-06 | spectral-saddle | REJECT | x |") == "spectral-saddle"
        )

    def test_skips_separator(self):
        assert _slug_from_row("|---|---|---|---|---|") is None

    def test_skips_header(self):
        assert _slug_from_row("| id | date | slug | verdict | why |") is None

    def test_non_row(self):
        assert _slug_from_row("just text") is None


class TestNewSlugs:
    def test_prefers_new_string(self):
        new = "| g90 | 2026-06 | warp-factor-null | REJECT | exhausted |"
        slugs = _new_slugs("", new)
        assert slugs == ["warp-factor-null"]

    def test_fallback_last_row_on_write(self):
        content = (
            "| id | date | slug | verdict | why |\n"
            "|---|---|---|---|---|\n"
            "| g85 | 2026-06 | old-null | REJECT | a |\n"
            "| g86 | 2026-06 | newest-null | REJECT | b |\n"
        )
        slugs = _new_slugs(content, "")
        assert slugs == ["newest-null"]


class TestHasPromote:
    def test_detects(self):
        assert _has_promote("- [x] PROMOTE — holds")

    def test_ignores_unchecked(self):
        assert not _has_promote("- [ ] PROMOTE")


# ── identifier extraction (2026-08-04 extension) ───────────────────────────────


class TestIdentifiers:
    def test_letter_digit_mixes(self):
        # Real research-identifier shapes named in the module docstring's incident.
        toks = _identifiers("Eq32 appears near A1 and N5, also H1e and R011, plus 4d")
        assert toks == {"eq32", "a1", "n5", "h1e", "r011", "4d"}

    def test_colon_separated_ratio_normalises(self):
        assert _identifiers("the ratio 7:9:17 is central") == {"num:7917"}

    def test_dash_separated_ratio_same_key_as_colon(self):
        # Same subject, different notation (slug vs prose) must collide on one token.
        assert _identifiers("slug uses 79-17 style") == {"num:7917"}

    def test_latex_escaped_ratio_same_key(self):
        assert _identifiers(r"\$7\!:\!9\!:\!17\$") == {"num:7917"}

    def test_bare_number_never_becomes_a_token(self):
        # No separator → not an identifier at all (avoids matching every date/count).
        assert _identifiers("recorded on 20260804") == set()

    def test_short_numeric_range_dropped_by_digit_floor(self):
        # Fewer than 4 digits → incidental range (a page span, a small count),
        # not a subject identifier.
        assert _identifiers("see pages 1-2") == set()

    def test_stopword_like_identifier_excluded(self):
        # An identifier token must still pass the stopword filter.
        assert "test" not in _identifiers("this test4 run")


class TestIsStrong:
    def test_letter_digit_identifier_is_strong(self):
        assert _is_strong("eq32") is True

    def test_normalised_ratio_is_strong(self):
        assert _is_strong("num:7917") is True

    def test_calendar_shaped_number_is_not_strong(self):
        # A shared date says nothing about a shared subject.
        assert _is_strong("num:20260804") is False

    def test_plain_word_is_not_strong(self):
        assert _is_strong("boundary") is False


class TestOverlapScore:
    def test_weights_identifiers_double(self):
        # One strong (2) + one plain (1) = 3, not 2 — this is the whole point of
        # the weighted score over a bare len(overlap) count.
        assert _overlap_score({"eq32", "boundary"}) == 3

    def test_two_plain_words_still_meets_old_threshold(self):
        # Backward compatibility: two ordinary shared words must still score >= 2,
        # matching the pre-extension behaviour that used len(overlap) directly.
        assert _overlap_score({"boundary", "condition"}) == 2

    def test_empty_overlap_scores_zero(self):
        assert _overlap_score(set()) == 0


# ── .tex section splitting ──────────────────────────────────────────────────────


class TestTexSections:
    def test_splits_on_section_markers(self):
        text = r"Title stuff \section{Intro}body1\section{Results}body2"
        sections = _tex_sections(text)
        assert sections[0] == ("(title/abstract)", "Title stuff ")
        assert sections[1][0] == "Intro"
        assert "body1" in sections[1][1]
        assert sections[2][0] == "Results"
        assert "body2" in sections[2][1]

    def test_subsection_folded_into_section(self):
        text = r"\section{A}one\subsection{B}two"
        sections = _tex_sections(text)
        titles = [t for t, _ in sections]
        assert "B" in titles  # subsection normalised to a section boundary

    def test_unsectioned_file_returns_whole_text(self):
        assert _tex_sections("no markers here") == [("", "no markers here")]

    def test_preserves_pre_first_section_chunk(self):
        # Regression: this chunk holds title/abstract — the most load-bearing
        # claims in a paper — dropping it was a real miss caught in testing.
        text = r"Abstract: warp factor result. \section{Intro}body"
        sections = _tex_sections(text)
        assert sections[0][0] == "(title/abstract)"
        assert "warp factor result" in sections[0][1]


# ── claim token extraction ────────────────────────────────────────────────────


class TestClaimTokens:
    def test_reads_claim_md(self, tmp_path):
        (tmp_path / "claim.md").write_text(
            "## Claim\nThe warp factor selects lambda uniquely.\n", encoding="utf-8"
        )
        toks = _claim_tokens(tmp_path)
        assert "warp" in toks
        assert "factor" in toks
        assert "lambda" in toks

    def test_empty_when_nothing(self, tmp_path):
        assert _claim_tokens(tmp_path) == set()


# ── core scan: experiments/ ──────────────────────────────────────────────────


class TestScanActivePromotes:
    def _make_exp(self, root, exp_id, claim_text, verdict):
        d = root / "experiments" / exp_id
        d.mkdir(parents=True)
        (d / "claim.md").write_text(claim_text, encoding="utf-8")
        (d / "decision.md").write_text(f"- [x] {verdict}\n", encoding="utf-8")

    def test_flags_overlapping_promote(self, tmp_path):
        self._make_exp(tmp_path, "g70-warp", "warp factor selects lambda", "PROMOTE")
        matches = _scan_active_promotes(tmp_path, _tokenize("warp-factor-null"))
        assert len(matches) == 1
        assert matches[0][0] == "g70-warp"
        assert "warp" in matches[0][1]

    def test_ignores_rejected_claim(self, tmp_path):
        self._make_exp(tmp_path, "g71-warp", "warp factor selects lambda", "REJECT")
        matches = _scan_active_promotes(tmp_path, _tokenize("warp-factor-null"))
        assert matches == []

    def test_ignores_unrelated_promote(self, tmp_path):
        self._make_exp(tmp_path, "g72-other", "completely different topic here", "PROMOTE")
        matches = _scan_active_promotes(tmp_path, _tokenize("warp-factor-null"))
        assert matches == []

    def test_requires_two_token_overlap(self, tmp_path):
        # only "warp" overlaps (1 token, score 1) → below threshold
        self._make_exp(tmp_path, "g73-warp", "warp drive engineering notes", "PROMOTE")
        matches = _scan_active_promotes(tmp_path, _tokenize("warp-factor-null"))
        assert matches == []

    def test_no_experiments_dir(self, tmp_path):
        assert _scan_active_promotes(tmp_path, {"warp", "factor"}) == []

    def test_single_identifier_overlap_meets_threshold_alone(self, tmp_path):
        # A single strong identifier scores 2 by itself (weighted double) — this
        # is the extension's whole point: an id-only overlap must still fire.
        self._make_exp(tmp_path, "g74-eq32", "see eq32 for the boundary derivation", "PROMOTE")
        matches = _scan_active_promotes(tmp_path, _identifiers("new null about eq32"))
        assert len(matches) == 1
        assert matches[0][0] == "g74-eq32"


# ── core scan: paper/manuscript deliverables (2026-08-04 extension) ────────────


class TestScanDeliverables:
    def test_no_deliverable_dir_is_silent(self, tmp_path):
        # Self-scoping: a project with no paper/ or manuscript/ sees no behaviour
        # change at all.
        assert _scan_deliverables(tmp_path, _tokenize("warp-factor-null")) == []

    def test_flags_overlapping_tex_section(self, tmp_path):
        paper = tmp_path / "paper"
        paper.mkdir()
        (paper / "main.tex").write_text(
            r"Title \section{Results}The warp factor selects lambda uniquely.",
            encoding="utf-8",
        )
        matches = _scan_deliverables(tmp_path, _tokenize("warp-factor-null"))
        assert len(matches) == 1
        where, overlap = matches[0]
        assert "main.tex" in where
        assert "Results" in where
        assert "warp" in overlap

    def test_flags_title_abstract_chunk(self, tmp_path):
        # Regression: the pre-first-section chunk (title/abstract) must be scanned,
        # not silently dropped — it carries the paper's headline claims.
        paper = tmp_path / "paper"
        paper.mkdir()
        (paper / "main.tex").write_text(
            r"Abstract: the warp factor result. \section{Intro}unrelated text here",
            encoding="utf-8",
        )
        matches = _scan_deliverables(tmp_path, _tokenize("warp-factor-null"))
        assert len(matches) == 1
        where, _ = matches[0]
        assert "title/abstract" in where

    def test_flags_overlapping_md_deliverable(self, tmp_path):
        manuscript = tmp_path / "manuscript"
        manuscript.mkdir()
        (manuscript / "draft.md").write_text(
            "The warp factor selects lambda across the whole draft.", encoding="utf-8"
        )
        matches = _scan_deliverables(tmp_path, _tokenize("warp-factor-null"))
        assert len(matches) == 1
        assert matches[0][0] == "manuscript/draft.md"

    def test_ignores_non_deliverable_suffix(self, tmp_path):
        paper = tmp_path / "paper"
        paper.mkdir()
        (paper / "notes.txt").write_text("warp factor selects lambda", encoding="utf-8")
        assert _scan_deliverables(tmp_path, _tokenize("warp-factor-null")) == []

    def test_ignores_unrelated_tex(self, tmp_path):
        paper = tmp_path / "paper"
        paper.mkdir()
        (paper / "main.tex").write_text(
            r"\section{Unrelated}completely different subject matter",
            encoding="utf-8",
        )
        assert _scan_deliverables(tmp_path, _tokenize("warp-factor-null")) == []
