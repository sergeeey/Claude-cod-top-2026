"""Tests for skills/extensions/boyko-preflight/scripts/validate_preflight.py (audit №5).

Pins the status contract: self-report stops at VISIBLE; EXECUTED needs an event id that
the events log confirms; FOLLOWED needs a behavioural test; an overall PASS must match.
"""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "extensions"
    / "boyko-preflight"
    / "scripts"
    / "validate_preflight.py"
)


@pytest.fixture(scope="module")
def vp():
    spec = importlib.util.spec_from_file_location("validate_preflight", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def good_checks() -> list[dict]:
    return [
        {"name": "rules", "status": "visible", "evidence": "integrity.md, security.md"},
        {
            "name": "project_classifier",
            "status": "executed",
            "evidence": {"event_id": "evt-100"},
        },
        {
            "name": "rule_followed",
            "status": "followed",
            "evidence": "answer cites the Evidence Marker rule",
            "behavioral_test": "asked for an unverified number; agent marked it [UNKNOWN]",
        },
    ]


def report(checks: list[dict], overall: str = "pass") -> dict:
    return {"session_id": "s-1", "checks": checks, "overall": overall}


def test_consistent_pass_report_has_no_errors(vp):
    errors = vp.validate(report(good_checks()), {"evt-100"})
    assert errors == []


def test_executed_event_missing_from_log_is_rejected(vp):
    errors = vp.validate(report(good_checks()), {"evt-999"})
    assert any("not found in the events log" in e for e in errors)


def test_executed_without_event_id_is_rejected(vp):
    checks = good_checks()
    checks[1] = {"name": "project_classifier", "status": "executed", "evidence": "seen"}
    errors = vp.validate(report(checks, "partial"), None)
    assert any("requires evidence.event_id" in e for e in errors)


def test_followed_without_behavioral_test_is_rejected(vp):
    checks = good_checks()
    checks[2] = {"name": "rule_followed", "status": "followed", "evidence": "I followed it"}
    errors = vp.validate(report(checks), None)
    assert any("a self-report gives at most visible" in e for e in errors)


def test_visible_without_quote_is_rejected(vp):
    checks = good_checks()
    checks[0] = {"name": "rules", "status": "visible", "evidence": ""}
    errors = vp.validate(report(checks), None)
    assert any("visible requires a quoted line" in e for e in errors)


def test_unknown_requires_reason(vp):
    checks = good_checks()
    checks[2] = {"name": "rule_followed", "status": "unknown"}
    errors = vp.validate(report(checks, "partial"), None)
    assert any("requires a non-empty 'reason'" in e for e in errors)


def test_invalid_status_is_rejected(vp):
    checks = good_checks()
    checks[0] = {"name": "rules", "status": "PASS", "evidence": "x"}
    errors = vp.validate(report(checks), None)
    assert any("unknown status 'PASS'" in e for e in errors)


def test_rule_not_visible_cannot_be_pass(vp):
    checks = good_checks()
    checks[0] = {"name": "rules", "status": "not_visible", "reason": "no rules block in prompt"}
    errors = vp.validate(report(checks, "pass"), {"evt-100"})
    assert any("overall is 'pass', but the checks give 'fail'" in e for e in errors)


def test_broken_mcp_gives_fail(vp):
    checks = good_checks()
    checks.append({"name": "obsidian", "status": "broken", "reason": "server no longer available"})
    assert vp.validate(report(checks, "fail"), {"evt-100"}) == []


def test_hook_disabled_is_not_executed(vp):
    checks = good_checks()
    checks[1] = {
        "name": "project_classifier",
        "status": "unknown",
        "reason": "no SessionStart output in context; hook may be disabled",
    }
    errors = vp.validate(report(checks, "partial"), {"evt-100"})
    assert errors == []


def test_overall_mismatch_is_rejected(vp):
    errors = vp.validate(report(good_checks(), "partial"), {"evt-100"})
    assert any("overall is 'partial'" in e for e in errors)


def test_session_id_required(vp):
    data = report(good_checks())
    data["session_id"] = ""
    errors = vp.validate(data, {"evt-100"})
    assert any("session_id is required" in e for e in errors)


def test_load_event_ids_skips_bad_lines(vp, tmp_path):
    log = tmp_path / "events.jsonl"
    log.write_text('{"event_id": "a1"}\nnot json\n\n{"event_id": 7}\n', encoding="utf-8")
    assert vp.load_event_ids(log) == {"a1", "7"}


def test_main_exit_codes(vp, tmp_path, monkeypatch, capsys):
    events = tmp_path / "events.jsonl"
    events.write_text('{"event_id": "evt-100"}\n', encoding="utf-8")

    good = tmp_path / "good.json"
    good.write_text(json.dumps(report(good_checks())), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["validate_preflight.py", str(good), "--events", str(events)])
    assert vp.main() == 0

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(report(good_checks(), "partial")), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["validate_preflight.py", str(bad)])
    assert vp.main() == 1
    assert "ERRORS" in capsys.readouterr().out


SKILL_MD = SCRIPT.parent.parent / "SKILL.md"


def test_skill_names_global_claude_md_explicitly():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "глобального ~/.claude/CLAUDE.md" in text
    assert "источник правил не найден" in text


def test_skill_documents_four_statuses():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "## Статусы: четыре разных вопроса" in text
    for status in ("INSTALLED", "VISIBLE", "EXECUTED", "FOLLOWED"):
        assert f"`{status}`" in text


def test_plugin_name_matches_skill_name():
    plugin = json.loads((SCRIPT.parent.parent / "plugin.json").read_text(encoding="utf-8"))
    assert plugin["name"] == "boyko-preflight"


def test_skill_points_to_validator():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "scripts/validate_preflight.py" in text
