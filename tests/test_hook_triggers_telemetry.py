"""Unit tests for log_hook_trigger() — hook telemetry layer.

WHY: log_hook_trigger writes to ~/.claude/logs/hook_triggers.jsonl. Without
tests we cannot prove (a) the file format is JSONL-parseable, (b) recursion
guard stops subagent double-counting, (c) failures are silent. These three
properties are the contract every consumer (dashboard, Habr metric claims,
precision/recall computation) depends on.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from utils import log_hook_trigger, redact_secrets


@pytest.fixture
def tmp_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect HOOK_TRIGGERS_LOG to tmp dir for isolation per test."""
    log_path = tmp_path / "hook_triggers.jsonl"
    monkeypatch.setattr("utils.HOOK_TRIGGERS_LOG", log_path)
    # WHY: clear CLAUDE_INVOKED_BY so tests don't get short-circuited by
    # a parent run env. Restored automatically after each test.
    monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
    return log_path


class TestLogFormat:
    """Trigger entries must be valid JSONL with all required fields."""

    def test_writes_valid_jsonl(self, tmp_log: Path) -> None:
        log_hook_trigger("vtg", "perfect_score", "warning", "F1=1.000", "abc-123")
        line = tmp_log.read_text(encoding="utf-8").strip()
        entry = json.loads(line)  # raises if malformed
        assert entry["hook"] == "vtg"
        assert entry["trigger"] == "perfect_score"
        assert entry["action"] == "warning"
        assert entry["sample"] == "F1=1.000"
        assert entry["session_id"] == "abc-123"
        assert "ts" in entry

    def test_appends_multiple_entries(self, tmp_log: Path) -> None:
        log_hook_trigger("vtg", "perfect_score", "warning", "first")
        log_hook_trigger("evidence_guard", "missing_marker", "warning", "second")
        lines = tmp_log.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        # Each line is independently parseable — the JSONL contract.
        first = json.loads(lines[0])
        second = json.loads(lines[1])
        assert first["hook"] == "vtg"
        assert second["hook"] == "evidence_guard"

    def test_truncates_long_sample(self, tmp_log: Path) -> None:
        # WHY: we promised <=200 chars in the function docstring. If a hook
        # accidentally feeds the entire tool output, log_hook_trigger must
        # protect us via sanitize_text, otherwise log files explode.
        long_sample = "x" * 10_000
        log_hook_trigger("vtg", "perfect_score", "warning", long_sample)
        entry = json.loads(tmp_log.read_text(encoding="utf-8").strip())
        # sanitize_text appends "..." when truncating, so length is 200 + ellipsis.
        assert len(entry["sample"]) <= 220


class TestRecursionGuard:
    """CLAUDE_INVOKED_BY env var must short-circuit logging."""

    def test_skips_when_invoked_by_set(
        self, tmp_log: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # WHY: when Claude SDK invokes a subagent, parent's hooks may fire
        # again on subagent output. Without recursion guard we double-count.
        monkeypatch.setenv("CLAUDE_INVOKED_BY", "parent-session")
        log_hook_trigger("vtg", "perfect_score", "warning", "should not log")
        # File should not exist (or be empty) — nothing was written.
        assert not tmp_log.exists() or tmp_log.read_text() == ""

    def test_logs_when_invoked_by_unset(self, tmp_log: Path) -> None:
        # tmp_log fixture already deletes CLAUDE_INVOKED_BY.
        log_hook_trigger("vtg", "perfect_score", "warning", "should log")
        assert tmp_log.exists() and tmp_log.read_text().strip() != ""


class TestSilentFailure:
    """OSError must never propagate — telemetry is non-essential."""

    def test_silent_on_oserror(self, tmp_log: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # WHY: simulate a read-only logs dir. Hook MUST keep running and
        # MUST NOT raise, because telemetry is best-effort. Hooks that crash
        # would break tool calls — exactly the bug we promised to avoid.
        def boom(*_args: object, **_kwargs: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr("builtins.open", boom)
        # No assertion needed — the contract is "does not raise".
        log_hook_trigger("vtg", "perfect_score", "warning", "sample")

    def test_creates_logs_dir_if_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        nested = tmp_path / "deeply" / "nested" / "logs" / "hook_triggers.jsonl"
        monkeypatch.setattr("utils.HOOK_TRIGGERS_LOG", nested)
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        log_hook_trigger("vtg", "perfect_score", "warning", "sample")
        # Both dirs and file must exist now.
        assert nested.exists()
        assert nested.parent.is_dir()


class TestRealUseCases:
    """Smoke tests reflecting how the three real hooks call the function."""

    def test_validation_theater_perfect_score_call(self, tmp_log: Path) -> None:
        # Mirrors validation_theater_guard.main() invocation shape.
        log_hook_trigger(
            hook_name="validation_theater_guard",
            trigger_type="perfect_score",
            action="warning",
            sample="Triggered by: F1\\s*=\\s*1\\.000",
            session_id="session-abc",
        )
        entry = json.loads(tmp_log.read_text(encoding="utf-8").strip())
        assert entry["hook"] == "validation_theater_guard"
        assert entry["trigger"] == "perfect_score"

    def test_input_guard_block_call(self, tmp_log: Path) -> None:
        # Mirrors input_guard.main() block path.
        log_hook_trigger(
            hook_name="input_guard",
            trigger_type="prompt_injection_high",
            action="block",
            sample="tool=mcp__github__create_issue categories=['system_override'] matches=2",
            session_id="session-xyz",
        )
        entry = json.loads(tmp_log.read_text(encoding="utf-8").strip())
        assert entry["action"] == "block"
        assert "system_override" in entry["sample"]

    def test_evidence_guard_warning_call(self, tmp_log: Path) -> None:
        # Mirrors evidence_guard.main() invocation shape.
        log_hook_trigger(
            hook_name="evidence_guard",
            trigger_type="missing_evidence_marker",
            action="warning",
            sample="claims=4 | Python 3.12 is required and pytest must be installed",
            session_id="session-def",
        )
        entry = json.loads(tmp_log.read_text(encoding="utf-8").strip())
        assert entry["hook"] == "evidence_guard"
        assert "claims=4" in entry["sample"]


# WHY: secrets in tool output (Bash stderr, MCP responses) must never reach
# the on-disk telemetry log. These tests pin the contract so a future change
# to redact_secrets that loosens patterns will fail loudly here.
class TestSecretRedaction:
    """redact_secrets() must scrub common credential shapes."""

    @pytest.mark.parametrize(
        "raw,must_not_contain",
        [
            ("AKIAIOSFODNN7EXAMPLE in error log", "AKIAIOSFODNN7EXAMPLE"),
            ("export aws_secret_access_key=wJalrXUtnFEMIK7MDENG", "wJalrXUtnFEMIK7MDENG"),
            ("api call sk-proj-abc123def456ghi789jkl mock", "sk-proj-abc123def456ghi789jkl"),
            (
                "anthropic sk-ant-api03-Q9vRk7T5_aBcDeFgHiJkLm dump",
                "sk-ant-api03-Q9vRk7T5_aBcDeFgHiJkLm",
            ),
            (
                "token ghp_1234567890abcdef1234567890abcdef1234 leak",
                "ghp_1234567890abcdef1234567890abcdef1234",
            ),
            ("slack xoxb-12345-abcdef-token123456 here", "xoxb-12345-abcdef-token123456"),
            ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.x.y", "eyJhbGciOiJIUzI1NiJ9"),
            ("DATABASE_PASSWORD=hunter2 in .env", "hunter2"),
            ("MY_API_TOKEN=ghu_secretvalue12345", "ghu_secretvalue12345"),
        ],
    )
    def test_redacts_known_shapes(self, raw: str, must_not_contain: str) -> None:
        # WHY: pinning by NOT containing the original — pattern set will grow,
        # and we don't want to hand-pick every replacement format.
        result = redact_secrets(raw)
        assert must_not_contain not in result, (
            f"Secret {must_not_contain!r} survived redaction in: {result!r}"
        )

    def test_redacts_jwt(self) -> None:
        # JWT pattern needs explicit test — three base64 segments separated by dots.
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ.SflKxw"
        result = redact_secrets(f"sent {jwt} to api")
        assert "[REDACTED-JWT]" in result
        assert jwt not in result

    def test_preserves_non_secret_content(self) -> None:
        # WHY: regression guard — overzealous redaction would scrub legit logs.
        clean = "F1=1.000 detected on test_data with 100% accuracy"
        assert redact_secrets(clean) == clean

    def test_log_hook_trigger_redacts_in_pipeline(self, tmp_log: Path) -> None:
        # End-to-end: caller passes raw output, on-disk entry must be safe.
        log_hook_trigger(
            hook_name="evidence_guard",
            trigger_type="missing_evidence_marker",
            action="warning",
            sample="error: AWS_SECRET_KEY=AKIAIOSFODNN7EXAMPLE leaked",
            session_id="s1",
        )
        entry = json.loads(tmp_log.read_text(encoding="utf-8").strip())
        assert "AKIAIOSFODNN7EXAMPLE" not in entry["sample"]
        # Either the env-var pattern or the AKIA pattern (or both) must catch it.
        assert "REDACTED" in entry["sample"]
