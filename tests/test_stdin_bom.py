"""Hook stdin must tolerate the UTF-8 BOM that Cursor prepends on Windows.

Cursor 3.20.21 sends valid JSON preceded by ``EF BB BF`` (verified with a raw
stdin probe: BOM on 14/14 payloads, none empty). Text-mode ``json.load`` choked
on it, so every fail-closed PREVENT hook denied every Cursor tool call as
"Malformed tool_input JSON". These tests feed real BYTES through real
subprocesses, because the ``io.StringIO`` fakes used elsewhere never exercise
the byte-decoding path where the bug lived.

The other half of the contract matters as much: genuinely broken input must
STILL be denied. A BOM fix that also waved through garbage would be a bypass.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent / "hooks"
sys.path.insert(0, str(HOOKS))

from lib import runtime  # noqa: E402

BOM = b"\xef\xbb\xbf"
PAYLOAD = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}}).encode("utf-8")

# Hooks that deny on unparseable stdin. Each must accept a BOM-prefixed payload.
FAIL_CLOSED_HOOKS = [
    "pre_commit_guard.py",
    "input_guard.py",
    "pre_vault_write.py",
    "security_verify.py",
]


def _run(hook: str, stdin: bytes) -> subprocess.CompletedProcess[bytes]:
    env = {**os.environ, "PYTHONPATH": str(HOOKS)}
    env.pop("CLAUDE_INVOKED_BY", None)
    return subprocess.run(
        [sys.executable, str(HOOKS / hook)],
        input=stdin,
        capture_output=True,
        timeout=30,
        env=env,
        cwd=str(HOOKS.parent),
    )


def _denied_as_malformed(proc: subprocess.CompletedProcess[bytes]) -> bool:
    return b"Malformed tool_input JSON" in proc.stdout


class _FakeStdin:
    """Text stream with a .buffer, like the real sys.stdin."""

    def __init__(self, raw: bytes) -> None:
        self.buffer = io.BytesIO(raw)


@pytest.mark.parametrize("hook", FAIL_CLOSED_HOOKS)
class TestFailClosedHooksAcceptBom:
    def test_bom_payload_is_not_malformed(self, hook: str) -> None:
        proc = _run(hook, BOM + PAYLOAD)
        assert not _denied_as_malformed(proc), proc.stdout.decode("utf-8", "replace")

    def test_plain_payload_is_not_malformed(self, hook: str) -> None:
        proc = _run(hook, PAYLOAD)
        assert not _denied_as_malformed(proc), proc.stdout.decode("utf-8", "replace")

    def test_empty_stdin_still_denied(self, hook: str) -> None:
        # security_verify asks rather than denies; both mention the malformed input.
        proc = _run(hook, b"")
        assert b"alformed" in proc.stdout, proc.stdout.decode("utf-8", "replace")

    def test_garbage_stdin_still_denied(self, hook: str) -> None:
        proc = _run(hook, BOM + b"this is not json")
        assert b"alformed" in proc.stdout, proc.stdout.decode("utf-8", "replace")

    def test_bom_alone_still_denied(self, hook: str) -> None:
        proc = _run(hook, BOM)
        assert b"alformed" in proc.stdout, proc.stdout.decode("utf-8", "replace")


class TestReadStdinText:
    def test_strips_one_leading_bom_from_bytes(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "stdin", _FakeStdin(BOM + b'{"a": 1}'))
        assert runtime.read_stdin_text() == '{"a": 1}'

    def test_only_one_bom_is_stripped(self, monkeypatch) -> None:
        # A second BOM is not valid JSON whitespace and must stay visible so
        # the parser rejects it, rather than being silently swallowed.
        monkeypatch.setattr(sys, "stdin", _FakeStdin(BOM + BOM + b"{}"))
        assert runtime.read_stdin_text().startswith("\ufeff")

    def test_no_bom_untouched(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "stdin", _FakeStdin(b'{"a": 1}'))
        assert runtime.read_stdin_text() == '{"a": 1}'

    def test_utf8_non_ascii_decoded_as_utf8(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "stdin", _FakeStdin('{"q": "тест"}'.encode()))
        assert json.loads(runtime.read_stdin_text()) == {"q": "тест"}

    def test_invalid_utf8_raises_value_error(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "stdin", _FakeStdin(b'{"a": "\xff\xfe"}'))
        with pytest.raises(ValueError):
            runtime.read_stdin_text()

    def test_text_stream_without_buffer_strips_bom(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO("\ufeff" + '{"a": 1}'))
        assert runtime.read_stdin_text() == '{"a": 1}'


class TestParseStdin:
    def test_strict_parses_bom_payload(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "stdin", _FakeStdin(BOM + PAYLOAD))
        assert runtime.parse_stdin(strict=True)["tool_name"] == "Bash"

    def test_strict_still_raises_on_garbage(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "stdin", _FakeStdin(BOM + b"nope"))
        with pytest.raises(runtime.HookInputError):
            runtime.parse_stdin(strict=True)

    def test_strict_still_raises_on_invalid_utf8(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "stdin", _FakeStdin(b"\xff\xfe{}"))
        with pytest.raises(runtime.HookInputError):
            runtime.parse_stdin(strict=True)

    def test_lenient_returns_empty_dict_on_garbage(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "stdin", _FakeStdin(BOM + b"nope"))
        assert runtime.parse_stdin() == {}

    def test_raw_variant_parses_bom_payload(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "stdin", _FakeStdin(BOM + PAYLOAD))
        assert runtime.parse_stdin_raw()["tool_name"] == "Bash"
