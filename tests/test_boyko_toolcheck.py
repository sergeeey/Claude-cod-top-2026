"""Tests for skills/extensions/boyko-toolcheck: readiness levels, run classification, redaction.

Regression cases follow the audit №10 list: CLI missing, version works but auth missing,
empty output, timeout, and exit 0 with an error payload.
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "extensions" / "boyko-toolcheck"


@pytest.fixture(scope="module")
def tc():
    spec = importlib.util.spec_from_file_location(
        "toolcheck", SKILL_DIR / "scripts" / "toolcheck.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- redaction -----------------------------------------------------------------------


def test_redacts_token_and_password_values(tc):
    text = "api_key=abc123secret token: xyz987 password=hunter2"
    out = tc.redact(text)
    assert "abc123secret" not in out and "xyz987" not in out and "hunter2" not in out
    assert out.count("[REDACTED]") == 3


def test_redacts_authorization_header_and_sk_keys(tc):
    assert "[REDACTED]" in tc.redact("Authorization: Bearer eyJhbGciOi.payload")
    assert "sk-AbCdEf123456" not in tc.redact("key sk-AbCdEf123456 used")


def test_redacts_user_home_path_keeps_codes_and_versions(tc):
    out = tc.redact(r"config at C:\Users\serge\.codex\config.toml exit 2 version 0.42.1")
    assert "serge" not in out
    assert "exit 2" in out and "0.42.1" in out


# --- run classification (regression cases) -----------------------------------------


def test_cli_missing(tc):
    assert tc.classify_run(None, "", timed_out=False, not_found=True) == "NOT_FOUND"


def test_version_ok_is_only_a_start_pass(tc):
    assert tc.classify_run(0, "codex 0.42.1", timed_out=False, not_found=False) == "PASS"


def test_empty_output_is_fail(tc):
    assert tc.classify_run(0, "   \n", timed_out=False, not_found=False) == "FAIL"


def test_timeout_is_timeout(tc):
    assert tc.classify_run(None, "", timed_out=True, not_found=False) == "TIMEOUT"


def test_exit_zero_with_error_payload_is_fail(tc):
    assert (
        tc.classify_run(0, '{"error": "not logged in"}', timed_out=False, not_found=False) == "FAIL"
    )


def test_nonzero_exit_is_fail(tc):
    assert tc.classify_run(2, "boom", timed_out=False, not_found=False) == "FAIL"


# --- readiness levels ----------------------------------------------------------------


def test_start_only_is_partial_not_pass(tc):
    result = tc.overall({"DISCOVERED": "PASS", "STARTS": "PASS"}, "CLI_START_OK")
    assert result["overall"] == "PARTIAL"
    assert result["reached"] == "STARTS"
    assert result["errors"] == []


def test_all_levels_pass_is_pass(tc):
    checks = {lvl: "PASS" for lvl in tc.LEVELS}
    result = tc.overall(checks, "WORKFLOW_OK: WORKFLOW_READY reached")
    assert result["overall"] == "PASS"
    assert result["reached"] == "WORKFLOW_READY"


def test_failed_auth_stops_the_ladder(tc):
    checks = {"DISCOVERED": "PASS", "STARTS": "PASS", "AUTHENTICATED": "FAIL"}
    result = tc.overall(checks, "CLI_START_OK")
    assert result["reached"] == "STARTS"
    assert result["overall"] == "PARTIAL"


def test_claim_above_reached_level_is_an_error(tc):
    result = tc.overall({"DISCOVERED": "PASS", "STARTS": "PASS"}, "AUTHENTICATED: auth ok")
    assert result["overall"] == "PARTIAL"
    assert any("claim names AUTHENTICATED" in e for e in result["errors"])


def test_nothing_reached_is_fail(tc):
    result = tc.overall({"DISCOVERED": "FAIL"}, "found")
    assert result["overall"] == "FAIL"
    assert result["reached"] is None


def test_tool_report_redacts_command_and_evidence(tc):
    rep = tc.tool_report(
        "codex",
        "codex login --token sk-AbCdEf123456",
        {"STARTS": "PASS"},
        r"C:\Users\serge\.codex ok",
    )
    assert "sk-AbCdEf123456" not in rep["command"]
    assert "serge" not in rep["evidence"]
