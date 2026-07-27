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
import verdict_logger  # noqa: E402


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
