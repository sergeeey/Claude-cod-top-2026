"""skill_candidates hook: advisory, once per skill per session, fail-open, experiment mode off by default."""

import importlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

PROMPT = (
    "Please reconcile these bank statements against the general ledger "
    "and flag the unmatched transactions"
)
OTHER = "Prepare the lighthouse maintenance schedule and inspect the beacon lenses thoroughly"


def write_skill(skills: Path, name: str, desc: str, extra: str = "") -> None:
    d = skills / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n{extra}---\n\n# {name}\n", encoding="utf-8"
    )


@pytest.fixture()
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    skills = home / ".claude" / "skills"
    write_skill(
        skills,
        "ledger-reconcile",
        "Reconcile bank statements against the general ledger and flag unmatched transactions",
    )
    write_skill(
        skills,
        "lighthouse-care",
        "Prepare the lighthouse maintenance schedule and inspect beacon lenses",
    )
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    monkeypatch.delenv("SKILL_CANDIDATES", raising=False)
    monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
    monkeypatch.delenv("SKILL_CANDIDATES_HOLDOUT", raising=False)
    monkeypatch.delenv("SKILL_CANDIDATES_LOG", raising=False)
    mod = importlib.import_module("skill_candidates")
    monkeypatch.setattr(mod, "STATE_DIR", home / ".claude" / "state")
    return mod, home, tmp_path


def run(mod, monkeypatch, capsys, prompt, session="s1", cwd=None):
    payload = {"prompt": prompt, "session_id": session, "cwd": str(cwd or os.getcwd())}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    with pytest.raises(SystemExit):
        mod.main()
    out = capsys.readouterr().out.strip()
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""


def test_confident_match_is_advised_once_per_session_and_again_in_a_new_session(
    env, monkeypatch, capsys
):
    mod, _, _ = env
    first = run(mod, monkeypatch, capsys, PROMPT)
    assert "[skill-candidates]" in first and "ledger-reconcile" in first
    assert "ignore" in first  # advisory wording: the model keeps the right to ignore
    assert run(mod, monkeypatch, capsys, PROMPT) == ""  # same skill, same session: silent
    assert "lighthouse-care" in run(
        mod, monkeypatch, capsys, OTHER
    )  # a new sub-task still surfaces
    assert "ledger-reconcile" in run(mod, monkeypatch, capsys, PROMPT, session="s2")


def test_slash_commands_short_messages_and_nonmatching_text_stay_silent(env, monkeypatch, capsys):
    mod, _, _ = env
    assert run(mod, monkeypatch, capsys, "/ledger-reconcile " + PROMPT) == ""
    assert run(mod, monkeypatch, capsys, "yes go on please") == ""
    assert (
        run(mod, monkeypatch, capsys, "what time is the weather forecast for tomorrow evening")
        == ""
    )


def test_project_overrides_are_honoured_through_the_hook(env, monkeypatch, capsys, tmp_path):
    mod, _, base = env
    proj = base / "proj"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "settings.json").write_text(
        json.dumps({"skillOverrides": {"ledger-reconcile": "off"}}), encoding="utf-8"
    )
    assert run(mod, monkeypatch, capsys, PROMPT, cwd=proj) == ""
    assert "ledger-reconcile" in run(mod, monkeypatch, capsys, PROMPT, session="other", cwd=base)


def test_a_missing_search_script_or_garbage_input_never_breaks_the_prompt(env, monkeypatch, capsys):
    mod, _, _ = env
    monkeypatch.setattr(mod, "_load_search", lambda: None)
    assert run(mod, monkeypatch, capsys, PROMPT) == ""
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    with pytest.raises(SystemExit) as e:
        mod.main()
    assert e.value.code == 0


def test_holdout_withholds_without_showing_and_logs_counts_only(env, monkeypatch, capsys):
    mod, home, base = env
    log = base / "exp.jsonl"
    monkeypatch.setenv("SKILL_CANDIDATES_LOG", str(log))
    monkeypatch.setenv("SKILL_CANDIDATES_HOLDOUT", "1.0")
    assert run(mod, monkeypatch, capsys, PROMPT) == ""
    assert not list((home / ".claude" / "state").glob("*.json"))  # withheld: offer not used up
    monkeypatch.setenv("SKILL_CANDIDATES_HOLDOUT", "0.0")
    assert "ledger-reconcile" in run(mod, monkeypatch, capsys, PROMPT, session="s9")
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [r["arm"] for r in rows] == ["control", "treatment"]
    assert all(set(r) == {"ts", "session", "arm", "names", "seconds"} for r in rows)
    assert all("statements" not in json.dumps(r) for r in rows)  # no message text


def test_experiment_mode_is_off_by_default(env, monkeypatch, capsys):
    mod, _, base = env
    assert mod._held_out("s", "p") is None
    assert not (base / "exp.jsonl").exists()


def test_kill_switch_exits_before_doing_any_work():
    code = "import sys; sys.path.insert(0, r'%s'); import skill_candidates" % (ROOT / "hooks")
    r = subprocess.run(
        [sys.executable, "-I", "-c", code],
        env={**os.environ, "SKILL_CANDIDATES": "0"},
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0 and r.stdout == ""
