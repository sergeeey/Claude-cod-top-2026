"""Tests for null_results_pre_check.py hook."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from null_results_pre_check import (
    _find_matches,
    _is_triggered,
    _parse_null_results,
    _tokenize,
)


class TestIsTriggerred:
    def test_triggered_by_hypothesis(self):
        assert _is_triggered("давай проверим гипотезу о скорости")

    def test_triggered_by_experiment(self):
        assert _is_triggered("Start a new experiment on caching")

    def test_triggered_by_claim(self):
        assert _is_triggered("New claim: this approach reduces latency")

    def test_not_triggered_by_generic(self):
        assert not _is_triggered("fix the bug in auth.py")

    def test_not_triggered_by_empty(self):
        assert not _is_triggered("")

    def test_triggered_by_english_check(self):
        assert _is_triggered("I want to test if the router handles edge cases")


class TestTokenize:
    def test_basic_split(self):
        tokens = _tokenize("fast-prompt-injection-detection")
        assert "fast" in tokens
        assert "prompt" in tokens
        assert "injection" in tokens
        assert "detection" in tokens

    def test_filters_short_tokens(self):
        tokens = _tokenize("a-to-be-of-is-in")
        # All tokens shorter than MIN_TOKEN_LEN=4 should be excluded
        assert not tokens

    def test_handles_cyrillic(self):
        tokens = _tokenize("проверка гипотезы")
        assert "проверка" in tokens or "гипотезы" in tokens


class TestParseNullResults:
    def test_parses_table(self, tmp_path):
        index = tmp_path / "null_results" / "INDEX.md"
        index.parent.mkdir(parents=True)
        index.write_text(
            "| ID | Date | Slug | Verdict | Why |\n"
            "|---|---|---|---|---|\n"
            "| 20260101 | 2026-01-01 | prompt-injection-detection | REJECT | Low precision on real data |\n"
            "| 20260102 | 2026-01-02 | cache-latency-test | REJECT | No measurable delta |\n",
            encoding="utf-8",
        )
        entries = _parse_null_results(index)
        assert len(entries) == 2
        assert entries[0]["slug"] == "prompt-injection-detection"
        assert entries[0]["verdict"] == "REJECT"
        assert entries[1]["slug"] == "cache-latency-test"

    def test_skips_header_and_separator(self, tmp_path):
        index = tmp_path / "INDEX.md"
        index.write_text(
            "# null_results\n\n"
            "| ID | Slug | Verdict | Why |\n"
            "|---|---|---|---|\n"
            "| 001 | real-entry | REJECT | bad |\n",
            encoding="utf-8",
        )
        entries = _parse_null_results(index)
        # Only the real-entry row
        assert any(e["id"] == "001" for e in entries)

    def test_handles_missing_file(self, tmp_path):
        entries = _parse_null_results(tmp_path / "missing.md")
        assert entries == []


class TestFindMatches:
    def make_entries(self):
        return [
            {"id": "001", "slug": "prompt-injection-detection", "verdict": "REJECT", "why": "bad"},
            {"id": "002", "slug": "cache-latency-benchmark", "verdict": "REJECT", "why": "delta=0"},
            {"id": "003", "slug": "router-fallback-logic", "verdict": "ARCHIVE", "why": "deferred"},
        ]

    def test_matches_on_slug_overlap(self):
        entries = self.make_entries()
        prompt = "Let me try a new experiment on prompt injection detection"
        matches = _find_matches(prompt, entries)
        assert len(matches) == 1
        assert matches[0]["id"] == "001"
        assert "prompt" in matches[0]["_overlap"] or "injection" in matches[0]["_overlap"]

    def test_no_match_when_only_one_token(self):
        entries = self.make_entries()
        # Only "cache" overlaps — below MATCH_THRESHOLD=2
        prompt = "I want to test cache performance in our system"
        matches = _find_matches(prompt, entries)
        # "cache" is only one token — no match
        assert not any(m["id"] == "002" for m in matches)

    def test_no_match_on_unrelated_prompt(self):
        entries = self.make_entries()
        prompt = "please refactor the logging module"
        matches = _find_matches(prompt, entries)
        assert matches == []

    def test_match_returns_overlap_field(self):
        entries = self.make_entries()
        prompt = "try prompt injection detection again"
        matches = _find_matches(prompt, entries)
        assert matches
        assert "_overlap" in matches[0]
        assert len(matches[0]["_overlap"]) >= 2  # noqa: PLR2004
