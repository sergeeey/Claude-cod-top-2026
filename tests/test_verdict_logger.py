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
