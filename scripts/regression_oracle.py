"""Oracle side of the coding tasks C1-C5 in tests/eval/e2e-regression-set.md.

    python scripts/regression_oracle.py selfcheck [C1 ...]      # parent fails, fix passes
    python scripts/regression_oracle.py prepare C1 DEST         # agent workspace, no history
    python scripts/regression_oracle.py check C1 DEST [--full]  # grade a finished workspace

It never starts a model: running an agent in the prepared workspace is a separate, paid step.
Every pytest run uses a temporary HOME, so tests do not write into the live ~/.claude.

A pass needs positive evidence: the hidden test must first pass on the fix commit on this machine,
and every test that passed there (and, with --full, on the parent tree) must pass for the candidate.
The graded tree is the parent commit plus the candidate's hooks/ and scripts/ changes only, so the
candidate's own test files and pytest configuration are never executed.

Exit codes of `check`: 0 confirmed, 1 defect found, 2 usage error, 3 partly confirmed (no --full),
4 insufficient evidence (also any failure of the oracle itself: git, files, hidden test hash).
`selfcheck`: 0 discriminates, 1 does not, 4 could not be run.
This is NOT a sandbox: the graded code runs on this machine, and an agent with shell or network
access can still read the fix from this clone, from installed hooks or from the public remote.
"""

import argparse
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ALLOWED_DIRS = ("hooks", "scripts", "tests")
CODE_DIRS = ("hooks", "scripts")  # the only candidate changes that are executed
# Caches and local tooling an agent leaves behind; they are not edits and are never graded.
IGNORED_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".hypothesis",
    ".coverage",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".DS_Store",
    "Thumbs.db",
    "htmlcov",
    "coverage.xml",
}
# compared lower-cased: Windows file systems load Conftest.py as conftest.py
CONFIG_NAMES = {
    "conftest.py",
    "sitecustomize.py",
    "usercustomize.py",
    "pytest.ini",
    ".pytest.ini",
    "pytest.toml",
    ".pytest.toml",
    "pyproject.toml",
    "tox.ini",
    "setup.cfg",
}
EXIT_CODES = {"confirmed by oracle": 0, "defect found": 1, "insufficient evidence": 4}
PARTLY = "partly confirmed: hidden test only"

TASKS: dict[str, dict[str, str]] = {
    "C1": {
        "fix": "ad9671a",
        "parent": "36fa964",
        "test": "tests/test_independence_scorer.py",
        "sha": "adda80e8f779",
        "statement": "`independence_scorer` writes `key:` without a space for an empty YAML value.",
    },
    "C2": {
        "fix": "278bc52",
        "parent": "ef5be27",
        "test": "tests/test_learning_hooks.py",
        "sha": "ede4882ae63b",
        "statement": "`mentor_nudge` must exempt Speed Mode prompts from the TIP/lesson reminder.",
    },
    "C3": {
        "fix": "e210d21",
        "parent": "a589dbe",
        "test": "tests/test_locality_escalation_guard.py",
        "sha": "edb53a9692ec",
        "statement": "`locality_escalation_guard` state must anchor to the git root, "
        "not the working directory.",
    },
    "C4": {
        "fix": "e130a1f",
        "parent": "45f494a",
        "test": "tests/test_resource_router.py",
        "sha": "cd1f5fa4e8ee",
        "statement": "`resource_router` matches the bare homograph token/токен.",
    },
    "C5": {
        "fix": "cd0fe91",
        "parent": "ab48154",
        "test": "tests/test_permission_policy.py",
        "sha": "f4421b2d135e",
        "statement": "A CI job name `secrets-scan` must not be read as a dangerous command "
        "by `permission_policy`.",
    },
}


class OracleError(Exception):
    """The oracle could not do its job; says nothing about the candidate."""


def git_bytes(*args: str) -> bytes:
    cmd = ["git", "-C", str(REPO), "-c", "core.autocrlf=false", "-c", "core.eol=lf", *args]
    return subprocess.run(cmd, capture_output=True, check=True).stdout


def export(rev: str, dest: Path) -> None:
    """Plain copy of a commit's tree (no .git), into a new or empty directory."""
    if dest.exists() and any(dest.iterdir()):
        raise OracleError(f"refusing to write into a non-empty directory: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(git_bytes("archive", "--format=tar", rev))) as tar:
        tar.extractall(dest, filter="data")


def hidden_test(task: dict[str, str]) -> bytes:
    blob = git_bytes("show", f"{task['fix']}:{task['test']}")
    digest = hashlib.sha256(blob).hexdigest()
    if not digest.startswith(task["sha"]):
        raise OracleError(f"hidden test hash mismatch: expected {task['sha']}, got {digest[:12]}")
    return blob


def manifest(root: Path) -> dict[str, str]:
    out = {}
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if path.is_file() and not IGNORED_PARTS & set(rel.parts):
            out[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def scope_violations(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Edits that void the result: touched tests or test config, or files outside the scope."""
    bad = []
    for rel in sorted(set(before) | set(after)):
        if before.get(rel) == after.get(rel):
            continue
        parts = Path(rel).parts
        if parts[0] not in ALLOWED_DIRS:
            bad.append(f"outside allowed directories: {rel}")
        elif parts[-1].lower() in CONFIG_NAMES:
            bad.append(f"test or import configuration changed: {rel}")
        elif parts[0] == "tests" and rel in before:
            bad.append(f"existing test file {'deleted' if rel not in after else 'modified'}: {rel}")
    return bad


def isolated_env(home: Path) -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("CLAUDE", "ANTHROPIC", "SKILL_CANDIDATES", "COV_CORE", "COVERAGE"))
        and k not in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS")
    }
    env.update(
        HOME=str(home),
        USERPROFILE=str(home),
        PYTHONDONTWRITEBYTECODE="1",
        GIT_AUTHOR_NAME="oracle",
        GIT_AUTHOR_EMAIL="oracle@example.invalid",
        GIT_COMMITTER_NAME="oracle",
        GIT_COMMITTER_EMAIL="oracle@example.invalid",
    )
    return env


def run_pytest(tree: Path, target: str, timeout: int) -> dict:
    """status: passed | failed | interrupted | infrastructure, with ids from the JUnit report."""
    with tempfile.TemporaryDirectory(prefix="oracle_home_", ignore_cleanup_errors=True) as tmp:
        report = Path(tmp) / "junit.xml"
        cmd = [sys.executable, "-m", "pytest", target, "-q", "-p", "no:cacheprovider"]
        cmd.append(f"--junitxml={report}")
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=tree,
                env=isolated_env(Path(tmp)),
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {"status": "infrastructure", "reason": f"timeout after {timeout}s"}
        seconds = round(time.monotonic() - start, 1)
        try:
            cases = list(ET.parse(report).getroot().iter("testcase")) if report.exists() else []
        except ET.ParseError as exc:
            return {"status": "infrastructure", "reason": f"unreadable test report: {exc}"}
        # exit 2 is an interrupted run (a collection error): nothing after it was executed
        status = {0: "passed", 1: "failed", 2: "interrupted"}.get(proc.returncode)
        if status is None or not cases:
            tail = proc.stdout.decode("utf-8", "replace")[-300:]
            return {"status": "infrastructure", "reason": f"exit {proc.returncode}: {tail}"}
        ids: dict[str, list[str]] = {"failed": [], "skipped": [], "passed": []}
        for case in cases:
            if case.find("failure") is not None or case.find("error") is not None:
                kind = "failed"
            else:
                kind = "skipped" if case.find("skipped") is not None else "passed"
            ids[kind].append(f"{case.get('classname')}::{case.get('name')}")
        return {
            "status": status,
            "exit": proc.returncode,
            "tests": len(cases),
            "failed": len(ids["failed"]),
            "skipped": len(ids["skipped"]),
            "failed_ids": sorted(ids["failed"]),
            "passed_ids": sorted(ids["passed"]),
            "seconds": seconds,
        }


def overlay_and_test(task: dict[str, str], tree: Path, timeout: int) -> dict:
    (tree / task["test"]).write_bytes(hidden_test(task))
    return run_pytest(tree, task["test"], timeout)


def selfcheck(tid: str, timeout: int) -> dict:
    """Does the oracle discriminate? Parent tree must fail, fix tree must pass."""
    task = TASKS[tid]
    with tempfile.TemporaryDirectory(prefix="oracle_", ignore_cleanup_errors=True) as tmp:
        export(task["parent"], Path(tmp) / "parent")
        export(task["fix"], Path(tmp) / "fix")
        parent = overlay_and_test(task, Path(tmp) / "parent", timeout)
        fix = overlay_and_test(task, Path(tmp) / "fix", timeout)
    return {
        "task": tid,
        "oracle_discriminates": parent["status"] in ("failed", "interrupted")
        and fix["status"] == "passed",
        "parent": parent,
        "fix": fix,
    }


def build_graded(task: dict[str, str], workspace: Path, changed: list[str], graded: Path) -> None:
    """Parent commit plus the candidate's code changes; its tests and root files are left out."""
    export(task["parent"], graded)
    for rel in changed:
        if Path(rel).parts[0] not in CODE_DIRS:
            continue
        source, target = workspace / rel, graded / rel
        if source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        else:
            target.unlink(missing_ok=True)


def compare_suites(task: dict[str, str], baseline: dict, suite: dict) -> dict:
    """Outside the hidden test module: new failures, and baseline passes that did not pass."""
    module = task["test"].removesuffix(".py").replace("/", ".")

    def elsewhere(ids: set[str]) -> list[str]:
        return sorted(i for i in ids if not i.startswith((f"{module}.", f"{module}::")))

    return {
        "new_failures": elsewhere(set(suite["failed_ids"]) - set(baseline["failed_ids"])),
        "lost_passes": elsewhere(set(baseline["passed_ids"]) - set(suite["passed_ids"])),
    }


def check(tid: str, workspace: Path, full: bool, timeout: int) -> dict:
    """Grade the workspace through a rebuilt tree; the workspace itself is not modified."""
    task = TASKS[tid]
    if not all((workspace / d).is_dir() for d in ("hooks", "tests")):
        raise ValueError(f"not a prepared workspace (no hooks/ and tests/): {workspace}")
    result: dict = {"task": tid, "full_suite_run": full}
    with tempfile.TemporaryDirectory(prefix="oracle_", ignore_cleanup_errors=True) as tmp:
        base, graded, control = (Path(tmp) / n for n in ("base", "graded", "control"))
        export(task["parent"], base)
        before, after = manifest(base), manifest(workspace)
        changed = sorted(r for r in set(before) | set(after) if before.get(r) != after.get(r))
        result["changed_files"] = changed
        result["scope_violations"] = scope_violations(before, after)
        result["test_files_not_executed"] = [r for r in changed if Path(r).parts[0] == "tests"]
        export(task["fix"], control)
        result["control"] = overlay_and_test(task, control, timeout)
        build_graded(task, workspace, changed, graded)
        result["hidden_test"] = overlay_and_test(task, graded, timeout)
        if "passed_ids" in result["control"] and "passed_ids" in result["hidden_test"]:
            result["hidden_lost_passes"] = sorted(
                set(result["control"]["passed_ids"]) - set(result["hidden_test"]["passed_ids"])
            )
        if full:
            baseline = run_pytest(base, "tests", timeout)
            suite = run_pytest(graded, "tests", timeout)
            result["baseline_suite"], result["candidate_suite"] = baseline, suite
            complete = baseline["status"] in ("passed", "failed")
            if complete and "passed_ids" in suite:
                result.update(compare_suites(task, baseline, suite))
    result["state"] = state_of(result)
    return result


def state_of(result: dict) -> str:
    """Result states of the regression set; a broken run is not evidence either way."""
    if result["scope_violations"]:
        return "defect found"
    hidden = result["hidden_test"]["status"]
    if result["control"]["status"] != "passed" or hidden == "infrastructure":
        return "insufficient evidence"
    if hidden != "passed" or result.get("hidden_lost_passes"):
        return "defect found"
    if result.get("new_failures") or result.get("lost_passes"):
        return "defect found"
    if not result["full_suite_run"]:
        return PARTLY
    if "new_failures" not in result:
        return "insufficient evidence"
    return "confirmed by oracle"


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    ap.add_argument("--timeout", type=int, default=900, help="seconds per pytest run")
    ap.add_argument("--out", type=Path, help="append the JSON record to this file")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("selfcheck")
    s.add_argument("tasks", nargs="*", metavar="TASK")
    p = sub.add_parser("prepare")
    p.add_argument("task", choices=TASKS)
    p.add_argument("dest", type=Path)
    c = sub.add_parser("check")
    c.add_argument("task", choices=TASKS)
    c.add_argument("dest", type=Path)
    c.add_argument("--full", action="store_true", help="also compare the whole suite")
    c.add_argument(
        "--run-meta", type=Path, help="JSON about the agent run, stored in the record as given"
    )
    a = ap.parse_args()

    if a.cmd == "prepare":
        task = TASKS[a.task]
        try:
            export(task["parent"], a.dest)
        except (OracleError, subprocess.CalledProcessError, OSError) as exc:
            ap.error(f"cannot prepare the workspace: {exc}")
        print(f"workspace: {a.dest.resolve()} (tree of {task['parent']}, no history)")
        print(f"statement: {task['statement']}")
        print("allowed: change code in hooks/ and scripts/; no network")
        print("existing tests must not change; test files you add are not executed by grading")
        return 0

    # everything that can be wrong with the arguments is checked before a long run
    if a.cmd == "selfcheck":
        unknown = [t for t in a.tasks if t not in TASKS]
        if unknown:
            ap.error(f"unknown task(s): {', '.join(unknown)}")
    meta = None
    if a.cmd == "check" and a.run_meta:
        try:
            meta = json.loads(a.run_meta.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            ap.error(f"cannot read --run-meta: {exc}")
    if a.out:
        try:
            a.out.open("a", encoding="utf-8").close()
        except OSError as exc:
            ap.error(f"cannot write --out: {exc}")
    env = {"python": platform.python_version(), "platform": platform.platform()}
    try:
        env["repo_head"] = git_bytes("rev-parse", "--short", "HEAD").decode().strip()
        if a.cmd == "selfcheck":
            records = [selfcheck(t, a.timeout) for t in a.tasks or TASKS]
            runs = [r[tree]["status"] for r in records for tree in ("parent", "fix")]
            if "infrastructure" in runs:
                code = EXIT_CODES["insufficient evidence"]
            else:
                code = 0 if all(r["oracle_discriminates"] for r in records) else 1
        else:
            try:
                records = [check(a.task, a.dest, a.full, a.timeout)]
            except ValueError as exc:
                ap.error(str(exc))
            code = EXIT_CODES.get(records[0]["state"], 3)
    except Exception as exc:  # any failure of the oracle itself, including tarfile errors
        records = [{"task": getattr(a, "task", None), "state": "insufficient evidence"}]
        records[0]["error"] = f"{type(exc).__name__}: {exc}"
        code = EXIT_CODES["insufficient evidence"]
    for r in records:
        record = {**r, "environment": env}
        if meta is not None:
            record["run_meta"] = meta
        if a.out:  # written first: a console that cannot print must not lose the record
            try:
                with a.out.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError as exc:
                print(f"cannot write --out: {exc}", file=sys.stderr)
                code = EXIT_CODES["insufficient evidence"]
        print(json.dumps(record))
    return code


if __name__ == "__main__":
    sys.exit(main())
