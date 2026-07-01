"""Tests for experiment_insight.py — FL decision.md → null_results + raw note.

WHY: the hook runs on every Write/Edit PostToolUse event and must:
- silently skip non-decision.md files
- silently skip PROMOTE/REPEAT verdicts
- update null_results/INDEX.md for REJECT/ARCHIVE
- create a structured raw note for Obsidian import
Tests are fully isolated via tmp_path and monkeypatching.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

DECISION_REJECT = """\
# Decision

**Experiment ID:** `20260612-llm-router-v1`
**Date:** 2026-06-12

## Verdict

**[ ] PROMOTE**
**[ ] REPEAT**
**[x] REJECT** — claim falsified, do not proceed
**[ ] ARCHIVE**

## Evidence Summary

| Gate | Status | Notes |
|---|---|---|
| Positive control | FAIL | |

## Reasoning

LLM router did not generalise beyond training distribution.
F1 dropped from 0.89 to 0.31 on real data.
Root cause: category leakage from source annotation, not biology.

---

*Signed: claude, 2026-06-12*
"""

DECISION_ARCHIVE = """\
# Decision

**Experiment ID:** `20260610-brier-accumulation`
**Date:** 2026-06-10

## Verdict

**[ ] PROMOTE**
**[ ] REPEAT**
**[ ] REJECT**
**[x] ARCHIVE** — valid but deprioritized

## Reasoning

Sequential Brier accumulation is correct but sequential only.
Deprioritised until parallel scenario support is needed.
"""

DECISION_PROMOTE = """\
# Decision

**Experiment ID:** `20260601-evidence-guard`
**Date:** 2026-06-01

## Verdict

**[x] PROMOTE**

## Reasoning

Evidence guard blocked 3 synthetic overclaims in CI. Promotes to main.
"""

DECISION_NO_VERDICT = """\
# Decision

**Experiment ID:** `20260601-incomplete`
**Date:** 2026-06-01

## Verdict

No checkboxes filled yet.
"""

NULL_INDEX_TEMPLATE = """\
# Null Results Index

| ID | Date | Claim Slug | Verdict | Why (10 words max) |
|---|---|---|---|---|
| — | — | — | — | No entries yet |

## How to Add an Entry
"""

NULL_INDEX_WITH_ROW = """\
# Null Results Index

| ID | Date | Claim Slug | Verdict | Why (10 words max) |
|---|---|---|---|---|
| 20260501-old-experiment | 2026-05-01 | old-experiment | REJECT | Did not work at all |

## How to Add an Entry
"""


def _load(monkeypatch: pytest.MonkeyPatch, raw_dir: Path, index_path: Path):
    """Reload experiment_insight with patched paths."""
    monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
    monkeypatch.setenv("CLAUDE_DRY_RUN", "0")

    import experiment_insight

    importlib.reload(experiment_insight)
    experiment_insight.RAW_DIR = raw_dir
    experiment_insight.NULL_RESULTS_INDEX = index_path
    experiment_insight.DRY_RUN = False
    return experiment_insight


# ---------------------------------------------------------------------------
# _parse_decision
# ---------------------------------------------------------------------------


class TestParseDecision:
    def test_reject_verdict(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw", tmp_path / "INDEX.md")
        p = mod._parse_decision(DECISION_REJECT)
        assert p["verdict"] == "REJECT"
        assert p["exp_id"] == "20260612-llm-router-v1"
        assert p["date"] == "2026-06-12"
        assert p["slug"] == "llm-router-v1"
        assert "F1 dropped" in p["reasoning"]

    def test_archive_verdict(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw", tmp_path / "INDEX.md")
        p = mod._parse_decision(DECISION_ARCHIVE)
        assert p["verdict"] == "ARCHIVE"
        assert p["slug"] == "brier-accumulation"

    def test_promote_verdict(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw", tmp_path / "INDEX.md")
        p = mod._parse_decision(DECISION_PROMOTE)
        assert p["verdict"] == "PROMOTE"

    def test_no_verdict_returns_none(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw", tmp_path / "INDEX.md")
        p = mod._parse_decision(DECISION_NO_VERDICT)
        assert p["verdict"] is None

    def test_exp_id_without_date_prefix(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw", tmp_path / "INDEX.md")
        text = "**Experiment ID:** `my-custom-id`\n**Date:** 2026-01-01\n**[x] REJECT**"
        p = mod._parse_decision(text)
        assert p["slug"] == "my-custom-id"


# ---------------------------------------------------------------------------
# _update_null_results_index
# ---------------------------------------------------------------------------


class TestUpdateNullResultsIndex:
    def test_replaces_placeholder_on_first_entry(self, monkeypatch, tmp_path):
        index = tmp_path / "INDEX.md"
        index.write_text(NULL_INDEX_TEMPLATE, encoding="utf-8")
        mod = _load(monkeypatch, tmp_path / "raw", index)
        parsed = mod._parse_decision(DECISION_REJECT)
        mod._update_null_results_index(parsed)

        content = index.read_text(encoding="utf-8")
        assert "No entries yet" not in content
        assert "20260612-llm-router-v1" in content
        assert "REJECT" in content

    def test_appends_to_existing_entries(self, monkeypatch, tmp_path):
        index = tmp_path / "INDEX.md"
        index.write_text(NULL_INDEX_WITH_ROW, encoding="utf-8")
        mod = _load(monkeypatch, tmp_path / "raw", index)
        parsed = mod._parse_decision(DECISION_ARCHIVE)
        mod._update_null_results_index(parsed)

        content = index.read_text(encoding="utf-8")
        assert "old-experiment" in content
        assert "brier-accumulation" in content

        # New row must appear BEFORE the ## How to Add an Entry section
        brier_pos = content.index("brier-accumulation")
        how_to_pos = content.index("## How to Add an Entry")
        assert brier_pos < how_to_pos, (
            "new entry must be in the table, not after ## How to Add an Entry"
        )

    def test_skips_if_index_missing(self, monkeypatch, tmp_path):
        index = tmp_path / "nonexistent" / "INDEX.md"
        mod = _load(monkeypatch, tmp_path / "raw", index)
        parsed = mod._parse_decision(DECISION_REJECT)
        # Should not raise — just silently skip
        mod._update_null_results_index(parsed)

    def test_reasoning_truncated_to_10_words(self, monkeypatch, tmp_path):
        index = tmp_path / "INDEX.md"
        index.write_text(NULL_INDEX_TEMPLATE, encoding="utf-8")
        mod = _load(monkeypatch, tmp_path / "raw", index)
        parsed = mod._parse_decision(DECISION_REJECT)
        mod._update_null_results_index(parsed)

        content = index.read_text(encoding="utf-8")
        # Row should exist and reasoning column ≤ ~10 words + ellipsis
        row_line = [line for line in content.splitlines() if "llm-router-v1" in line][0]
        cells = [c.strip() for c in row_line.strip("|").split("|")]
        why_col = cells[-1]
        word_count = len(why_col.replace("…", "").split())
        assert word_count <= 10


# ---------------------------------------------------------------------------
# _create_raw_insight
# ---------------------------------------------------------------------------


class TestCreateRawInsight:
    def test_creates_raw_note_for_reject(self, monkeypatch, tmp_path):
        raw_dir = tmp_path / "raw"
        mod = _load(monkeypatch, raw_dir, tmp_path / "INDEX.md")
        parsed = mod._parse_decision(DECISION_REJECT)
        mod._create_raw_insight(parsed)

        files = list(raw_dir.glob("*-insight.md"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "#null-result" in content
        assert "#experiment-insight" in content
        assert "#rejected" in content
        assert "llm-router-v1" in content
        assert "F1 dropped" in content
        assert "Что это говорит о механизме" in content
        assert "Где этот инсайт может быть ключом" in content

    def test_creates_raw_note_for_archive(self, monkeypatch, tmp_path):
        raw_dir = tmp_path / "raw"
        mod = _load(monkeypatch, raw_dir, tmp_path / "INDEX.md")
        parsed = mod._parse_decision(DECISION_ARCHIVE)
        mod._create_raw_insight(parsed)

        files = list(raw_dir.glob("*-insight.md"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "#archived" in content

    def test_idempotent_second_write(self, monkeypatch, tmp_path):
        raw_dir = tmp_path / "raw"
        mod = _load(monkeypatch, raw_dir, tmp_path / "INDEX.md")
        parsed = mod._parse_decision(DECISION_REJECT)
        mod._create_raw_insight(parsed)
        mod._create_raw_insight(parsed)  # second call

        files = list(raw_dir.glob("*-insight.md"))
        assert len(files) == 1  # not duplicated


# ---------------------------------------------------------------------------
# main() — integration: file path filter
# ---------------------------------------------------------------------------


class TestMain:
    def _run_main(self, monkeypatch, tmp_path, file_path: str, content: str):
        raw_dir = tmp_path / "raw"
        index = tmp_path / "INDEX.md"
        index.write_text(NULL_INDEX_TEMPLATE, encoding="utf-8")
        mod = _load(monkeypatch, raw_dir, index)

        stdin_data = json.dumps({"tool_input": {"file_path": file_path, "content": content}})
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO(stdin_data))
        mod.main()
        return raw_dir, index

    def test_skips_non_decision_file(self, monkeypatch, tmp_path):
        raw_dir, index = self._run_main(
            monkeypatch,
            tmp_path,
            "experiments/20260612-foo/claim.md",
            DECISION_REJECT,
        )
        assert not list(raw_dir.glob("*.md"))
        assert "No entries yet" in index.read_text(encoding="utf-8")

    def test_skips_promote_verdict(self, monkeypatch, tmp_path):
        raw_dir, index = self._run_main(
            monkeypatch,
            tmp_path,
            "experiments/20260601-evidence-guard/decision.md",
            DECISION_PROMOTE,
        )
        assert not list(raw_dir.glob("*.md"))
        assert "No entries yet" in index.read_text(encoding="utf-8")

    def test_processes_reject_decision(self, monkeypatch, tmp_path):
        raw_dir, index = self._run_main(
            monkeypatch,
            tmp_path,
            "experiments/20260612-llm-router-v1/decision.md",
            DECISION_REJECT,
        )
        assert list(raw_dir.glob("*-insight.md"))
        assert "llm-router-v1" in index.read_text(encoding="utf-8")

    def test_processes_archive_decision(self, monkeypatch, tmp_path):
        raw_dir, index = self._run_main(
            monkeypatch,
            tmp_path,
            "experiments/20260610-brier-accumulation/decision.md",
            DECISION_ARCHIVE,
        )
        assert list(raw_dir.glob("*-insight.md"))
        assert "brier-accumulation" in index.read_text(encoding="utf-8")

    def test_reads_from_disk_if_no_content_in_stdin(self, monkeypatch, tmp_path):
        raw_dir = tmp_path / "raw"
        index = tmp_path / "INDEX.md"
        index.write_text(NULL_INDEX_TEMPLATE, encoding="utf-8")

        # Write decision.md to a real temp path
        exp_dir = tmp_path / "experiments" / "20260612-llm-router-v1"
        exp_dir.mkdir(parents=True)
        dec_file = exp_dir / "decision.md"
        dec_file.write_text(DECISION_REJECT, encoding="utf-8")

        mod = _load(monkeypatch, raw_dir, index)
        # Use forward slashes so the regex in main() matches on Windows too
        stdin_data = json.dumps({"tool_input": {"file_path": dec_file.as_posix(), "content": ""}})
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO(stdin_data))
        mod.main()

        assert list(raw_dir.glob("*-insight.md"))
