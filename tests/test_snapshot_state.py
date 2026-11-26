"""Tests for scripts/snapshot_state.py: parsing, privacy guard, compare."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

import snapshot_state as ss  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def test_hook_scripts_skips_async_launcher():
    cmd = "python /h/hooks/async_wrapper.py /h/hooks/real_hook.py --x"
    assert ss.hook_scripts(cmd) == ["real_hook.py"]
    assert ss.hook_scripts("python /h/hooks/async_wrapper.py") == ["async_wrapper.py"]
    assert ss.hook_scripts("echo hi") == []


def test_secret_shapes_are_caught_and_plain_text_is_not():
    assert ss.secret_hits("key sk-" + "a" * 30)
    assert ss.secret_hits("pass" + "word = '" + "abcdefghij" + "klmnop1234'")
    assert not ss.secret_hits("| env_keys | PYTHONIOENCODING |")


def test_anonymise_replaces_home(tmp_path):
    home = tmp_path / ".claude"
    assert ss.anonymise(f"path {home} here", home).startswith("path ~")


def test_build_on_this_repo_without_live_install(tmp_path):
    snap = ss.build(ROOT, tmp_path / "missing", None)
    m = snap["metrics"]
    assert snap["live"] == {"present": False}
    assert m["repo.skills"] == len(snap["repo"]["skills"]["items"]) > 0
    assert m["repo.hooks_registered"] == len(snap["repo"]["hooks"]["items"]) > 0
    assert not any(k.startswith(("live.", "drift.")) for k in m)


def test_main_writes_md_and_json_without_secret_values(tmp_path):
    home = tmp_path / ".claude"
    home.mkdir()
    (home / "settings.json").write_text(
        json.dumps({"env": {"MY_TOKEN": "sk-" + "z" * 40}, "model": "haiku"}), encoding="utf-8"
    )
    out = tmp_path / "out"
    rc = ss.main(["--repo", str(ROOT), "--live", str(home), "--out", str(out)])
    assert rc == 0
    text = "".join(p.read_text(encoding="utf-8") for p in out.iterdir())
    assert "MY_TOKEN" in text  # names are recorded
    assert "zzzzzzzz" not in text  # values never are
    assert len(list(out.glob("snapshot-*.json"))) == 1


def test_compare_reports_added_removed_and_metric_delta():
    base = {
        "date": "d1",
        "repo": {
            "skills": {"items": [{"name": "a", "hash": "1"}, {"name": "b", "hash": "2"}]},
            "agents": [],
            "rules": [],
            "hooks": {"items": []},
        },
        "metrics": {"repo.skills": 2},
    }
    new = json.loads(json.dumps(base))
    new["date"] = "d2"
    new["repo"]["skills"]["items"] = [{"name": "a", "hash": "9"}, {"name": "c", "hash": "3"}]
    new["metrics"]["repo.skills"] = 5
    new["metrics"]["repo.maturity.dogfooded"] = 4
    out = ss.compare(base, new)
    assert "| skills | c | b | a |" in out
    assert "| repo.skills | 2 | 5 | +3 |" in out
    assert "| repo.maturity.dogfooded | – | 4 |" in out


def test_skill_files_follow_directory_symlinks(tmp_path):
    real = tmp_path / "store" / "brainstorming"
    real.mkdir(parents=True)
    (real / "SKILL.md").write_text("---\nname: brainstorming\n---\n", encoding="utf-8")
    skills = tmp_path / "skills"
    skills.mkdir()
    try:
        (skills / "brainstorming").symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlinks are not available here")
    assert [p.parent.name for p in ss.skill_files(skills)] == ["brainstorming"]


def test_anonymise_with_relative_live_path_keeps_dots(tmp_path, monkeypatch):
    (tmp_path / ".claude").mkdir()
    monkeypatch.chdir(tmp_path)
    out = ss.anonymise("repo.skills input_guard.py " + str(tmp_path / ".claude"), Path(".claude"))
    assert "repo.skills input_guard.py" in out
    assert out == "repo.skills input_guard.py ~"
