"""Tests for null_results_pre_check.py hook."""

import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from null_results_pre_check import (
    _find_matches,
    _find_null_results_index,
    _is_triggered,
    _parse_null_results,
    _tokenize,
    main,
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

    def test_skips_row_with_too_few_columns(self, tmp_path):
        index = tmp_path / "INDEX.md"
        index.write_text(
            "| ID | Slug | Verdict | Why |\n"
            "|---|---|---|---|\n"
            "| only-two |\n"
            "| 001 | real-entry | REJECT | bad |\n",
            encoding="utf-8",
        )
        entries = _parse_null_results(index)
        assert len(entries) == 1
        assert entries[0]["id"] == "001"


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
        assert len(matches[0]["_overlap"]) >= 2


# ── _find_null_results_index() and main() ───────────────────────────────────
#
# WHY these classes exist: the tests above cover every pure helper
# individually but never exercise the hook entrypoint that wires them
# together, nor the upward directory search.


def _stdin(monkeypatch, payload):
    text = (
        "" if payload is None else json.dumps(payload) if not isinstance(payload, str) else payload
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))


class TestFindNullResultsIndex:
    def test_finds_index_in_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        index = tmp_path / "null_results" / "INDEX.md"
        index.parent.mkdir(parents=True)
        index.write_text("| ID |\n", encoding="utf-8")
        assert _find_null_results_index() == index

    def test_finds_index_in_parent_directory(self, tmp_path, monkeypatch):
        index = tmp_path / "null_results" / "INDEX.md"
        index.parent.mkdir(parents=True)
        index.write_text("| ID |\n", encoding="utf-8")
        nested = tmp_path / "sub" / "deeper"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        assert _find_null_results_index() == index

    def test_returns_none_when_absent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert _find_null_results_index() is None


class TestMain:
    def test_recursion_guard_skips_when_invoked_by_subagent(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CLAUDE_INVOKED_BY", "some-agent")
        monkeypatch.chdir(tmp_path)
        _stdin(monkeypatch, {"prompt": "let's run a new experiment"})

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_invalid_json_stdin_exits_quietly(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        monkeypatch.chdir(tmp_path)
        _stdin(monkeypatch, "not json")

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_empty_prompt_exits_quietly(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        monkeypatch.chdir(tmp_path)
        _stdin(monkeypatch, {"prompt": "   "})

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_non_string_prompt_exits_quietly(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        monkeypatch.chdir(tmp_path)
        _stdin(monkeypatch, {"prompt": 42})

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_not_triggered_prompt_exits_quietly(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        monkeypatch.chdir(tmp_path)
        _stdin(monkeypatch, {"prompt": "please fix the typo in the README"})

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_triggered_but_no_index_found_exits_quietly(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        monkeypatch.chdir(tmp_path)  # no null_results/ anywhere upward in tmp_path
        _stdin(monkeypatch, {"prompt": "I want to test a new hypothesis about caching"})

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_triggered_index_found_but_empty_exits_quietly(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        index = tmp_path / "null_results" / "INDEX.md"
        index.parent.mkdir(parents=True)
        index.write_text("# empty, no table rows\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        _stdin(monkeypatch, {"prompt": "I want to test a new hypothesis about caching"})

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_triggered_entries_present_but_no_overlap_exits_quietly(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        index = tmp_path / "null_results" / "INDEX.md"
        index.parent.mkdir(parents=True)
        index.write_text(
            "| ID | Date | Slug | Verdict | Why |\n"
            "|---|---|---|---|---|\n"
            "| 001 | 2026-01-01 | totally-unrelated-topic | REJECT | n/a |\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        _stdin(monkeypatch, {"prompt": "I want to test a new hypothesis about database caching"})

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_triggered_with_match_prints_warning_and_falls_through(
        self, monkeypatch, tmp_path, capsys
    ):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        index = tmp_path / "null_results" / "INDEX.md"
        index.parent.mkdir(parents=True)
        index.write_text(
            "| ID | Date | Slug | Verdict | Why |\n"
            "|---|---|---|---|---|\n"
            "| 20260101 | 2026-01-01 | prompt-injection-detection | REJECT | Low precision |\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        _stdin(
            monkeypatch,
            {"prompt": "let me try a new experiment on prompt injection detection"},
        )

        main()  # WHY no pytest.raises: the match branch falls off the end, no sys.exit

        out = capsys.readouterr().out
        assert "null-results-pre-check" in out
        payload = json.loads(out)
        assert payload["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert "20260101" in payload["hookSpecificOutput"]["additionalContext"]
