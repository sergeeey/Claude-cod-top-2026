"""session_id in the deny telemetry row is redacted, then capped, and ordinary ids are kept.

Kept in its own file so the existing deny-log tests stay untouched. Uses the REAL
log_hook_trigger writer on a temp file, so the value that reaches disk is checked.
"""

from __future__ import annotations

import io
import json

import permission_policy as pp
import pytest

DENY_COMMAND = "rm -rf /tmp/x"


@pytest.fixture
def real_log(monkeypatch, tmp_path):
    import lib.state as state

    path = tmp_path / "hook_triggers.jsonl"
    monkeypatch.setattr(state, "HOOK_TRIGGERS_LOG", path)
    monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
    return path


def _rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _run_with_session(monkeypatch, capsys, session_id: str) -> str:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": DENY_COMMAND},
        "session_id": session_id,
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    try:
        pp.main()
    except SystemExit:
        pass
    return capsys.readouterr().out


def test_session_id_is_redacted_then_capped_in_the_real_row(monkeypatch, capsys, real_log):
    # session_id is supplied by the harness, not the model, and was never redacted
    # before. A secret shape in it would reach the telemetry file. Redaction runs
    # first, then the cap, so a cut cannot leave part of a token behind.
    _run_with_session(monkeypatch, capsys, "sk-" + "a" * 40)
    _run_with_session(monkeypatch, capsys, "x" * 300)
    rows = _rows(real_log)
    assert len(rows) == 2
    assert "a" * 40 not in rows[0]["session_id"]
    assert rows[0]["session_id"] != ""
    assert len(rows[1]["session_id"]) == 128


def test_normal_session_id_is_kept_unchanged(monkeypatch, capsys, real_log):
    # Redaction must not mangle an ordinary session id, or the row can no longer be
    # joined to its session.
    sid = "3cc01ee2-47e2-4493-a59f-1ea6a5c0f39d"
    _run_with_session(monkeypatch, capsys, sid)
    rows = _rows(real_log)
    assert len(rows) == 1
    assert rows[0]["session_id"] == sid


def test_uuid_that_redact_secrets_would_alter_is_kept(monkeypatch, capsys, real_log):
    # 0.5% of random UUIDs contain a digit run that the card or phone patterns match
    # (verified: c6785a5c-48db-4d56-8289-6207468cee34 becomes [REDACTED-PHONE]).
    # The exemption must cover exactly this shape, or the row loses its session.
    sid = "c6785a5c-48db-4d56-8289-6207468cee34"
    assert pp.redact_secrets(sid) != sid
    _run_with_session(monkeypatch, capsys, sid)
    rows = _rows(real_log)
    assert rows[0]["session_id"] == sid


def test_secret_crossing_the_128_cut_is_redacted_before_capping(monkeypatch, capsys, real_log):
    # Cap-first would keep "sk-" and five a's, which no redaction pattern matches.
    # Redact-first removes the whole token, so no "sk-" fragment survives the cut.
    _run_with_session(monkeypatch, capsys, "y" * 120 + "sk-" + "a" * 40)
    rows = _rows(real_log)
    assert len(rows[0]["session_id"]) <= 128
    assert "sk-" not in rows[0]["session_id"]


def test_redaction_failure_does_not_change_the_deny(monkeypatch, capsys, real_log):
    # session_id handling sits inside _log_deny's try, so an exception from the
    # redactor must be absorbed and the deny must still be printed.
    def broken(text):
        raise RuntimeError("redactor failed")

    monkeypatch.setattr(pp, "redact_secrets", broken)
    out = _run_with_session(monkeypatch, capsys, "sk-" + "a" * 40)
    assert json.loads(out.strip())["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_non_string_session_id_does_not_break_the_hook(monkeypatch, capsys, real_log):
    out = _run_with_session(monkeypatch, capsys, 12345)
    assert json.loads(out.strip())["hookSpecificOutput"]["permissionDecision"] == "deny"
    rows = _rows(real_log)
    assert rows[0]["session_id"] == "12345"


def test_missing_session_id_is_written_as_empty(monkeypatch, capsys, real_log):
    # A payload without session_id must not crash the hook or leave a null in the row.
    payload = {"tool_name": "Bash", "tool_input": {"command": DENY_COMMAND}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    try:
        pp.main()
    except SystemExit:
        pass
    capsys.readouterr()
    rows = _rows(real_log)
    assert rows[0]["session_id"] == ""


def test_uppercase_uuid_is_kept(monkeypatch, capsys, real_log):
    # The exemption is case-insensitive hex, so an upper-case UUID is not altered.
    sid = "C6785A5C-48DB-4D56-8289-6207468CEE34"
    _run_with_session(monkeypatch, capsys, sid)
    rows = _rows(real_log)
    assert rows[0]["session_id"] == sid
