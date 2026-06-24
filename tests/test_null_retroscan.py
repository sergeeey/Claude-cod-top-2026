"""Tests for null_retroscan.py — immediate retroscan on new NULL results."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from null_retroscan import (
    _claim_tokens,
    _has_promote,
    _is_null_index,
    _new_slugs,
    _scan_active_promotes,
    _slug_from_row,
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


# ── core scan ─────────────────────────────────────────────────────────────────


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
        # only "warp" overlaps (1 token) → below threshold
        self._make_exp(tmp_path, "g73-warp", "warp drive engineering notes", "PROMOTE")
        matches = _scan_active_promotes(tmp_path, _tokenize("warp-factor-null"))
        assert matches == []

    def test_no_experiments_dir(self, tmp_path):
        assert _scan_active_promotes(tmp_path, {"warp", "factor"}) == []
