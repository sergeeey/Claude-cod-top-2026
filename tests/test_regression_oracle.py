"""scripts/regression_oracle.py on a small synthetic repository (no project history, no model).

The planted cases are the point: a grader that never rejects an unsolved, cheating or
regressing workspace proves nothing when it accepts a solved one.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
import regression_oracle as oracle

REAL_TASKS = {tid: dict(task) for tid, task in oracle.TASKS.items()}
DOC = Path(__file__).parent / "eval" / "e2e-regression-set.md"

HEADER = (
    "import sys\nfrom pathlib import Path\n\n"
    "sys.path.insert(0, str(Path(__file__).parent.parent / 'hooks'))\n"
)
OLD_TEST = HEADER + "import calc\n\n\ndef test_zero():\n    assert calc.double(0) == 0\n"
NEW_TEST = OLD_TEST + "\n\ndef test_two():\n    assert calc.double(2) == 4\n"
OTHER_TEST = HEADER + "import other\n\n\ndef test_other():\n    assert other.NAME == 'x'\n"
BROKEN = "def double(n):\n    return n\n"
FIXED = "def double(n):\n    return n * 2\n"


def write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


def commit(repo: Path, files: dict[str, str]) -> str:
    def git(*args: str) -> str:
        cmd = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        cmd += ["-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args]
        return subprocess.run(cmd, capture_output=True, check=True, text=True).stdout

    if not (repo / ".git").exists():
        git("init", "-q")
    write(repo, files)
    git("add", "-A")
    git("commit", "-q", "--no-verify", "-m", "c")
    return git("rev-parse", "HEAD").strip()


@pytest.fixture
def task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    repo = tmp_path / "repo"
    repo.mkdir()
    parent = commit(
        repo,
        {
            "hooks/calc.py": BROKEN,
            "hooks/other.py": "NAME = 'x'\n",
            "tests/test_calc.py": OLD_TEST,
            "tests/test_other.py": OTHER_TEST,
            "README.md": "demo\n",
        },
    )
    fix = commit(repo, {"hooks/calc.py": FIXED, "tests/test_calc.py": NEW_TEST})
    monkeypatch.setattr(oracle, "REPO", repo)
    # the nested pytest runs need no third-party plugins; autoloading them triples the runtime
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setitem(
        oracle.TASKS,
        "T",
        {
            "fix": fix,
            "parent": parent,
            "test": "tests/test_calc.py",
            "sha": hashlib.sha256(NEW_TEST.encode()).hexdigest()[:12],
            "statement": "double must double",
        },
    )
    return "T"


def workspace(task_id: str, dest: Path, edits: dict[str, str] | None = None) -> Path:
    oracle.export(oracle.TASKS[task_id]["parent"], dest)
    write(dest, edits or {})
    return dest


@pytest.mark.parametrize(
    ("rel", "was", "now", "reason"),
    [
        ("hooks/a.py", "1", "2", None),
        ("scripts/new.py", None, "1", None),
        ("tests/test_new.py", None, "1", None),
        ("tests/test_a.py", "1", "2", "modified"),
        ("tests/test_a.py", "1", None, "deleted"),
        ("tests/conftest.py", None, "1", "configuration"),
        ("hooks/sitecustomize.py", None, "1", "configuration"),
        ("tests/.pytest.ini", None, "1", "configuration"),
        ("tests/pyproject.toml", None, "1", "configuration"),
        ("tests/pytest.toml", None, "1", "configuration"),
        ("tests/sub/Conftest.py", None, "1", "configuration"),
        ("pyproject.toml", "1", "2", "outside"),
        ("conftest.py", None, "1", "outside"),
    ],
)
def test_scope_violations(rel: str, was: str | None, now: str | None, reason: str | None) -> None:
    before = {rel: was} if was else {}
    after = {rel: now} if now else {}
    found = oracle.scope_violations(before, after)
    assert found == [] if reason is None else reason in found[0]


def _result(**changes: object) -> dict:
    base: dict = {
        "scope_violations": [],
        "control": {"status": "passed"},
        "hidden_test": {"status": "passed"},
        "full_suite_run": True,
        "new_failures": [],
        "lost_passes": [],
    }
    return {**base, **changes}


BROKEN_CONTROL = {"control": {"status": "failed"}, "hidden_test": {"status": "failed"}}


@pytest.mark.parametrize(
    ("changes", "state"),
    [
        ({"scope_violations": ["x"]}, "defect found"),
        ({"hidden_test": {"status": "failed"}}, "defect found"),
        ({"hidden_test": {"status": "interrupted"}}, "defect found"),
        ({"hidden_lost_passes": ["t"]}, "defect found"),
        ({"new_failures": ["t"]}, "defect found"),
        ({"lost_passes": ["t"]}, "defect found"),
        ({"control": {"status": "interrupted"}}, "insufficient evidence"),
        (BROKEN_CONTROL, "insufficient evidence"),
        ({"hidden_test": {"status": "infrastructure"}}, "insufficient evidence"),
        ({"full_suite_run": False}, "partly confirmed: hidden test only"),
        ({}, "confirmed by oracle"),
    ],
)
def test_state_of(changes: dict, state: str) -> None:
    assert oracle.state_of(_result(**changes)) == state


def test_state_of_without_a_suite_comparison_is_not_confirmed() -> None:
    result = _result()
    del result["new_failures"]
    assert oracle.state_of(result) == "insufficient evidence"


def test_manifest_ignores_tool_caches(tmp_path: Path) -> None:
    write(tmp_path, {"hooks/a.py": "1", ".hypothesis/x": "1", "tests/__pycache__/a.pyc": "1"})
    write(tmp_path, {".git/config": "1", ".venv/lib.py": "1", ".DS_Store": "1"})
    (tmp_path / ".coverage").write_text("1")
    assert list(oracle.manifest(tmp_path)) == ["hooks/a.py"]


def test_isolated_env_drops_live_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("CLAUDE_CONFIG_DIR", "ANTHROPIC_API_KEY", "SKILL_CANDIDATES_LOG", "PYTHONPATH"):
        monkeypatch.setenv(name, "leak")
    for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "COV_CORE_SOURCE", "COVERAGE_PROCESS_START"):
        monkeypatch.setenv(name, "leak")
    env = oracle.isolated_env(tmp_path)
    assert "leak" not in env.values()
    assert env["HOME"] == env["USERPROFILE"] == str(tmp_path)


def test_export_has_no_history_and_refuses_non_empty(task: str, tmp_path: Path) -> None:
    dest = workspace(task, tmp_path / "ws")
    assert not (dest / ".git").exists()
    assert (dest / "hooks" / "calc.py").read_bytes() == BROKEN.encode()
    with pytest.raises(oracle.OracleError, match="non-empty"):
        oracle.export(oracle.TASKS[task]["parent"], dest)


def test_hidden_test_hash_mismatch_stops(task: str) -> None:
    bad = {**oracle.TASKS[task], "sha": "0" * 12}
    with pytest.raises(oracle.OracleError, match="hash mismatch"):
        oracle.hidden_test(bad)


def test_selfcheck_discriminates(task: str) -> None:
    record = oracle.selfcheck(task, 120)
    assert record["oracle_discriminates"]
    assert record["parent"]["failed"] == 1
    assert record["fix"]["tests"] == 2


def test_untouched_workspace_is_a_defect(task: str, tmp_path: Path) -> None:
    result = oracle.check(task, workspace(task, tmp_path / "ws"), False, 120)
    assert result["state"] == "defect found"
    assert result["changed_files"] == []


def test_solved_workspace_without_full_suite_is_only_partial(task: str, tmp_path: Path) -> None:
    ws = workspace(task, tmp_path / "ws", {"hooks/calc.py": FIXED})
    result = oracle.check(task, ws, False, 120)
    assert result["state"] == "partly confirmed: hidden test only"
    # grading runs on a copy: the workspace keeps its own test file
    assert (ws / "tests" / "test_calc.py").read_text(encoding="utf-8") == OLD_TEST


def test_solved_workspace_with_full_suite_is_confirmed(task: str, tmp_path: Path) -> None:
    ws = workspace(task, tmp_path / "ws", {"hooks/calc.py": FIXED})
    result = oracle.check(task, ws, True, 120)
    assert result["state"] == "confirmed by oracle"
    assert result["new_failures"] == []


def test_regression_elsewhere_is_a_defect(task: str, tmp_path: Path) -> None:
    edits = {"hooks/calc.py": FIXED, "hooks/other.py": "NAME = 'y'\n"}
    result = oracle.check(task, workspace(task, tmp_path / "ws", edits), True, 120)
    assert result["hidden_test"]["status"] == "passed"
    assert result["state"] == "defect found"
    assert any("test_other" in failed for failed in result["new_failures"])


def test_edited_test_is_a_defect_even_when_solved(task: str, tmp_path: Path) -> None:
    edits = {"hooks/calc.py": FIXED, "tests/test_calc.py": "def test_ok():\n    pass\n"}
    result = oracle.check(task, workspace(task, tmp_path / "ws", edits), False, 120)
    assert result["hidden_test"]["status"] == "passed"
    assert result["state"] == "defect found"
    assert "modified" in result["scope_violations"][0]


DESELECT = '[pytest]\npythonpath = ../hooks\naddopts = -k "not test_two"\n'
SKIPS = "import pytest\n\n\ndef double(n):\n    pytest.skip('x')\n"
EXITS = (
    "import pytest\n\n\ndef double(n):\n"
    "    if n:\n        pytest.exit('x', returncode=0)\n    return 0\n"
)


def test_candidate_pytest_config_cannot_hide_the_hidden_test(task: str, tmp_path: Path) -> None:
    ws = workspace(task, tmp_path / "ws", {"tests/.pytest.ini": DESELECT})
    result = oracle.check(task, ws, False, 120)
    assert result["hidden_test"]["status"] == "failed"  # the config was not executed
    assert result["state"] == "defect found"


def test_candidate_test_files_are_reported_but_not_executed(task: str, tmp_path: Path) -> None:
    edits = {"tests/calc.py": FIXED, "tests/test_extra.py": "def test_x():\n    assert 0\n"}
    result = oracle.check(task, workspace(task, tmp_path / "ws", edits), True, 120)
    assert result["test_files_not_executed"] == ["tests/calc.py", "tests/test_extra.py"]
    assert result["state"] == "defect found"  # unsolved: a shadow module in tests/ does not help
    assert result["new_failures"] == []


@pytest.mark.parametrize("body", [SKIPS, EXITS], ids=["skip", "exit"])
def test_a_hidden_test_that_does_not_run_is_a_defect(task: str, tmp_path: Path, body: str) -> None:
    ws = workspace(task, tmp_path / "ws", {"hooks/calc.py": body})
    result = oracle.check(task, ws, False, 120)
    assert result["hidden_lost_passes"]
    assert result["state"] == "defect found"


def test_collection_error_elsewhere_is_not_confirmed(task: str, tmp_path: Path) -> None:
    edits = {"hooks/calc.py": FIXED, "hooks/other.py": "import no_such_module_here\n"}
    result = oracle.check(task, workspace(task, tmp_path / "ws", edits), True, 120)
    assert result["candidate_suite"]["status"] == "interrupted"
    assert result["lost_passes"]
    assert result["state"] == "defect found"


def test_skipped_test_elsewhere_is_a_defect(task: str, tmp_path: Path) -> None:
    skip_module = "import pytest\n\npytest.skip('x', allow_module_level=True)\n"
    edits = {"hooks/calc.py": FIXED, "hooks/other.py": skip_module}
    result = oracle.check(task, workspace(task, tmp_path / "ws", edits), True, 120)
    assert result["new_failures"] == []
    assert any("test_other" in lost for lost in result["lost_passes"])
    assert result["state"] == "defect found"


def test_deleted_code_file_is_deleted_in_the_graded_tree(task: str, tmp_path: Path) -> None:
    ws = workspace(task, tmp_path / "ws", {"hooks/calc.py": FIXED})
    (ws / "hooks" / "other.py").unlink()
    assert oracle.check(task, ws, True, 120)["state"] == "defect found"


def test_failing_control_is_insufficient_evidence(
    task: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The machine cannot pass even the fix commit: that says nothing about the candidate."""
    real = oracle.run_pytest

    def broken(tree: Path, target: str, timeout: int) -> dict:
        if tree.name == "control":
            return {"status": "interrupted", "failed_ids": [], "passed_ids": []}
        return real(tree, target, timeout)

    monkeypatch.setattr(oracle, "run_pytest", broken)
    result = oracle.check(task, workspace(task, tmp_path / "ws"), False, 120)
    assert result["state"] == "insufficient evidence"


def test_wrong_workspace_is_a_usage_error(task: str, tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    for path in (tmp_path / "empty", tmp_path / "absent"):
        with pytest.raises(ValueError, match="not a prepared workspace"):
            oracle.check(task, path, False, 120)


def test_run_without_tests_is_infrastructure(tmp_path: Path) -> None:
    write(tmp_path, {"tests/helper.py": "X = 1\n"})
    assert oracle.run_pytest(tmp_path, "tests", 120)["status"] == "infrastructure"


def test_timeout_is_infrastructure(tmp_path: Path) -> None:
    slow = "import time\n\n\ndef test_slow():\n    time.sleep(30)\n"
    write(tmp_path, {"tests/test_slow.py": slow})
    assert oracle.run_pytest(tmp_path, "tests", 1)["status"] == "infrastructure"


def cli(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["regression_oracle.py", *args])
    return oracle.main()


def test_cli_exit_codes_and_record(
    task: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    ws, out, meta = tmp_path / "ws", tmp_path / "runs.jsonl", tmp_path / "meta.json"
    meta.write_text('{"model": "m"}', encoding="utf-8")
    assert cli(monkeypatch, "prepare", task, str(ws)) == 0
    assert "double must double" in capsys.readouterr().out
    run = ["--out", str(out), "check", task, str(ws), "--run-meta", str(meta)]
    assert cli(monkeypatch, *run) == 1
    write(ws, {"hooks/calc.py": FIXED})
    assert cli(monkeypatch, *run) == 3  # without --full a pass is never exit 0
    assert cli(monkeypatch, *run, "--full") == 0
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    states = [r["state"] for r in records]
    assert states == ["defect found", oracle.PARTLY, "confirmed by oracle"]
    assert records[0]["run_meta"] == {"model": "m"}
    assert records[0]["environment"]["python"]
    assert cli(monkeypatch, "selfcheck", task) == 0


@pytest.mark.parametrize("bad", ["meta", "workspace"])
def test_cli_usage_errors(
    task: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    ws = workspace(task, tmp_path / "ws")
    args = ["check", task, str(ws), "--run-meta", str(tmp_path / "absent.json")]
    if bad == "workspace":
        args = ["check", task, str(tmp_path / "absent")]
    with pytest.raises(SystemExit) as stop:
        cli(monkeypatch, *args)
    assert stop.value.code == 2


@pytest.mark.parametrize("failure", ["hash", "commit", "git"])
def test_cli_oracle_failure_is_not_a_candidate_defect(
    task: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    failure: str,
) -> None:
    ws = workspace(task, tmp_path / "ws", {"hooks/calc.py": FIXED})
    if failure == "hash":
        monkeypatch.setitem(oracle.TASKS[task], "sha", "0" * 12)
    elif failure == "commit":
        monkeypatch.setitem(oracle.TASKS[task], "fix", "f" * 40)
    else:

        def no_git(*args: str) -> bytes:
            raise FileNotFoundError("git")

        monkeypatch.setattr(oracle, "git_bytes", no_git)
    assert cli(monkeypatch, "check", task, str(ws)) == 4
    record = json.loads(capsys.readouterr().out)
    assert record["state"] == "insufficient evidence"
    assert record["error"]


def test_cli_selfcheck_that_cannot_run_exits_four(
    task: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(oracle, "run_pytest", lambda *a: {"status": "infrastructure"})
    assert cli(monkeypatch, "selfcheck", task) == 4


def test_cli_bad_paths_stop_before_any_run(
    task: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = workspace(task, tmp_path / "ws")

    def never(*args: object) -> dict:
        raise AssertionError("the run must not start")

    monkeypatch.setattr(oracle, "check", never)
    for args in (
        ["--out", str(tmp_path / "absent" / "r.jsonl"), "check", task, str(ws)],
        ["prepare", task, str(ws)],  # destination is not empty
    ):
        with pytest.raises(SystemExit) as stop:
            cli(monkeypatch, *args)
        assert stop.value.code == 2


def test_truncated_report_is_infrastructure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def truncated(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        report = Path(cmd[-1].split("=", 1)[1])
        report.write_text("<testsuites><testsuite>", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(oracle.subprocess, "run", truncated)
    assert oracle.run_pytest(tmp_path, "tests", 5)["status"] == "infrastructure"


def test_cli_rejects_unknown_selfcheck_task(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["regression_oracle.py", "selfcheck", "NOPE"])
    with pytest.raises(SystemExit) as stop:
        oracle.main()
    assert stop.value.code == 2


@pytest.mark.parametrize("tid", sorted(REAL_TASKS))
def test_script_and_document_list_the_same_commits(tid: str) -> None:
    task = REAL_TASKS[tid]
    row = next(
        line
        for line in DOC.read_text(encoding="utf-8").splitlines()
        if line.startswith(f"| {tid} | coding |")
    )
    assert f"`{task['fix']}` / `{task['parent']}` / `{task['sha']}`" in row
    assert task["test"] in row


def test_tar_failure_is_insufficient_evidence_not_a_defect(
    task: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    import tarfile

    def broken_export(rev: str, dest: Path) -> None:
        raise tarfile.ReadError("truncated archive")

    ws = workspace(task, tmp_path / "ws")  # built before export is replaced
    monkeypatch.setattr(oracle, "export", broken_export)
    code = cli(monkeypatch, "check", task, str(ws))
    assert code == 4
    assert json.loads(capsys.readouterr().out)["state"] == "insufficient evidence"


def test_reference_run_with_no_passing_test_is_insufficient_evidence() -> None:
    # Codex P2 (PR #572): an all-skipped reference passes pytest with exit 0 and no passed ids.
    # That says nothing about the candidate; it must not confirm.
    control = {"status": "passed", "passed_ids": [], "failed_ids": [], "exit": 0}
    hidden = {"status": "passed", "passed_ids": ["t::a"], "failed_ids": [], "exit": 0}
    result = {
        "scope_violations": [],
        "control": control,
        "hidden_test": hidden,
        "full_suite_run": False,
    }
    assert oracle.state_of(result) == "insufficient evidence"
    result["control"] = {"status": "passed", "passed_ids": ["t::a"], "failed_ids": [], "exit": 0}
    assert oracle.state_of(result) == oracle.PARTLY
