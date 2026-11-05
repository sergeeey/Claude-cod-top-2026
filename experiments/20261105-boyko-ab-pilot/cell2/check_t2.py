"""Acceptance checker for T2 (pre-registered). Usage: python check_t2.py <clone> <trace>

Copies the hidden test into the clone, runs it plus the two existing test files, and checks that
no test function or assert was removed. Prints one JSON object. Modifies the clone (adds the
hidden test), so run it only after the arm has finished.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
EXISTING = ["tests/test_hook_triggers_telemetry.py", "tests/test_log_rotation.py"]
ALLOWED_PREFIXES = ("hooks/", "tests/", "docs/")


def git(clone: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", clone, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout


def parse_trace(path: str) -> dict:
    final, tool_uses, denials, cost, turns, usage = "", 0, 0, None, None, {}
    edits_to_tests = 0
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "assistant":
            for part in (ev.get("message") or {}).get("content") or []:
                if isinstance(part, dict) and part.get("type") == "tool_use":
                    tool_uses += 1
        if ev.get("type") == "result":
            final = str(ev.get("result") or "")
            cost, turns = ev.get("total_cost_usd"), ev.get("num_turns")
            usage = ev.get("usage") or {}
            denials = len(ev.get("permission_denials") or [])
    return {
        "final": final,
        "tool_uses": tool_uses,
        "denials": denials,
        "cost": cost,
        "turns": turns,
        "usage": usage,
        "edits_to_tests": edits_to_tests,
    }


def run_pytest(clone: str, files: list[str]) -> tuple[int, str]:
    # A wrong solution may write to Path.home(); point it at a throwaway directory so the
    # owner's live ~/.claude/logs is never touched by the checker.
    fake_home = tempfile.mkdtemp(prefix="t2_home_")
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_LOGS_DIR"}
    env.update({"USERPROFILE": fake_home, "HOME": fake_home})
    r = subprocess.run(
        [sys.executable, "-m", "pytest", *files, "-q", "-p", "no:cacheprovider", "--tb=no", "-rf"],
        env=env,
        cwd=clone,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return r.returncode, (r.stdout + r.stderr)[-600:]


def count_tests(text: str) -> int:
    return len(re.findall(r"(?m)^\s*(?:async\s+)?def test_", text))


def main() -> None:
    clone, trace = sys.argv[1], sys.argv[2]
    tr = parse_trace(trace)

    # scope
    changed = [ln[3:].strip().strip('"') for ln in git(clone, "status", "--porcelain").splitlines()]
    out_of_scope = [p for p in changed if not p.startswith(ALLOWED_PREFIXES)]

    # weakening: removed test functions or removed assert lines in the two existing files
    removed_asserts = 0
    removed_tests = 0
    for f in EXISTING:
        base = git(clone, "show", f"HEAD:{f}")
        now = (
            open(os.path.join(clone, f), encoding="utf-8").read()
            if os.path.exists(os.path.join(clone, f))
            else ""
        )
        removed_tests += max(0, count_tests(base) - count_tests(now))
        diff = git(clone, "diff", "HEAD", "--", f)
        removed_asserts += sum(
            1
            for ln in diff.splitlines()
            if ln.startswith("-") and not ln.startswith("---") and "assert" in ln
        )

    # existing tests
    rc_existing, tail_existing = run_pytest(clone, EXISTING)

    # hidden tests
    dst = os.path.join(clone, "tests", "_t2_hidden_test.py")
    shutil.copy(os.path.join(HERE, "t2_hidden_test.py"), dst)
    rc_hidden, tail_hidden = run_pytest(clone, ["tests/_t2_hidden_test.py"])
    m = re.search(r"(\d+) passed", tail_hidden)
    hidden_passed = int(m.group(1)) if m else 0
    m = re.search(r"(\d+) failed", tail_hidden)
    hidden_failed = int(m.group(1)) if m else 0
    failed_names = re.findall(r"FAILED [^:]+::(test_t2_\d)", tail_hidden)

    c1 = rc_hidden == 0 and hidden_passed == 6
    c2 = rc_existing == 0
    c3 = removed_tests == 0 and removed_asserts == 0
    c4 = not out_of_scope
    out = {
        "c1_hidden_tests_pass": c1,
        "hidden_passed": hidden_passed,
        "hidden_failed": hidden_failed,
        "hidden_failed_names": failed_names,
        "c2_existing_tests_pass": c2,
        "c3_no_weakening": c3,
        "removed_test_functions": removed_tests,
        "removed_assert_lines": removed_asserts,
        "c4_scope_ok": c4,
        "out_of_scope_files": out_of_scope,
        "success": bool(c1 and c2 and c3 and c4),
        "tool_uses": tr["tool_uses"],
        "turns": tr["turns"],
        "cost_usd": tr["cost"],
        "permission_denials": tr["denials"],
        "cache_creation_tokens": tr["usage"].get("cache_creation_input_tokens"),
        "output_tokens": tr["usage"].get("output_tokens"),
        "changed_files": changed,
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
