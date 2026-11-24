"""Tests for experiment_insight.py -- FL decision.md -> project index + raw note.

WHY: the hook runs on every Write/Edit PostToolUse event and must:
- fire on Windows (backslash) paths -- it silently never did before 2026-11-08
- silently skip non-decision.md files and files without a recognised verdict
- classify outcomes through a closed map and NEVER guess (unknown token, ambiguous
  checkboxes, corrected verdict are not captured)
- write ONE note per (project, experiment, verdict) with provenance and an explicit
  not-verified evidence status; a repeat must not duplicate it or the index row
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


def _decision(verdict_line: str, exp_id="20260612-llm-router-v1", date="2026-06-12", extra=""):
    return f"""\
# Decision

**Experiment ID:** `{exp_id}`
**Date:** {date}
{extra}
## Verdict

{verdict_line}

## Reasoning

LLM router did not generalise beyond training distribution.
F1 dropped from 0.89 to 0.31 on real data.
Root cause: category leakage from source annotation, not biology.

---

*Signed: claude, {date}*
"""


DECISION_REJECT = _decision(
    "**[ ] PROMOTE**\n**[ ] REPEAT**\n**[x] REJECT** — claim falsified, do not proceed\n**[ ] ARCHIVE**"
)
DECISION_ARCHIVE = _decision(
    "**[ ] PROMOTE**\n**[ ] REPEAT**\n**[ ] REJECT**\n**[x] ARCHIVE** — valid but deprioritized",
    exp_id="20260610-brier-accumulation",
    date="2026-06-10",
)
DECISION_PROMOTE = _decision("**[x] PROMOTE**", exp_id="20260601-evidence-guard", date="2026-06-01")
DECISION_NO_VERDICT = (
    "# Decision\n\n**Experiment ID:** `20260601-incomplete`\n\n## Verdict\n\nNo boxes.\n"
)
UNCHECKED_TEMPLATE = _decision("- [ ] PROMOTE\n- [ ] REPEAT\n- [ ] REJECT\n- [ ] ARCHIVE")

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

PARKED_INDEX = """\
# parked/INDEX.md

## Index

| ID | Date | Slug | Why parked | Revival trigger |
|----|------|------|-----------|----------------|
| example | 2026-01-01 | example-idea | deprioritized | new dataset |

## Footer
"""


def _load(monkeypatch: pytest.MonkeyPatch, raw_dir: Path, index_path: Path | None = None):
    """Reload experiment_insight with patched paths."""
    monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
    monkeypatch.setenv("CLAUDE_DRY_RUN", "0")

    import experiment_insight

    importlib.reload(experiment_insight)
    experiment_insight.RAW_DIR = raw_dir
    experiment_insight.NULL_RESULTS_INDEX = index_path
    experiment_insight.DRY_RUN = False
    return experiment_insight


def _project(tmp_path: Path, name="proj", *, null_index=None, parked_index=None, git=True):
    """A project dir with experiments/ and optional indexes. Returns (project_dir, decision_path)."""
    proj = tmp_path / name
    (proj / "experiments" / "20260612-llm-router-v1").mkdir(parents=True)
    if git:
        (proj / ".git").mkdir()
    if null_index is not None:
        (proj / "null_results").mkdir()
        (proj / "null_results" / "INDEX.md").write_text(null_index, encoding="utf-8")
    if parked_index is not None:
        (proj / "parked").mkdir()
        (proj / "parked" / "INDEX.md").write_text(parked_index, encoding="utf-8")
    return proj, proj / "experiments" / "20260612-llm-router-v1" / "decision.md"


def _fire(monkeypatch, mod, file_path: str, content: str = ""):
    stdin_data = json.dumps({"tool_input": {"file_path": file_path, "content": content}})
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(stdin_data))
    mod.main()


# ---------------------------------------------------------------------------
# _parse_decision / classification
# ---------------------------------------------------------------------------


class TestParseDecision:
    def test_reject_verdict(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        p = mod._parse_decision(DECISION_REJECT)
        assert (p["verdict"], p["outcome"]) == ("REJECT", "NEGATIVE")
        assert p["exp_id"] == "20260612-llm-router-v1"
        assert p["date"] == "2026-06-12"
        assert p["slug"] == "llm-router-v1"
        assert "F1 dropped" in p["reasoning"]

    def test_archive_verdict(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        p = mod._parse_decision(DECISION_ARCHIVE)
        assert (p["verdict"], p["outcome"], p["slug"]) == (
            "ARCHIVE",
            "ARCHIVE",
            "brier-accumulation",
        )

    def test_promote_is_positive_not_negative(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        assert mod._parse_decision(DECISION_PROMOTE)["outcome"] == "POSITIVE"

    def test_no_verdict_and_unchecked_template_have_no_outcome(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        assert mod._parse_decision(DECISION_NO_VERDICT)["outcome"] is None
        # unchecked options must never be read as the verdict
        assert mod._parse_decision(UNCHECKED_TEMPLATE)["outcome"] is None

    @pytest.mark.parametrize(
        ("line", "word", "outcome"),
        [
            ("- [x] REJECTED — falsified", "REJECTED", "NEGATIVE"),
            ("## Verdict: REJECTED", "REJECTED", "NEGATIVE"),
            ("- [x] INCONCLUSIVE", "INCONCLUSIVE", "INCONCLUSIVE"),
            ("- [x] REPEAT — more data", "REPEAT", "INCONCLUSIVE"),
            ("## Decision: NEEDS-HUMAN (owner call)", "NEEDS-HUMAN", "NEEDS_HUMAN"),
            ("- [x] KILLED", "KILLED", "NEGATIVE"),
        ],
    )
    def test_current_vocabulary(self, monkeypatch, tmp_path, line, word, outcome):
        mod = _load(monkeypatch, tmp_path / "raw")
        text = f"**Experiment ID:** `20260101-x`\n\n{line}\n\n## Reasoning\n\nr\n"
        p = mod._parse_decision(text)
        assert (p["verdict"], p["outcome"]) == (word, outcome)

    def test_unknown_token_is_not_classified(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        p = mod._parse_decision("## Verdict: RESOLVED\n")
        assert p["outcome"] is None and p["basis"] == "unknown-token"

    def test_two_different_checked_boxes_are_ambiguous(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        p = mod._parse_decision("- [x] REJECT\n- [x] PROMOTE\n")
        assert p["outcome"] is None and p["basis"] == "ambiguous-checkboxes"

    def test_corrected_verdict_is_not_classified(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        text = "CORRECTION ADDENDUM: verdict downgraded CONFIRMED -> FALSIFIED\n\n- [x] PROMOTE\n"
        p = mod._parse_decision(text)
        assert p["outcome"] is None and p["basis"] == "corrected-verdict"

    def test_exp_id_without_date_prefix(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        p = mod._parse_decision(
            "**Experiment ID:** `my-custom-id`\n**Date:** 2026-01-01\n- [x] REJECT"
        )
        assert p["slug"] == "my-custom-id"


# ---------------------------------------------------------------------------
# indexes
# ---------------------------------------------------------------------------


class TestIndexes:
    def test_override_replaces_placeholder_on_first_entry(self, monkeypatch, tmp_path):
        index = tmp_path / "INDEX.md"
        index.write_text(NULL_INDEX_TEMPLATE, encoding="utf-8")
        mod = _load(monkeypatch, tmp_path / "raw", index)
        mod._update_null_results_index(mod._parse_decision(DECISION_REJECT))
        content = index.read_text(encoding="utf-8")
        assert "No entries yet" not in content
        assert "20260612-llm-router-v1" in content and "REJECT" in content

    def test_row_inserted_inside_table(self, monkeypatch, tmp_path):
        index = tmp_path / "INDEX.md"
        index.write_text(NULL_INDEX_WITH_ROW, encoding="utf-8")
        mod = _load(monkeypatch, tmp_path / "raw", index)
        mod._update_null_results_index(mod._parse_decision(DECISION_REJECT))
        content = index.read_text(encoding="utf-8")
        assert "old-experiment" in content
        assert content.index("llm-router-v1") < content.index("## How to Add an Entry")

    def test_index_row_not_duplicated_on_repeat(self, monkeypatch, tmp_path):
        index = tmp_path / "INDEX.md"
        index.write_text(NULL_INDEX_TEMPLATE, encoding="utf-8")
        mod = _load(monkeypatch, tmp_path / "raw", index)
        parsed = mod._parse_decision(DECISION_REJECT)
        for _ in range(3):
            mod._update_null_results_index(parsed)
        assert index.read_text(encoding="utf-8").count("20260612-llm-router-v1") == 1

    def test_skips_if_index_missing(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw", tmp_path / "nonexistent" / "INDEX.md")
        mod._update_null_results_index(mod._parse_decision(DECISION_REJECT))  # must not raise

    def test_reasoning_truncated_to_10_words(self, monkeypatch, tmp_path):
        index = tmp_path / "INDEX.md"
        index.write_text(NULL_INDEX_TEMPLATE, encoding="utf-8")
        mod = _load(monkeypatch, tmp_path / "raw", index)
        mod._update_null_results_index(mod._parse_decision(DECISION_REJECT))
        row = [x for x in index.read_text(encoding="utf-8").splitlines() if "llm-router-v1" in x][0]
        why = [c.strip() for c in row.strip("|").split("|")][-1]
        assert len(why.replace("…", "").split()) <= 10

    def test_non_negative_outcomes_do_not_touch_null_results(self, monkeypatch, tmp_path):
        index = tmp_path / "INDEX.md"
        index.write_text(NULL_INDEX_TEMPLATE, encoding="utf-8")
        mod = _load(monkeypatch, tmp_path / "raw", index)
        for text in (DECISION_ARCHIVE, DECISION_PROMOTE):
            mod._update_null_results_index(mod._parse_decision(text))
        assert "No entries yet" in index.read_text(encoding="utf-8")

    def test_archive_goes_to_parked_index_of_the_project(self, monkeypatch, tmp_path):
        proj, dec = _project(tmp_path, null_index=NULL_INDEX_TEMPLATE, parked_index=PARKED_INDEX)
        mod = _load(monkeypatch, tmp_path / "raw")
        _fire(monkeypatch, mod, str(dec), DECISION_ARCHIVE)
        parked = (proj / "parked" / "INDEX.md").read_text(encoding="utf-8")
        assert "brier-accumulation" in parked
        assert parked.index("brier-accumulation") < parked.index("## Footer")
        assert "No entries yet" in (proj / "null_results" / "INDEX.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# raw note
# ---------------------------------------------------------------------------


class TestRawNote:
    def _write(self, mod, tmp_path, text=DECISION_REJECT, name="proj"):
        proj, dec = _project(tmp_path, name=name)
        parsed = mod._parse_decision(text)
        return mod._create_raw_insight(parsed, mod._project_of(str(dec)), dec.as_posix()), proj

    def test_note_has_provenance_and_not_verified_status(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        path, proj = self._write(mod, tmp_path)
        text = path.read_text(encoding="utf-8")
        for needle in (
            "project: proj",
            "experiment_id: 20260612-llm-router-v1",
            "decision_date: 2026-06-12",
            "verdict_as_written: REJECT",
            "outcome: NEGATIVE",
            "evidence: UNKNOWN",
            "status: auto-captured-not-verified",
            "decision.md",
            "#null-result",
            "#rejected",
            "F1 dropped",
        ):
            assert needle in text, needle
        assert "[заполнить" not in text

    def test_repeat_does_not_duplicate(self, monkeypatch, tmp_path):
        raw = tmp_path / "raw"
        mod = _load(monkeypatch, raw)
        proj, dec = _project(tmp_path)
        project = mod._project_of(str(dec))
        parsed = mod._parse_decision(DECISION_REJECT)
        assert mod._create_raw_insight(parsed, project, dec.as_posix()) is not None
        assert mod._create_raw_insight(parsed, project, dec.as_posix()) is None
        assert len(list(raw.glob("*-insight.md"))) == 1

    def test_changed_verdict_writes_new_note_that_supersedes_old(self, monkeypatch, tmp_path):
        raw = tmp_path / "raw"
        mod = _load(monkeypatch, raw)
        proj, dec = _project(tmp_path)
        project = mod._project_of(str(dec))
        first = mod._create_raw_insight(mod._parse_decision(DECISION_REJECT), project, "s")
        second = mod._create_raw_insight(
            mod._parse_decision(DECISION_REJECT.replace("[x] REJECT", "[x] REPEAT")), project, "s"
        )
        assert first and second and first != second
        assert first.exists(), "history is preserved"
        assert f"supersedes: [{first.name}]" in second.read_text(encoding="utf-8")

    def test_same_experiment_id_in_two_projects_does_not_collide(self, monkeypatch, tmp_path):
        raw = tmp_path / "raw"
        mod = _load(monkeypatch, raw)
        for name in ("alpha", "beta"):
            _, dec = _project(tmp_path, name=name)
            mod._create_raw_insight(
                mod._parse_decision(DECISION_REJECT), mod._project_of(str(dec)), dec.as_posix()
            )
        assert len(list(raw.glob("*-insight.md"))) == 2

    def test_secrets_in_reasoning_are_redacted(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        secret = "sk-ant-api03-" + "A1b2C3d4" * 6
        text = DECISION_REJECT.replace("Root cause", f"key {secret} Root cause")
        path, _ = self._write(mod, tmp_path, text)
        assert secret not in path.read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        ("line", "tag"),
        [("- [x] INCONCLUSIVE", "#inconclusive"), ("## Decision: NEEDS-HUMAN", "#needs-human")],
    )
    def test_uncertain_outcomes_are_labelled_not_negative(self, monkeypatch, tmp_path, line, tag):
        mod = _load(monkeypatch, tmp_path / "raw")
        path, _ = self._write(mod, tmp_path, _decision(line))
        text = path.read_text(encoding="utf-8")
        assert tag in text and "#null-result" not in text and "#rejected" not in text


# ---------------------------------------------------------------------------
# main() -- integration
# ---------------------------------------------------------------------------


class TestMain:
    def test_skips_non_decision_file(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        _, dec = _project(tmp_path, null_index=NULL_INDEX_TEMPLATE)
        _fire(monkeypatch, mod, str(dec.with_name("claim.md")), DECISION_REJECT)
        assert not list((tmp_path / "raw").glob("*.md")) if (tmp_path / "raw").exists() else True

    def test_skips_when_no_verdict(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        _, dec = _project(tmp_path)
        _fire(monkeypatch, mod, str(dec), UNCHECKED_TEMPLATE)
        assert not (tmp_path / "raw").exists()

    def test_reject_updates_project_index_and_writes_note(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        proj, dec = _project(tmp_path, null_index=NULL_INDEX_TEMPLATE)
        _fire(monkeypatch, mod, dec.as_posix(), DECISION_REJECT)
        assert list((tmp_path / "raw").glob("*-insight.md"))
        assert "llm-router-v1" in (proj / "null_results" / "INDEX.md").read_text(encoding="utf-8")

    def test_windows_backslash_path_fires(self, monkeypatch, tmp_path):
        """Regression: the old filter matched '/' only, so no Windows path ever fired."""
        mod = _load(monkeypatch, tmp_path / "raw")
        proj, dec = _project(tmp_path, null_index=NULL_INDEX_TEMPLATE)
        win = str(dec).replace("/", "\\")
        assert mod._PATH_RE.search(mod._norm_path(r"D:\p\experiments\20260101-x\decision.md"))
        _fire(monkeypatch, mod, win, DECISION_REJECT)
        assert list((tmp_path / "raw").glob("*-insight.md"))

    def test_second_edit_is_a_noop(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        proj, dec = _project(tmp_path, null_index=NULL_INDEX_TEMPLATE)
        for _ in range(3):
            _fire(monkeypatch, mod, dec.as_posix(), DECISION_REJECT)
        assert len(list((tmp_path / "raw").glob("*-insight.md"))) == 1
        index_text = (proj / "null_results" / "INDEX.md").read_text(encoding="utf-8")
        assert index_text.count("| 20260612-llm-router-v1 |") == 1

    def test_unknown_verdict_writes_nothing(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        proj, dec = _project(tmp_path, null_index=NULL_INDEX_TEMPLATE)
        _fire(monkeypatch, mod, dec.as_posix(), _decision("## Verdict: RESOLVED"))
        assert not (tmp_path / "raw").exists()
        assert "No entries yet" in (proj / "null_results" / "INDEX.md").read_text(encoding="utf-8")

    def test_project_without_index_still_gets_note(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        _, dec = _project(tmp_path)
        _fire(monkeypatch, mod, dec.as_posix(), DECISION_REJECT)
        assert list((tmp_path / "raw").glob("*-insight.md"))

    def test_reads_from_disk_if_no_content_in_stdin(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        _, dec = _project(tmp_path)
        dec.write_text(DECISION_REJECT, encoding="utf-8")
        _fire(monkeypatch, mod, str(dec), "")
        assert list((tmp_path / "raw").glob("*-insight.md"))


class TestRealCorpusShapes:
    """Shapes that flipped or lost real outcomes in the 2026-11-08 replay over 637 decision files."""

    def test_skeptic_subverdict_does_not_flip_a_rejected_file(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        text = (
            "# Decision\n\n**Experiment ID:** `20260910-x-h22`\n\n## Verdict\n\n"
            "**REJECTED** — the synchronous-only characterisation fails.\n\n"
            "## Skeptic review\n\n**Verdict: CONFIRMED.** The reviewer reconstructed the case.\n"
        )
        p = mod._parse_decision(text)
        assert p["outcome"] is None, "a REJECTED file must never be captured as POSITIVE"

    def test_own_verdict_beats_later_subverdict(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        text = (
            "# Decision\n\nVerdict: **PARTIAL_OVERLAP** — neither identical nor contained\n\n"
            "**Verdict: CONFIRMED, with 2 corrections applied below.**\n"
        )
        assert mod._parse_decision(text)["outcome"] is None  # not "CONFIRMED"

    def test_null_is_negative_but_not_tagged_rejected(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        _, dec = _project(tmp_path)
        text = "# Decision\n\n**Experiment ID:** `20260620-g46-x`\n\n## Verdict: NULL\n\n## Reasoning\n\nNo effect.\n"
        p = mod._parse_decision(text)
        assert (p["verdict"], p["outcome"]) == ("NULL", "NEGATIVE")
        note = mod._create_raw_insight(p, mod._project_of(str(dec)), "s").read_text(
            encoding="utf-8"
        )
        assert "#null-result" in note and "#rejected" not in note

    def test_bold_verdict_label_with_space(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        p = mod._parse_decision("# D\n\n**Verdict:** REJECT → null_results/\n\n## Reasoning\n\nx\n")
        assert (p["verdict"], p["outcome"]) == ("REJECT", "NEGATIVE")

    def test_heading_with_dash_form(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        p = mod._parse_decision("# G99 decision — REJECT (hard closed)\n\n## Reasoning\n\nx\n")
        assert p["outcome"] == "NEGATIVE"


# ---------------------------------------------------------------------------
# O44 (2026-11-09): reliable experiment id and date -- no "unknown" rows, no invented dates
# ---------------------------------------------------------------------------

NO_ID_REJECT = """\
# decision.md -- {name}

## Verdict

- [x] REJECT

## Reasoning

The kill criterion fired on the pre-registered metric.
"""


def _project_no_id(tmp_path: Path, exp_dir: str, *, name="proj"):
    proj = tmp_path / name
    (proj / "experiments" / exp_dir).mkdir(parents=True)
    (proj / ".git").mkdir()
    (proj / "null_results").mkdir()
    (proj / "null_results" / "INDEX.md").write_text(NULL_INDEX_TEMPLATE, encoding="utf-8")
    return proj, proj / "experiments" / exp_dir / "decision.md"


def _rows(proj: Path) -> list[str]:
    text = (proj / "null_results" / "INDEX.md").read_text(encoding="utf-8")
    return [x for x in text.splitlines() if x.startswith("|") and "No entries yet" not in x][2:]


class TestIdAndDateProvenance:
    def test_folder_id_used_when_file_states_none_and_row_not_duplicated(
        self, monkeypatch, tmp_path
    ):
        """The reproduced defect: 3 saves of one decision.md gave 3 'unknown' rows."""
        mod = _load(monkeypatch, tmp_path / "raw")
        proj, dec = _project_no_id(tmp_path, "20260906-sample-null")
        for _ in range(3):
            _fire(monkeypatch, mod, str(dec), NO_ID_REJECT.format(name=dec.parent.name))
        rows = _rows(proj)
        assert len(rows) == 1 and rows[0].startswith("| 20260906-sample-null |")
        assert "unknown" not in (proj / "null_results" / "INDEX.md").read_text(encoding="utf-8")
        assert len(list((tmp_path / "raw").glob("*-insight.md"))) == 1

    def test_unverified_folder_name_gets_no_row_but_a_discoverable_note(
        self, monkeypatch, tmp_path, capsys
    ):
        mod = _load(monkeypatch, tmp_path / "raw")
        proj, dec = _project_no_id(tmp_path, "g99")
        for _ in range(3):
            _fire(monkeypatch, mod, str(dec), NO_ID_REJECT.format(name="g99"))
        assert _rows(proj) == []
        notes = list((tmp_path / "raw").glob("*-insight.md"))
        assert len(notes) == 1
        text = notes[0].read_text(encoding="utf-8")
        assert "experiment_id: undetermined" in text and "experiment_dir: g99" in text
        assert "unknown" not in text.split("---")[1]  # frontmatter
        assert "no reliable experiment id" in capsys.readouterr().err

    def test_impossible_date_prefix_is_not_an_id(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        p = mod._parse_decision(NO_ID_REJECT.format(name="x"), "20269999-bad-prefix")
        assert p["exp_id"] is None and p["id_source"] == "undetermined"

    def test_heading_naming_another_id_makes_it_undetermined(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        text = "# decision.md -- 20260101-other-experiment\n\n- [x] REJECT\n"
        p = mod._parse_decision(text, "20260906-sample-null")
        assert p["exp_id"] is None

    def test_explicit_id_wins_and_placeholder_is_rejected(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        explicit = mod._parse_decision(
            "**Experiment ID:** `20260101-explicit`\n- [x] REJECT\n", "20260906-folder"
        )
        assert (explicit["exp_id"], explicit["id_source"]) == ("20260101-explicit", "explicit")
        placeholder = mod._parse_decision(
            "**Experiment ID:** `<YYYYMMDD-short-slug>`\n- [x] REJECT\n", "20260906-folder"
        )
        assert (placeholder["exp_id"], placeholder["id_source"]) == ("20260906-folder", "directory")

    def test_missing_date_is_not_today_and_not_the_folder_prefix(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        proj, dec = _project_no_id(tmp_path, "20260906-sample-null")
        _fire(monkeypatch, mod, str(dec), NO_ID_REJECT.format(name="x"))
        (note,) = (tmp_path / "raw").glob("*-insight.md")
        text = note.read_text(encoding="utf-8")
        assert note.name.startswith("undated-")
        assert "decision_date: not stated" in text
        assert "2026-09-06" not in text.split("captured_at")[0]  # the folder prefix is not a date
        assert "| not stated |" in _rows(proj)[0]

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("**Date:** 2026-09-06", "2026-09-06"),
            ("Date: 2026-09-07", "2026-09-07"),
            ("Дата: 2026-09-08", "2026-09-08"),
            ("**Date:** 2026-13-45", None),
            ("Updated 2026-09-09 by someone", None),
        ],
    )
    def test_date_only_from_an_explicit_statement(self, monkeypatch, tmp_path, line, expected):
        mod = _load(monkeypatch, tmp_path / "raw")
        p = mod._parse_decision(f"# D\n{line}\n- [x] REJECT\n", "20260101-x")
        assert p["date"] == expected

    def test_undated_note_is_idempotent_across_days(self, monkeypatch, tmp_path):
        import datetime as real

        raw = tmp_path / "raw"
        mod = _load(monkeypatch, raw)
        proj, dec = _project_no_id(tmp_path, "20260906-sample-null")
        project = mod._project_of(str(dec))
        parsed = mod._parse_decision(NO_ID_REJECT.format(name="x"), "20260906-sample-null")

        class _Day(real.datetime):
            day = 1

            @classmethod
            def now(cls, tz=None):
                return cls(2026, 11, cls.day, 12, 0, 0, tzinfo=tz)

        monkeypatch.setattr(mod, "datetime", _Day)
        assert mod._create_raw_insight(parsed, project, "s") is not None
        _Day.day = 2
        assert mod._create_raw_insight(parsed, project, "s") is None
        assert len(list(raw.glob("*-insight.md"))) == 1

    def test_existing_rows_are_never_rewritten(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        proj, dec = _project_no_id(tmp_path, "20260906-sample-null")
        index = proj / "null_results" / "INDEX.md"
        legacy = "| unknown | 2026-11-08 | unknown | REJECT | old junk row |"
        index.write_text(
            index.read_text(encoding="utf-8").replace("| No entries yet |", legacy),
            encoding="utf-8",
        )
        _fire(monkeypatch, mod, str(dec), NO_ID_REJECT.format(name="x"))
        text = index.read_text(encoding="utf-8")
        assert legacy in text and "| 20260906-sample-null |" in text

    def test_parallel_hooks_give_one_row_and_one_note(self, tmp_path):
        import subprocess

        proj, dec = _project_no_id(tmp_path, "20260906-sample-null")
        dec.write_text(NO_ID_REJECT.format(name="x"), encoding="utf-8")
        raw = tmp_path / "raw"
        child = (
            "import sys, json, io, pathlib\n"
            f"sys.path.insert(0, {str(Path(__file__).parent.parent / 'hooks')!r})\n"
            "import experiment_insight as m\n"
            f"m.RAW_DIR = pathlib.Path({str(raw)!r}); m.DRY_RUN = False\n"
            f"sys.stdin = io.StringIO(json.dumps({{'tool_input': {{'file_path': {str(dec)!r}}}}}))\n"
            "m.main()\n"
        )
        import os

        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_INVOKED_BY"}
        procs = [
            subprocess.Popen(
                [sys.executable, "-c", child],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for _ in range(6)
        ]
        for p in procs:
            p.wait(timeout=90)
        assert len(_rows(proj)) == 1
        assert len(list(raw.glob("*-insight.md"))) == 1


class TestRound2ReviewFindings:
    @pytest.mark.parametrize("junk", ["unknown", "TBD", "todo", "YYYYMMDD-short-slug", "N/A"])
    def test_explicit_junk_id_falls_through_to_folder(self, monkeypatch, tmp_path, junk):
        mod = _load(monkeypatch, tmp_path / "raw")
        text = f"# D\n**Experiment ID:** {junk}\n\n## Verdict\n- [x] REJECT\n"
        p = mod._parse_decision(text, "20260906-real-folder")
        assert (p["exp_id"], p["id_source"]) == ("20260906-real-folder", "directory")
        p2 = mod._parse_decision(text, "g99")
        assert p2["exp_id"] is None

    def test_explicit_id_inside_a_code_block_or_later_section_is_ignored(
        self, monkeypatch, tmp_path
    ):
        mod = _load(monkeypatch, tmp_path / "raw")
        text = (
            "# D\n\n```\n**Experiment ID:** 20200101-in-code\n```\n\n"
            "## Notes\n**Experiment ID:** 20200202-later\n\n- [x] REJECT\n"
        )
        p = mod._parse_decision(text, "20260906-folder")
        assert p["exp_id"] == "20260906-folder"

    @pytest.mark.parametrize(
        "text",
        [
            "# D\n\n```\nDate: 2020-01-01\n```\n- [x] REJECT\n",
            "# D\n    Date: 2019-05-05\n- [x] REJECT\n",
            "# D\n\n## Notes\nDate: 2019-05-05\n- [x] REJECT\n",
            "# D\n\n## Prior\n**Date:** 2020-02-02\n- [x] REJECT\n",
        ],
    )
    def test_date_from_code_indent_or_later_section_is_not_the_decision_date(
        self, monkeypatch, tmp_path, text
    ):
        mod = _load(monkeypatch, tmp_path / "raw")
        assert mod._parse_decision(text, "20260101-x")["date"] is None

    def test_header_date_beats_a_later_bold_date_in_document_order(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        text = "# D\nDate: 2026-01-01\nsee **Date:** 2020-02-02\n\n## Prior\n- [x] REJECT\n"
        assert mod._parse_decision(text, "20260101-x")["date"] == "2026-01-01"

    def test_future_date_is_not_a_decision_date(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        text = "# D\n**Date:** 2999-01-01\n- [x] REJECT\n"
        assert mod._parse_decision(text, "20260101-x")["date"] is None

    def test_heading_with_trailing_period_names_the_same_id(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        text = "# Decision 20260514-prompt-injection.\n- [x] REJECT\n"
        assert mod._parse_decision(text, "20260514-prompt-injection")["exp_id"] == (
            "20260514-prompt-injection"
        )

    def test_bom_before_heading_does_not_hide_a_conflicting_id(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        text = "\ufeff# Decision 20250101-other-experiment\n- [x] REJECT\n"
        assert mod._parse_decision(text, "20260906-folder")["exp_id"] is None

    def test_non_utf8_decision_file_does_not_crash_main(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path / "raw")
        proj, dec = _project(tmp_path, null_index=NULL_INDEX_TEMPLATE)
        dec.write_bytes("# Решение\n- [x] REJECT\n".encode("cp1251"))
        _fire(monkeypatch, mod, str(dec), "")  # empty content => the hook reads the file
        assert (
            not list((tmp_path / "raw").glob("*-insight.md"))
            if (tmp_path / "raw").exists()
            else True
        )
