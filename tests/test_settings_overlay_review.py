"""Review findings on settings_overlay.py (2026-11-27): each test encodes one finding."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "settings_overlay", ROOT / "scripts" / "settings_overlay.py"
)
so = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(so)


def _group(cmd, matcher="Bash", timeout=None):
    h = {"type": "command", "command": cmd}
    if timeout is not None:
        h["timeout"] = timeout
    return {"matcher": matcher, "hooks": [h]}


SHIPPED = "python /tmp/a/.claude/hooks/input_guard.py"


def test_live_variant_with_extra_args_is_reported_not_lost():
    tmpl = {"hooks": {"PreToolUse": [_group(SHIPPED)]}}
    live = {"hooks": {"PreToolUse": [_group("python C:/u/.claude/hooks/input_guard.py --strict")]}}
    ov = so.extract(live, tmpl)
    assert ov["hooks"] == {}
    assert ov["variants"]["PreToolUse"], "a variant of a shipped hook must be reported"
    assert so.missing(tmpl, ov, with_variants=True), "verify must see the variant as missing"
    merged = so.apply(tmpl, ov, with_variants=True)
    assert so.missing(merged, ov, with_variants=True) == []
    cmds = [h["command"] for g in merged["hooks"]["PreToolUse"] for h in g["hooks"]]
    assert len(cmds) == 1 and "--strict" in cmds[0], "the variant replaces, it does not duplicate"


def test_variant_is_not_applied_by_default_so_no_hook_runs_twice():
    tmpl = {"hooks": {"PreToolUse": [_group(SHIPPED)]}}
    live = {"hooks": {"PreToolUse": [_group("python -S C:/u/.claude/hooks/input_guard.py")]}}
    merged = so.apply(tmpl, so.extract(live, tmpl))
    assert len(merged["hooks"]["PreToolUse"]) == 1


def test_live_variant_with_different_timeout_is_reported():
    tmpl = {"hooks": {"PreToolUse": [_group(SHIPPED, timeout=5)]}}
    live = {
        "hooks": {"PreToolUse": [_group("python C:/u/.claude/hooks/input_guard.py", timeout=30)]}
    }
    assert so.extract(live, tmpl)["variants"]


def test_same_shipped_hook_under_another_home_is_not_private():
    tmpl = {"hooks": {"PreToolUse": [_group(SHIPPED)]}}
    live = {"hooks": {"PreToolUse": [_group("python C:/Users/x/.claude/hooks/input_guard.py")]}}
    assert so.extract(live, tmpl)["hooks"] == {}


def test_inline_private_hook_is_not_masked_by_another_inline_hook():
    tmpl = {"hooks": {"Stop": [_group("echo shipped", matcher="")]}}
    live = {
        "hooks": {
            "Stop": [_group("echo shipped", matcher=""), _group("notify-send done", matcher="")]
        }
    }
    ov = so.extract(live, tmpl)
    assert sum(len(v) for v in ov["hooks"].values()) == 1
    assert so.missing(tmpl, ov), "verify must see the inline private hook as missing"


def test_hook_removed_from_new_template_is_not_carried_back_when_old_template_given():
    old = {
        "hooks": {"PreToolUse": [_group(SHIPPED), _group("python /tmp/a/.claude/hooks/retired.py")]}
    }
    new = {"hooks": {"PreToolUse": [_group(SHIPPED)]}}
    live = {
        "hooks": {"PreToolUse": [_group(SHIPPED), _group("python C:/u/.claude/hooks/retired.py")]}
    }
    assert so.extract(live, new, old_template=old)["hooks"] == {}


def test_non_list_permission_keys_are_kept():
    tmpl = {"permissions": {"allow": ["Read(*)"]}}
    live = {
        "permissions": {
            "allow": ["Read(*)"],
            "defaultMode": "acceptEdits",
            "additionalDirectories": ["D:/work"],
        }
    }
    ov = so.extract(live, tmpl)
    merged = so.apply(tmpl, ov)
    assert merged["permissions"]["defaultMode"] == "acceptEdits"
    assert merged["permissions"]["additionalDirectories"] == ["D:/work"]
    assert so.missing(merged, ov) == []


def test_out_inside_a_git_repo_is_refused(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    live, tmpl = tmp_path / "l.json", tmp_path / "t.json"
    live.write_text("{}", encoding="utf-8")
    tmpl.write_text("{}", encoding="utf-8")
    rc = so.main(
        ["extract", "--live", str(live), "--template", str(tmpl), "--out", str(tmp_path / "o.json")]
    )
    assert rc == 2
    assert not (tmp_path / "o.json").exists()


def test_non_object_json_is_a_clean_error(tmp_path):
    live, tmpl = tmp_path / "l.json", tmp_path / "t.json"
    live.write_text("[]", encoding="utf-8")
    tmpl.write_text("{}", encoding="utf-8")
    assert so.main(["extract", "--live", str(live), "--template", str(tmpl), "--dry-run"]) == 2
