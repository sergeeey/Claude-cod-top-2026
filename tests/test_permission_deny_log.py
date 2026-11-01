"""permission_policy writes one telemetry row per deny, and never the command text.

Context: the solo profile emits only "deny", and hook_triggers.jsonl had no deny
rows for this hook, so its false-positive rate could not be measured. These
tests pin the new telemetry without changing a single verdict.
"""

from __future__ import annotations

import io
import json
import sys

import permission_policy as pp
import pytest

SECRET = "SECRET_TOKEN_abc123xyz"


@pytest.fixture
def calls(monkeypatch):
    recorded: list[dict] = []

    def fake_log(**kwargs):
        recorded.append(kwargs)

    monkeypatch.setattr(pp, "log_hook_trigger", fake_log)
    return recorded


def _run_main(monkeypatch, capsys, command: str) -> str:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "session_id": "s-1"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    try:
        pp.main()
    except SystemExit:
        pass
    return capsys.readouterr().out


class TestDenyIsLogged:
    def test_dangerous_deny_logs_one_row_without_command(self, monkeypatch, capsys, calls):
        command = f"rm -rf /tmp/x && echo {SECRET}"
        out = _run_main(monkeypatch, capsys, command)
        assert json.loads(out.strip())["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert len(calls) == 1
        row = calls[0]
        assert row["hook_name"] == "permission_policy"
        assert row["trigger_type"] == "dangerous_command"
        assert row["action"] == "block"
        assert row["session_id"] == "s-1"
        # Case-insensitive: the hook matches on lowercased text, so a regression
        # that logged the lowercased command would pass a case-sensitive check.
        assert SECRET.lower() not in json.dumps(row).lower()

    def test_allow_writes_no_row(self, monkeypatch, capsys, calls):
        _run_main(monkeypatch, capsys, "git status")
        assert calls == []

    def test_ask_writes_no_row(self, monkeypatch, capsys, calls):
        out = _run_main(monkeypatch, capsys, "git status && git diff")
        assert out.strip() == ""
        assert calls == []

    @pytest.mark.parametrize(
        "exc",
        [OSError("disk full"), ValueError("bad sample"), TypeError("bad session_id")],
    )
    def test_logging_failure_does_not_change_the_deny(self, monkeypatch, capsys, exc):
        # WHY three types: log_hook_trigger catches only OSError itself, so a
        # ValueError or TypeError from it must still be caught by _log_deny.
        def broken(**kwargs):
            raise exc

        monkeypatch.setattr(pp, "log_hook_trigger", broken)
        out = _run_main(monkeypatch, capsys, "sudo apt install nginx")
        assert json.loads(out.strip())["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_sensitive_escalation_logs_without_path_text(self, monkeypatch, capsys, calls):
        command = f"cat .env # {SECRET}"
        # Precondition: this really is the ask-then-escalate branch, not a vacuous pass.
        assert pp.decide("Bash", {"command": command})[0] == "ask"
        assert pp._names_a_sensitive_path(command.lower().strip())
        out = _run_main(monkeypatch, capsys, command)
        assert json.loads(out.strip())["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert len(calls) == 1
        assert calls[0]["trigger_type"] == "sensitive_path_escalation"
        assert SECRET.lower() not in json.dumps(calls[0]).lower()


def test_no_dangerous_pattern_resembles_a_secret():
    """The deny message, which goes into the telemetry sample, is built from
    DANGEROUS_PATTERNS. A secret-shaped entry there would leak into the log, so
    this pins that no entry looks like a real credential token."""
    import re

    secret_shapes = re.compile(
        r"(sk-[A-Za-z0-9_\-]{8,}|ghp_[A-Za-z0-9]{8,}|AKIA[0-9A-Z]{8,}"
        r"|xox[abprs]-[A-Za-z0-9\-]{8,}|BEGIN [A-Z ]*PRIVATE KEY)"
    )
    for pattern in pp.DANGEROUS_PATTERNS:
        assert not secret_shapes.search(pattern), f"pattern looks like a secret: {pattern[:20]}"


@pytest.fixture
def real_log(monkeypatch, tmp_path):
    """The REAL log_hook_trigger, writing to a temp file. Exercises the sample
    field, the session_id field and the CLAUDE_INVOKED_BY guard, which the mocked
    tests above cannot see. Redaction runs on `sample` only: session_id is
    written as is (the harness supplies it, not the model), and no test here
    checks redaction of it."""
    import lib.state as state

    path = tmp_path / "hook_triggers.jsonl"
    monkeypatch.setattr(state, "HOOK_TRIGGERS_LOG", path)
    monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
    return path


def _rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_real_log_row_has_no_secret_and_keeps_session_id(monkeypatch, capsys, real_log):
    out = _run_main(monkeypatch, capsys, f"rm -rf /tmp/x && echo {SECRET.upper()}")
    assert json.loads(out.strip())["hookSpecificOutput"]["permissionDecision"] == "deny"
    rows = _rows(real_log)
    assert len(rows) == 1
    assert rows[0]["hook"] == "permission_policy"
    assert rows[0]["action"] == "block"
    assert rows[0]["session_id"] == "s-1"
    assert SECRET.lower() not in real_log.read_text(encoding="utf-8").lower()


def test_nested_run_writes_no_row_but_still_denies(monkeypatch, capsys, real_log):
    # Documented limit: the logger skips nested runs. The deny itself must not change.
    monkeypatch.setenv("CLAUDE_INVOKED_BY", "agent")
    out = _run_main(monkeypatch, capsys, "rm -rf /tmp/x")
    assert json.loads(out.strip())["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert _rows(real_log) == []


def test_sensitive_config_read_deny_is_logged(monkeypatch, capsys, calls):
    tool_input = {"file_path": "C:/work/.mcp.json"}
    # Precondition: this really is the Read branch that logs as sensitive_config_read.
    assert pp.decide("Read", tool_input)[0] == "deny"
    payload = {"tool_name": "Read", "tool_input": tool_input, "session_id": "s-2"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    try:
        pp.main()
    except SystemExit:
        pass
    out = capsys.readouterr().out
    assert json.loads(out.strip())["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert len(calls) == 1
    assert calls[0]["trigger_type"] == "sensitive_config_read"


def test_decision_is_printed_before_the_log_call(monkeypatch, capsys):
    # Pins the ORDER, which the other tests do not: the deny must already be on
    # stdout at the moment the telemetry call happens. Swapping emit and log
    # would leave every other test green, so this one fails in that case.
    seen = {}

    def fake_log(**kwargs):
        seen["stdout_at_log"] = capsys.readouterr().out

    monkeypatch.setattr(pp, "log_hook_trigger", fake_log)
    payload = {"tool_name": "Bash", "tool_input": {"command": "rm -rf /tmp/x"}, "session_id": "s-3"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    try:
        pp.main()
    except SystemExit:
        pass
    assert "permissionDecision" in seen["stdout_at_log"]
    assert "deny" in seen["stdout_at_log"]


def test_closed_stdout_on_flush_does_not_escape(monkeypatch, calls):
    # A broken stdout must not raise out of main(): the flush sits inside the
    # telemetry try block, so the failure is absorbed there.
    class BrokenFlush(io.StringIO):
        def flush(self):
            raise ValueError("I/O operation on closed file")

    monkeypatch.setattr(sys, "stdout", BrokenFlush())
    payload = {"tool_name": "Bash", "tool_input": {"command": "rm -rf /tmp/x"}, "session_id": "s-4"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    try:
        pp.main()
    except SystemExit:
        pass
    # The row is skipped when stdout is broken; the verdict was already printed.
    assert calls == []


def test_escalation_decision_is_printed_before_the_log_call(monkeypatch, capsys):
    # Same ORDER pin as the deny branch, for the ask-then-escalate branch, which
    # the earlier order test does not cover.
    command = "cat .env"
    assert pp.decide("Bash", {"command": command})[0] == "ask"
    assert pp._names_a_sensitive_path(command.lower().strip())
    seen = {}

    def fake_log(**kwargs):
        seen["stdout_at_log"] = capsys.readouterr().out

    monkeypatch.setattr(pp, "log_hook_trigger", fake_log)
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "session_id": "s-5"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    try:
        pp.main()
    except SystemExit:
        pass
    assert "permissionDecision" in seen["stdout_at_log"]
    assert "deny" in seen["stdout_at_log"]
