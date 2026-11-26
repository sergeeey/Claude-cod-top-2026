"""End-to-end checks of pattern_extractor.py as Claude Code runs it: payload on stdin, JSON on stdout.

WHY: the reminder used to take its commit subject from HEAD, not from the commit the command made, so
a non-fix commit could repeat an older fix reminder. These checks pin the behaviour the way the
hook is actually invoked.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "pattern_extractor.py"


def _run(payload: dict) -> str:
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0
    return proc.stdout


def _commit_payload(command: str, stdout: str, stderr: str = "") -> dict:
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"stdout": stdout, "stderr": stderr, "interrupted": False},
    }


def test_fix_commit_reminder_carries_the_commits_own_subject():
    out = _run(
        _commit_payload(
            'git commit -m "fix(hooks): example subject"',
            "[main 1a2b3c4] fix(hooks): example subject\n 1 file changed",
        )
    )
    assert out, "a fix: commit must produce a reminder"
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "1a2b3c4" in context
    assert "fix(hooks): example subject" in context


def test_non_fix_commit_produces_no_reminder_even_when_head_is_a_fix():
    out = _run(
        _commit_payload(
            'git commit -m "feat: unrelated"',
            "[main 9f8e7d6] feat: unrelated\n 2 files changed",
        )
    )
    assert out == ""


def test_output_without_a_commit_line_produces_no_reminder():
    out = _run(_commit_payload('git commit --dry-run -m "fix: x"', "would commit: fix: x"))
    assert out == ""


def test_failed_commit_produces_no_reminder():
    out = _run(
        _commit_payload(
            'git commit -m "fix: x"',
            "",
            stderr="fatal: pathspec 'x' did not match any files",
        )
    )
    assert out == ""


def test_non_commit_command_produces_no_reminder():
    out = _run(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "git status"},
            "tool_response": {"stdout": "clean", "stderr": "", "interrupted": False},
        }
    )
    assert out == ""


@pytest.mark.parametrize("line", ["[main abc1234] fix(x): y", "[feature/a-b 0123456] fix: z"])
def test_commit_line_formats_are_recognised(line: str):
    out = _run(_commit_payload('git commit -m "fix: x"', line))
    assert out and json.loads(out)["hookSpecificOutput"]["hookEventName"] == "PostToolUse"


def _hook_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("pattern_extractor_under_test", HOOK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys_path_entry = str(HOOK.parent)
    if sys_path_entry not in sys.path:
        sys.path.insert(0, sys_path_entry)
    spec.loader.exec_module(module)
    return module


PATTERNS_RU = (
    "## Отладка и фиксы\n\n"
    "### [AVOID×2] Подстрока в команде: wrapper обходит запрет\n"
    "Проверка по подстроке пропускает обёртки.\n\n"
    "### [REPEAT] Проверять ввод до построения пути\n"
    "Сверять внешнее значение с разрешённым набором.\n"
)


def test_known_pattern_in_russian_section_is_found():
    # Matching is lexical: an English subject finds a header only through a shared word.
    module = _hook_module()
    hits = module.find_matching_patterns("fix(hooks): wrapper bypass", PATTERNS_RU)
    assert any("wrapper" in header for header, _ in hits)


def test_unrelated_subject_finds_nothing():
    module = _hook_module()
    assert module.find_matching_patterns("fix(ui): button colour", PATTERNS_RU) == []


def test_headers_outside_the_debugging_section_are_not_matched():
    # Architecture headers must not match: only the debugging section is searched.
    module = _hook_module()
    text = "## Архитектура\n### [AVOID] Путь из repository name в path\nтекст\n"
    assert module.find_matching_patterns("fix(ledger): repository name in path", text) == []
