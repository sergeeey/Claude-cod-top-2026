"""Tests for scripts/settings_overlay.py. All settings below are synthetic."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "settings_overlay", ROOT / "scripts" / "settings_overlay.py"
)
so = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(so)

TEMPLATE = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {"type": "command", "command": "python /tmp/a/.claude/hooks/input_guard.py"}
                ],
            }
        ],
        "SessionStart": [
            {
                "matcher": "",
                "hooks": [
                    {"type": "command", "command": "python /tmp/a/.claude/hooks/session_start.py"}
                ],
            }
        ],
    },
    "env": {"SHARED": "1"},
    "permissions": {"allow": ["Read(*)"]},
}


def _live():
    live = json.loads(json.dumps(TEMPLATE))
    # same shipped hooks under a different home path: NOT part of the overlay
    live["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = (
        "python C:/Users/x/.claude/hooks/input_guard.py"
    )
    # private additions: part of the overlay
    live["hooks"]["UserPromptSubmit"] = [
        {
            "matcher": "",
            "hooks": [
                {
                    "type": "command",
                    "command": "python C:/Users/x/.claude/hooks/skill_candidates.py",
                }
            ],
        }
    ]
    live["env"]["SKILL_CANDIDATES_LOG"] = "C:/Users/x/.claude/logs/sc.jsonl"
    live["permissions"]["allow"].append("Bash(gh pr view:*)")
    live["model"] = "opus"
    return live


def test_extract_finds_only_private_items():
    ov = so.extract(_live(), TEMPLATE)
    assert list(ov["hooks"]) == ["UserPromptSubmit"]
    assert list(ov["env"]) == ["SKILL_CANDIDATES_LOG"]
    assert ov["permissions"] == {"allow": ["Bash(gh pr view:*)"]}
    assert ov["other"] == {"model": "opus"}


def test_apply_then_verify_and_idempotent():
    ov = so.extract(_live(), TEMPLATE)
    merged = so.apply(TEMPLATE, ov)
    assert so.missing(merged, ov) == []
    twice = so.apply(merged, ov)
    assert twice == merged  # no duplicate hooks or permission items
    assert so.missing(TEMPLATE, ov), "an install without the overlay must be reported"


def test_apply_keeps_shipped_hooks():
    merged = so.apply(TEMPLATE, so.extract(_live(), TEMPLATE))
    assert so._hook_keys(TEMPLATE) <= so._hook_keys(merged)


def test_cli_dry_run_prints_keys_not_values(tmp_path, capsys):
    live, tmpl = tmp_path / "live.json", tmp_path / "t.json"
    live.write_text(json.dumps(_live()), encoding="utf-8")
    tmpl.write_text(json.dumps(TEMPLATE), encoding="utf-8")
    assert so.main(["extract", "--live", str(live), "--template", str(tmpl), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "SKILL_CANDIDATES_LOG" in out
    assert "sc.jsonl" not in out
    assert not (tmp_path / "o.json").exists()


def test_cli_round_trip_with_backup(tmp_path):
    live, tmpl, inst, ov = (tmp_path / n for n in ("live.json", "t.json", "i.json", "o.json"))
    live.write_text(json.dumps(_live()), encoding="utf-8")
    tmpl.write_text(json.dumps(TEMPLATE), encoding="utf-8")
    inst.write_text(json.dumps(TEMPLATE), encoding="utf-8")
    assert so.main(["extract", "--live", str(live), "--template", str(tmpl), "--out", str(ov)]) == 0
    assert so.main(["verify", "--installed", str(inst), "--overlay", str(ov)]) == 1
    assert so.main(["apply", "--installed", str(inst), "--overlay", str(ov)]) == 0
    assert so.main(["verify", "--installed", str(inst), "--overlay", str(ov)]) == 0
    assert list(tmp_path.glob("i.json.bak-overlay-*"))
