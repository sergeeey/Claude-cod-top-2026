"""Tests for hooks/verdict_logger.py -- verdict extraction and append-only logging.

Control: known reviewer/security-guard verdict text is extracted correctly.
Mutation-style checks: text that doesn't match any known format is silently ignored
(adversarially proven -- a hook that "detects" everything is as useless as one that
detects nothing).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
import verdict_logger


# --------------------------------------------------------------------------- extraction
def test_extracts_reviewer_lgtm():
    text = "Some review text...\n\nVERDICT: LGTM\nSEVERITY: -\n"
    assert verdict_logger.extract(text) == ("reviewer", "LGTM")


def test_extracts_reviewer_needs_work():
    text = "VERDICT: NEEDS_WORK\n"
    assert verdict_logger.extract(text) == ("reviewer", "NEEDS_WORK")


def test_lowercase_verdict_label_does_not_match_reviewer_format():
    """Label casing is the disambiguator (see hooks/verdict_logger.py) -- a lowercase
    'verdict:' matches neither template exactly, so it's correctly left unmatched."""
    assert verdict_logger.extract("verdict: lgtm\n") is None


def test_extracts_security_guard_pass():
    text = "## Security Report\n\nCRITICAL [0]: none\nVerdict: PASS\n"
    assert verdict_logger.extract(text) == ("security-guard", "PASS")


def test_extracts_security_guard_block():
    text = "Verdict: BLOCK\n"
    assert verdict_logger.extract(text) == ("security-guard", "BLOCK")


def test_reviewer_pattern_checked_before_security_guard_pattern():
    """A reviewer BLOCK verdict must not be mis-tagged as security-guard, even though
    'BLOCK' alone would also match the looser security-guard-style pattern."""
    text = "VERDICT: BLOCK\n"
    assert verdict_logger.extract(text) == ("reviewer", "BLOCK")


# --------------------------------------------------------------------------- non-matches
@pytest.mark.parametrize(
    "text",
    [
        "",
        "just some prose with no verdict at all",
        "the word verdict appears but no colon-value follows it",
        "PASS",  # bare word, no "Verdict:" label
    ],
)
def test_no_match_returns_none(text):
    assert verdict_logger.extract(text) is None


# --------------------------------------------------------------------------- git helpers
def test_git_helper_returns_none_on_failure(monkeypatch):
    import subprocess

    def fake_run(*_args, **_kwargs):
        raise OSError("git not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert verdict_logger._git(["rev-parse", "HEAD"]) is None


# --------------------------------------------------------------------------- end-to-end main()
def test_main_appends_jsonl_record_for_reviewer_verdict(monkeypatch, tmp_path, capsys):
    memory_dir = tmp_path / ".claude" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "activeContext.md").write_text("# state\n", encoding="utf-8")
    log_path = memory_dir / "verdict_log.jsonl"

    monkeypatch.setattr(verdict_logger, "_log_path", lambda: log_path)
    monkeypatch.setattr(verdict_logger, "_git", lambda args: None)

    stdin_payload = json.dumps(
        {"last_assistant_message": "VERDICT: LGTM\n", "session_id": "sess-1"}
    )
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(stdin_payload))

    with pytest.raises(SystemExit) as exc:
        verdict_logger.main()
    assert exc.value.code == 0

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["agent"] == "reviewer"
    assert record["verdict"] == "LGTM"
    assert record["session_id"] == "sess-1"
    assert record["schema_version"] == 1


def test_main_prefers_declared_subagent_type_when_present(monkeypatch, tmp_path):
    """Defensive corroboration: if a future Claude Code version DOES pass subagent_type
    on SubagentStop, it should be trusted over the label-casing heuristic -- here forced
    to disagree with the message content to prove the override actually happens."""
    memory_dir = tmp_path / ".claude" / "memory"
    memory_dir.mkdir(parents=True)
    log_path = memory_dir / "verdict_log.jsonl"
    monkeypatch.setattr(verdict_logger, "_log_path", lambda: log_path)
    monkeypatch.setattr(verdict_logger, "_git", lambda args: None)

    # Message content alone would extract ("reviewer", "BLOCK") -- subagent_type disagrees
    # and must win.
    stdin_payload = json.dumps(
        {"last_assistant_message": "VERDICT: BLOCK\n", "subagent_type": "security-guard"}
    )
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(stdin_payload))

    with pytest.raises(SystemExit):
        verdict_logger.main()

    record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["agent"] == "security-guard"
    assert record["verdict"] == "BLOCK"


def test_main_is_silent_when_no_verdict_present(monkeypatch, tmp_path):
    memory_dir = tmp_path / ".claude" / "memory"
    memory_dir.mkdir(parents=True)
    log_path = memory_dir / "verdict_log.jsonl"
    monkeypatch.setattr(verdict_logger, "_log_path", lambda: log_path)

    stdin_payload = json.dumps({"last_assistant_message": "no verdict here"})
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(stdin_payload))

    with pytest.raises(SystemExit) as exc:
        verdict_logger.main()
    assert exc.value.code == 0
    assert not log_path.exists()


def test_main_fails_open_on_malformed_stdin(monkeypatch):
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO("not json"))
    with pytest.raises(SystemExit) as exc:
        verdict_logger.main()
    assert exc.value.code == 0


# --------------------------------------------------------------------------- model + run_outcome
def _user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def _assistant(message_id, model, stop_reason):
    return {
        "type": "assistant",
        "message": {
            "id": message_id,
            "role": "assistant",
            "model": model,
            "stop_reason": stop_reason,
            "content": [{"type": "text", "text": "done"}],
        },
    }


def _write_transcript(home, session_id, agent_id, records):
    subagents = home / ".claude" / "projects" / "proj" / session_id / "subagents"
    subagents.mkdir(parents=True)
    text = "\n".join(json.dumps(r) for r in records) + "\n"
    (subagents / f"agent-{agent_id}.jsonl").write_text(text, encoding="utf-8")


def _point_home_at(monkeypatch, home):
    """Path.home() reads these variables, so the tests never look at the real ~/.claude."""
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))


def test_run_meta_reads_model_and_completed_outcome(monkeypatch, tmp_path):
    _point_home_at(monkeypatch, tmp_path)
    records = [_user("task"), _assistant("m1", "claude-sonnet-5-5", "end_turn")]
    _write_transcript(tmp_path, "sess-1", "a1", records)
    result = verdict_logger._run_meta({"session_id": "sess-1", "agent_id": "a1"})
    assert result == ("claude-sonnet-5-5", "completed")


@pytest.mark.parametrize(
    ("stop_reason", "outcome"),
    [
        ("end_turn", "completed"),
        ("max_tokens", "truncated"),
        ("refusal", "refused"),
        ("tool_use", "interrupted"),
        ("stop_sequence", "unknown"),
    ],
)
def test_run_meta_maps_stop_reason_to_outcome(monkeypatch, tmp_path, stop_reason, outcome):
    _point_home_at(monkeypatch, tmp_path)
    records = [_assistant("m1", "claude-sonnet-5-5", stop_reason)]
    _write_transcript(tmp_path, "sess-2", "a2", records)
    result = verdict_logger._run_meta({"session_id": "sess-2", "agent_id": "a2"})
    assert result == ("claude-sonnet-5-5", outcome)


def test_run_meta_takes_stop_reason_from_final_message_only(monkeypatch, tmp_path):
    """An earlier tool_use must not stand in for a final message with no stop_reason."""
    _point_home_at(monkeypatch, tmp_path)
    records = [
        _assistant("m1", "claude-sonnet-5-5", "tool_use"),
        _user("result"),
        _assistant("m2", "claude-sonnet-5-5", None),
    ]
    _write_transcript(tmp_path, "sess-3", "a3", records)
    result = verdict_logger._run_meta({"session_id": "sess-3", "agent_id": "a3"})
    assert result == ("claude-sonnet-5-5", "unknown")


def test_run_meta_reads_final_message_split_into_records(monkeypatch, tmp_path):
    """One assistant message is written as several records; the stop_reason sits on the last."""
    _point_home_at(monkeypatch, tmp_path)
    records = [
        _assistant("m1", "claude-sonnet-5-5", "tool_use"),
        _user("result"),
        _assistant("m2", "claude-sonnet-5-5", None),
        _assistant("m2", "claude-sonnet-5-5", "end_turn"),
    ]
    _write_transcript(tmp_path, "sess-4", "a4", records)
    result = verdict_logger._run_meta({"session_id": "sess-4", "agent_id": "a4"})
    assert result == ("claude-sonnet-5-5", "completed")


def test_run_meta_is_unknown_when_transcript_is_absent(monkeypatch, tmp_path):
    _point_home_at(monkeypatch, tmp_path)
    result = verdict_logger._run_meta({"session_id": "sess-9", "agent_id": "absent"})
    assert result == ("unknown", "unknown")


@pytest.mark.parametrize(
    ("data", "decoy"),
    [
        ({}, None),
        ({"session_id": "sess-1"}, None),
        ({"session_id": "../escape", "agent_id": "a1"}, "escape/subagents/agent-a1.jsonl"),
        # no decoy for the 129-character id: its path would exceed Windows MAX_PATH
        ({"session_id": "sess-1", "agent_id": "a" * 129}, None),
    ],
)
def test_run_meta_rejects_partial_or_unsafe_ids(monkeypatch, tmp_path, data, decoy):
    """A transcript that an unvalidated id would reach must still be ignored."""
    _point_home_at(monkeypatch, tmp_path)
    projects = tmp_path / ".claude" / "projects"
    # the decoy's own folder is the only project folder, so an unvalidated id matches one file
    if decoy is not None:
        target = projects / decoy
        target.parent.mkdir(parents=True, exist_ok=True)
        record = _assistant("m1", "claude-sonnet-5-5", "end_turn")
        target.write_text(json.dumps(record) + "\n", encoding="utf-8")
    assert verdict_logger._run_meta(data) == ("unknown", "unknown")


def test_run_meta_fails_open_when_home_cannot_be_determined(monkeypatch):
    def no_home(cls):
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(verdict_logger.Path, "home", classmethod(no_home))
    result = verdict_logger._run_meta({"session_id": "sess-1", "agent_id": "a1"})
    assert result == ("unknown", "unknown")


def _run_main_with(monkeypatch, tmp_path, payload):
    """Run main() against a temp log, with the home directory pointed at tmp_path."""
    _point_home_at(monkeypatch, tmp_path)
    memory_dir = tmp_path / "repo" / ".claude" / "memory"
    memory_dir.mkdir(parents=True)
    log_path = memory_dir / "verdict_log.jsonl"
    monkeypatch.setattr(verdict_logger, "_log_path", lambda: log_path)
    monkeypatch.setattr(verdict_logger, "_git", lambda args: None)
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(payload)))
    with pytest.raises(SystemExit) as exc:
        verdict_logger.main()
    assert exc.value.code == 0
    return json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])


def test_main_records_model_and_outcome_from_transcript(monkeypatch, tmp_path):
    records = [_user("task"), _assistant("m1", "claude-opus-5-5", "end_turn")]
    _write_transcript(tmp_path, "sess-5", "a5", records)
    payload = {
        "last_assistant_message": "VERDICT: LGTM\n",
        "session_id": "sess-5",
        "agent_id": "a5",
    }
    record = _run_main_with(monkeypatch, tmp_path, payload)
    assert record["model"] == "claude-opus-5-5"
    assert record["run_outcome"] == "completed"


def test_main_writes_unknown_fields_when_transcript_is_absent(monkeypatch, tmp_path):
    payload = {
        "last_assistant_message": "VERDICT: LGTM\n",
        "session_id": "sess-6",
        "agent_id": "a6",
    }
    record = _run_main_with(monkeypatch, tmp_path, payload)
    assert record["model"] == "unknown"
    assert record["run_outcome"] == "unknown"


def test_run_meta_keeps_stop_reason_when_a_later_record_has_none(monkeypatch, tmp_path):
    _point_home_at(monkeypatch, tmp_path)
    records = [
        _assistant("m2", "claude-sonnet-5-5", "end_turn"),
        _assistant("m2", "claude-sonnet-5-5", None),
    ]
    _write_transcript(tmp_path, "sess-7", "a7", records)
    result = verdict_logger._run_meta({"session_id": "sess-7", "agent_id": "a7"})
    assert result == ("claude-sonnet-5-5", "completed")


def test_last_assistant_meta_skips_synthetic_turns(tmp_path):
    path = tmp_path / "synthetic.jsonl"
    records = [
        _assistant("m1", "claude-sonnet-5-5", "end_turn"),
        _assistant("m2", "<synthetic>", "stop_sequence"),
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    assert verdict_logger._last_assistant_meta(path) == ("claude-sonnet-5-5", "end_turn")


@pytest.mark.parametrize("model", ["m" * 101, "claude\x07sonnet"])
def test_model_longer_than_100_or_unprintable_is_unknown(monkeypatch, tmp_path, model):
    _point_home_at(monkeypatch, tmp_path)
    _write_transcript(tmp_path, "sess-8", "a8", [_assistant("m1", model, "end_turn")])
    result = verdict_logger._run_meta({"session_id": "sess-8", "agent_id": "a8"})
    assert result == ("unknown", "completed")


def test_records_without_id_count_as_separate_messages(monkeypatch, tmp_path):
    """If id-less records shared one key, the earlier end_turn would win; they must not."""
    _point_home_at(monkeypatch, tmp_path)
    records = [
        _assistant(None, "claude-sonnet-5-5", "end_turn"),
        _assistant(None, "claude-sonnet-5-5", None),
    ]
    _write_transcript(tmp_path, "sess-10", "a10", records)
    result = verdict_logger._run_meta({"session_id": "sess-10", "agent_id": "a10"})
    assert result == ("claude-sonnet-5-5", "unknown")


def test_blank_and_broken_lines_are_skipped(monkeypatch, tmp_path):
    _point_home_at(monkeypatch, tmp_path)
    subagents = tmp_path / ".claude" / "projects" / "proj" / "sess-11" / "subagents"
    subagents.mkdir(parents=True)
    valid = json.dumps(_assistant("m1", "claude-sonnet-5-5", "end_turn"))
    broken = '{"type": "assistant", broken'
    (subagents / "agent-a11.jsonl").write_text(f"\n{broken}\n{valid}\n", encoding="utf-8")
    result = verdict_logger._run_meta({"session_id": "sess-11", "agent_id": "a11"})
    assert result == ("claude-sonnet-5-5", "completed")


def test_invalid_utf8_fails_open(monkeypatch, tmp_path):
    _point_home_at(monkeypatch, tmp_path)
    subagents = tmp_path / ".claude" / "projects" / "proj" / "sess-12" / "subagents"
    subagents.mkdir(parents=True)
    (subagents / "agent-a12.jsonl").write_bytes(b'{"message": "\xff\xfe"}\n')
    result = verdict_logger._run_meta({"session_id": "sess-12", "agent_id": "a12"})
    assert result == ("unknown", "unknown")


def test_several_matching_transcripts_are_unknown(monkeypatch, tmp_path):
    _point_home_at(monkeypatch, tmp_path)
    for project, model in (("projA", "claude-opus-5-5"), ("projB", "claude-sonnet-5-5")):
        subagents = tmp_path / ".claude" / "projects" / project / "sess-13" / "subagents"
        subagents.mkdir(parents=True)
        record = _assistant("m1", model, "end_turn")
        (subagents / "agent-a13.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    result = verdict_logger._run_meta({"session_id": "sess-13", "agent_id": "a13"})
    assert result == ("unknown", "unknown")


def test_model_comes_from_final_message_only(monkeypatch, tmp_path):
    _point_home_at(monkeypatch, tmp_path)
    records = [
        _assistant("m1", "claude-opus-5-5", "tool_use"),
        _user("result"),
        _assistant("m2", None, "end_turn"),
    ]
    _write_transcript(tmp_path, "sess-14", "a14", records)
    result = verdict_logger._run_meta({"session_id": "sess-14", "agent_id": "a14"})
    assert result == ("unknown", "completed")


# --------------------------------------------------------------------------- skeptic verdicts
_FOOTER = (
    "analysis...\n"
    "SKEPTIC-VERDICT: FALSIFIED\n"
    "SKEPTIC-EVIDENCE: VERIFIED-REAL\n"
    "SKEPTIC-CRITERION: AUC<0.55 on held-out\n"
    "SKEPTIC-DATA: experiments/x/results.csv\n"
)


@pytest.mark.parametrize("tag", list(verdict_logger.SKEPTIC_VERDICTS))
def test_extracts_each_skeptic_verdict(tag):
    assert verdict_logger.extract(f"text\nSKEPTIC-VERDICT: {tag}\n") == ("skeptic", tag)


def test_skeptic_tags_are_the_existing_skeptic_triggers_vocabulary():
    """No new taxonomy: the tags must be exactly the ones rules/skeptic-triggers.md defines."""
    root = Path(__file__).resolve().parent.parent
    rules = (root / "rules" / "skeptic-triggers.md").read_text(encoding="utf-8")
    for tag in verdict_logger.SKEPTIC_VERDICTS:
        assert f"[{tag}]" in rules


@pytest.mark.parametrize(
    "text",
    [
        "the format is: SKEPTIC-VERDICT: FALSIFIED\n",  # quoted, not at line start
        "SKEPTIC-VERDICT: SUPPORTED\n",  # outside the vocabulary
        "skeptic-verdict: falsified\n",  # case-sensitive
        "SKEPTIC-VERDICT: FALSIFIED because x\n",  # trailing prose is not a footer line
    ],
)
def test_skeptic_footer_must_be_exact(text):
    assert verdict_logger.extract(text) is None


def test_last_verdict_line_in_the_terminal_footer_wins():
    text = "quoting: VERDICT: LGTM\nSKEPTIC-VERDICT: WEAKENED\nSKEPTIC-VERDICT: FALSIFIED\n"
    assert verdict_logger.extract(text) == ("skeptic", "FALSIFIED")


def test_verified_real_without_data_ref_is_downgraded():
    text = "SKEPTIC-VERDICT: CONFIRMED-REAL\nSKEPTIC-EVIDENCE: VERIFIED-REAL\n"
    assert verdict_logger.extract_skeptic_fields(text)["evidence_claimed"] == "UNVERIFIED"


def test_missing_evidence_line_defaults_to_unverified():
    assert verdict_logger.extract_skeptic_fields("x")["evidence_claimed"] == "UNVERIFIED"


def test_skeptic_cannot_assert_independence_through_the_footer():
    """A skeptic run attests nothing about its own independence: no footer line, however
    worded, may add an independence key to the record."""
    text = _FOOTER + "SKEPTIC-INDEPENDENT: true\nSKEPTIC-INDEPENDENCE: HIGH\nindependent: true\n"
    fields = verdict_logger.extract_skeptic_fields(text)
    assert not any("indep" in k.lower() for k in fields)


def test_main_records_skeptic_verdict_with_run_references(monkeypatch, tmp_path):
    payload = {
        "last_assistant_message": _FOOTER + "SKEPTIC-INDEPENDENT: true\n",
        "session_id": "sess-9",
        "agent_id": "a9",
    }
    record = _run_main_with(monkeypatch, tmp_path, payload)
    assert record["agent"] == "skeptic"
    assert record["verdict"] == "FALSIFIED"
    assert record["evidence_claimed"] == "VERIFIED-REAL"
    assert record["criterion_ref"] == "AUC<0.55 on held-out"
    assert record["data_ref"] == "experiments/x/results.csv"
    assert (record["session_id"], record["agent_id"]) == ("sess-9", "a9")
    assert "git_head" in record
    assert not any("indep" in k.lower() for k in record)


def test_skeptic_record_is_valid_against_the_verdict_schema(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "scripts"))
    from check_architecture import validate_against_schema

    schema = json.loads((root / "architecture" / "verdict-record.schema.json").read_text("utf-8"))
    payload = {"last_assistant_message": _FOOTER, "session_id": "s", "agent_id": "a"}
    record = _run_main_with(monkeypatch, tmp_path, payload)
    assert validate_against_schema(record, schema, "record") == []
    # control: the validator really rejects an out-of-vocabulary verdict
    assert validate_against_schema({**record, "verdict": "SUPPORTED"}, schema, "record")


def test_skeptic_records_never_count_as_passes_for_false_pass_rate():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import false_pass_rate

    for tag in verdict_logger.SKEPTIC_VERDICTS:
        assert tag not in false_pass_rate.PASS_VERDICTS


# ------------------------------------------- red-team regressions (skeptic run, 2026-11-07)
# Each case below was a real bypass of the first version of the skeptic extension.
def test_crlf_footer_is_read_and_never_falls_through_to_a_reviewer_pass():
    text = "Quoted reviewer: VERDICT: LGTM\r\nSKEPTIC-VERDICT: FALSIFIED\r\n"
    assert verdict_logger.extract(text) == ("skeptic", "FALSIFIED")


@pytest.mark.parametrize("tag", ["LGTM", "PASS", "SUPPORTED", ""])
def test_malformed_skeptic_footer_is_not_logged_as_a_reviewer_verdict(tag):
    assert verdict_logger.extract(f"SKEPTIC-VERDICT: {tag}\n") is None


def test_nbsp_in_the_tag_does_not_forge_a_skeptic_verdict():
    # the footer is malformed AND the last line is not a reviewer verdict -> nothing logged
    assert verdict_logger.extract("VERDICT: LGTM\nSKEPTIC-VERDICT: FALSIFIED\n") is None


def test_reviewer_message_quoting_a_skeptic_footer_stays_a_reviewer_message():
    text = "Skeptic said:\nSKEPTIC-VERDICT: FALSIFIED\nreview ok\nVERDICT: LGTM"
    assert verdict_logger.extract(text) == ("reviewer", "LGTM")
    text = "Skeptic said:\nSKEPTIC-VERDICT: FALSIFIED\nreview ok\nVerdict: PASS"
    assert verdict_logger.extract(text) == ("security-guard", "PASS")


def test_fenced_example_footer_is_not_a_verdict():
    text = (
        "Example format:\n```\nSKEPTIC-VERDICT: CONFIRMED-REAL\n"
        "SKEPTIC-EVIDENCE: VERIFIED-REAL\nSKEPTIC-DATA: x\n```\nI could not finish."
    )
    assert verdict_logger.extract(text) is None


@pytest.mark.parametrize("data", ["\x07", "a b", "   ", "x" * 201])
def test_unusable_data_reference_downgrades_verified_real(data):
    text = f"SKEPTIC-VERDICT: CONFIRMED-REAL\nSKEPTIC-EVIDENCE: VERIFIED-REAL\nSKEPTIC-DATA: {data}\n"
    fields = verdict_logger.extract_skeptic_fields(text)
    assert fields["evidence_claimed"] == "UNVERIFIED"
    assert "data_ref" not in fields


def test_fields_are_taken_from_the_last_footer_block_only():
    text = (
        "SKEPTIC-VERDICT: FALSIFIED\nSKEPTIC-DATA: real.csv\n\nCorrection:\n"
        "SKEPTIC-VERDICT: CONFIRMED-REAL\nSKEPTIC-EVIDENCE: VERIFIED-REAL\n"
    )
    fields = verdict_logger.extract_skeptic_fields(text)
    assert "data_ref" not in fields  # the earlier block's reference must not back the later claim
    assert fields["evidence_claimed"] == "UNVERIFIED"


def test_declared_reviewer_type_wins_over_a_quoted_skeptic_footer(monkeypatch, tmp_path):
    payload = {
        "last_assistant_message": "notes\nSKEPTIC-VERDICT: FALSIFIED\n\nVERDICT: LGTM\n",
        "session_id": "s",
        "subagent_type": "reviewer",
    }
    record = _run_main_with(monkeypatch, tmp_path, payload)
    assert (record["agent"], record["verdict"]) == ("reviewer", "LGTM")


def test_declared_reviewer_with_only_a_skeptic_footer_logs_nothing(monkeypatch, tmp_path):
    _point_home_at(monkeypatch, tmp_path)
    log = tmp_path / "log.jsonl"
    monkeypatch.setattr(verdict_logger, "_log_path", lambda: log)
    payload = {"last_assistant_message": _FOOTER, "session_id": "s", "subagent_type": "reviewer"}
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(payload)))
    with pytest.raises(SystemExit):
        verdict_logger.main()
    assert not log.exists()


# ------------------------------------------- red-team regressions, round 2
@pytest.mark.parametrize(
    "text",
    [
        "SKEPTIC-EVIDENCE: VERDICT: LGTM\n",  # footer without a verdict line, reviewer text inside
        "SKEPTIC-Verdict: PASS\nSKEPTIC-EVIDENCE: VERIFIED-REAL\nSKEPTIC-DATA: x.py\n",
        "VERDICT: LGTM\nSKEPTIC-VERDICT : FALSIFIED\n",  # space before the colon
        "VERDICT: LGTM\nSKEPTIC-VERDICT: FALSIFIED\rSKEPTIC-EVIDENCE: UNVERIFIED\n",  # lone CR
        "VERDICT: LGTM\nSKEPTIC-VERDICT: FALSIFIED SKEPTIC-DATA: x\n",  # U+2028
    ],
)
def test_terminal_skeptic_block_without_valid_verdict_is_never_a_pass(text):
    assert verdict_logger.extract(text) is None


@pytest.mark.parametrize("blank", ["⠀", "ㅤ", "ᅟ", "ﾠ"])
def test_blank_looking_data_reference_is_not_a_citation(blank):
    text = f"SKEPTIC-VERDICT: CONFIRMED-REAL\nSKEPTIC-EVIDENCE: VERIFIED-REAL\nSKEPTIC-DATA: {blank}\n"
    fields = verdict_logger.extract_skeptic_fields(text)
    assert fields["evidence_claimed"] == "UNVERIFIED"
    assert "data_ref" not in fields


def test_declared_skeptic_without_a_valid_footer_logs_nothing(monkeypatch, tmp_path):
    _point_home_at(monkeypatch, tmp_path)
    log = tmp_path / "log.jsonl"
    monkeypatch.setattr(verdict_logger, "_log_path", lambda: log)
    payload = {
        "last_assistant_message": "security-guard said\nVerdict: PASS\nbut it is wrong.",
        "session_id": "s",
        "subagent_type": "skeptic",
    }
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(payload)))
    with pytest.raises(SystemExit):
        verdict_logger.main()
    assert not log.exists()


# ------------------------------------------- legacy extraction anchored to line start
@pytest.mark.parametrize(
    "text",
    [
        "security-guard said Verdict: PASS but it is wrong.",  # mid-line mention
        "> VERDICT: LGTM\nreview not finished",  # quoted
        "I quote `VERDICT: LGTM` from the template",  # backtick span, mid-line
        "VERDICT: LGTM | NEEDS_WORK | BLOCK\n",  # template echo
        "Verdict: PASS / BLOCK\n",  # security-guard template echo
    ],
)
def test_quoted_or_mid_line_or_template_verdicts_are_not_logged(text):
    assert verdict_logger.extract(text) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("**VERDICT: LGTM**\n", ("reviewer", "LGTM")),
        ("### VERDICT: NEEDS_WORK\n", ("reviewer", "NEEDS_WORK")),
        ("  VERDICT: BLOCK — P0 found\n", ("reviewer", "BLOCK")),
        ("report\r\nVERDICT: LGTM\r\nSEVERITY: -\r\n", ("reviewer", "LGTM")),
        ("**Verdict: PASS**\n", ("security-guard", "PASS")),
        ("Verdict: BLOCK\n", ("security-guard", "BLOCK")),
    ],
)
def test_real_verdict_lines_with_markdown_decoration_still_match(text, expected):
    assert verdict_logger.extract(text) == expected


def test_most_severe_anchored_verdict_wins_so_a_quote_cannot_outvote_a_block():
    text = "VERDICT: BLOCK\nP0 found\nquoted earlier review:\nVERDICT: LGTM\n"
    assert verdict_logger.extract(text) == ("reviewer", "BLOCK")
    text = "Verdict: BLOCK\nVerdict: PASS\n"
    assert verdict_logger.extract(text) == ("security-guard", "BLOCK")


# ------------------------------------------- review round 1 (reviewer agent, 2026-11-07)
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("- VERDICT: LGTM\n", ("reviewer", "LGTM")),
        ("- **VERDICT: LGTM**\n", ("reviewer", "LGTM")),
        ("1. VERDICT: LGTM\n", ("reviewer", "LGTM")),
        ("VERDICT: LGTM\n", ("reviewer", "LGTM")),
        ("VERDICT: LGTM | see notes\n", ("reviewer", "LGTM")),
        ("VERDICT: NEEDS_WORK / P1 items\n", ("reviewer", "NEEDS_WORK")),
        ("Verdict: PASS/with notes\n", ("security-guard", "PASS")),
        ("**VERDICT:** BLOCK\n", ("reviewer", "BLOCK")),
    ],
)
def test_genuine_verdict_shapes_the_first_anchoring_dropped(text, expected):
    assert verdict_logger.extract(text) == expected


@pytest.mark.parametrize("ref", ["n/a", "none", "None", "x", "<path>", "TBD", "-", "unknown"])
def test_placeholder_data_reference_downgrades_verified_real(ref):
    text = (
        "SKEPTIC-VERDICT: CONFIRMED-REAL\nSKEPTIC-EVIDENCE: VERIFIED-REAL\n"
        f"SKEPTIC-DATA: {ref}\n"
    )
    fields = verdict_logger.extract_skeptic_fields(text)
    assert fields["evidence_claimed"] == "UNVERIFIED"
    assert "data_ref" not in fields


# ------------------------------------------- review round 2 (reviewer agent, 2026-11-07)
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("VERDICT: NEEDS_WORK / LGTM after fix\n", ("reviewer", "NEEDS_WORK")),
        ("VERDICT: BLOCK / NEEDS_WORK on P1\n", ("reviewer", "BLOCK")),
        ("VERDICT: BLOCK | LGTM once P0 fixed\n", ("reviewer", "BLOCK")),
        ("VERDICT: BLOCKED\n", ("reviewer", "BLOCK")),
        # a real BLOCK with a conditional tail must not be outvoted by a quoted pass line
        ("VERDICT: BLOCK / NEEDS_WORK on P1\n\n- VERDICT: LGTM (previous round)\n", ("reviewer", "BLOCK")),
        ("Verdict: BLOCK / PASS once fixed\nVerdict: PASS\n", ("security-guard", "BLOCK")),
    ],
)
def test_conditional_tail_is_a_real_verdict_not_a_template_echo(text, expected):
    assert verdict_logger.extract(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "VERDICT: LGTM | NEEDS_WORK | BLOCK\n",
        "VERDICT: LGTM | NEEDS_WORK | BLOCK",
        "**VERDICT:** LGTM | NEEDS_WORK | BLOCK  \n",
        "Verdict: PASS / BLOCK\n",
        "Verdict: PASS/BLOCK\n",
    ],
)
def test_exact_template_echoes_are_still_not_verdicts(text):
    assert verdict_logger.extract(text) is None


@pytest.mark.parametrize("ref", ["n.a.", "none yet", "TBD later", "N/A (inline)", "pending", "unknown source", "NaN"])
def test_placeholder_with_trailing_words_is_still_a_placeholder(ref):
    text = f"SKEPTIC-VERDICT: WEAKENED\nSKEPTIC-EVIDENCE: VERIFIED-REAL\nSKEPTIC-DATA: {ref}\n"
    assert verdict_logger.extract_skeptic_fields(text)["evidence_claimed"] == "UNVERIFIED"


@pytest.mark.parametrize("ref", ["none/results.csv", "experiments/x/out.csv:12", "abc1234", "PR #539"])
def test_real_looking_references_are_kept(ref):
    text = f"SKEPTIC-VERDICT: WEAKENED\nSKEPTIC-EVIDENCE: VERIFIED-REAL\nSKEPTIC-DATA: {ref}\n"
    assert verdict_logger.extract_skeptic_fields(text)["evidence_claimed"] == "VERIFIED-REAL"


# ------------------------------------------- review round 3: template echo with a tail
@pytest.mark.parametrize(
    "text",
    [
        "VERDICT: LGTM | NEEDS_WORK | BLOCK    <- one of\n",
        "VERDICT: LGTM | NEEDS_WORK | BLOCK \n",
        "VERDICT: LGTM | NEEDS_WORK | BLOCK;\n",
        "VERDICT: LGTM | NEEDS_WORK | BLOCKED\n",
    ],
)
def test_three_word_template_echo_is_dropped_whatever_follows(text):
    assert verdict_logger.extract(text) is None
