"""Codex review findings on PR #583 for settings_overlay.py. Synthetic settings only."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "settings_overlay", ROOT / "scripts" / "settings_overlay.py"
)
so = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(so)

SHIPPED = {"type": "command", "command": "python /tmp/a/.claude/hooks/input_guard.py"}
PRIVATE = {"type": "command", "command": "python C:/u/.claude/hooks/private.py"}


def _count(settings: dict, needle: str) -> int:
    return sum(
        needle in h["command"]
        for groups in settings.get("hooks", {}).values()
        for g in groups
        for h in g["hooks"]
    )


def test_private_hook_added_to_a_shipped_group_does_not_duplicate_the_shipped_hook():
    tmpl = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [SHIPPED]}]}}
    live_shipped = dict(SHIPPED, command="python C:/u/.claude/hooks/input_guard.py")
    live = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [live_shipped, PRIVATE]}]}}
    ov = so.extract(live, tmpl)
    assert so.missing(tmpl, ov), "the private hook must be reported as missing before apply"
    merged = so.apply(tmpl, ov)
    assert so.missing(merged, ov) == []
    assert _count(merged, "input_guard.py") == 1, "the shipped hook must run once"
    assert _count(merged, "private.py") == 1
    assert so.apply(merged, ov) == merged


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_apply_keeps_restrictive_permissions(tmp_path):
    inst, ov = tmp_path / "settings.json", tmp_path / "o.json"
    inst.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
    os.chmod(inst, 0o600)
    ov.write_text(
        json.dumps({"hooks": {}, "env": {"K": "v"}, "permissions": {}, "other": {}}),
        encoding="utf-8",
    )
    assert so.main(["apply", "--installed", str(inst), "--overlay", str(ov)]) == 0
    assert stat.S_IMODE(inst.stat().st_mode) == 0o600


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_overlay_file_is_written_owner_only(tmp_path):
    live, tmpl, out = tmp_path / "l.json", tmp_path / "t.json", tmp_path / "o.json"
    live.write_text(json.dumps({"env": {"K": "secret-value"}}), encoding="utf-8")
    tmpl.write_text("{}", encoding="utf-8")
    assert (
        so.main(["extract", "--live", str(live), "--template", str(tmpl), "--out", str(out)]) == 0
    )
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
