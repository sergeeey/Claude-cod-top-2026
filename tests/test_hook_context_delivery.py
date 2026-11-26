"""A hook that delivers its result on stdout must not run behind async_wrapper.py.

WHY: async_wrapper.py starts the real hook as a detached process and sends that process's stdout to
DEVNULL. A hook that delivers context through emit_hook_result() writes its JSON to stdout, so the
wrapper discards it. Found 2026-11-26: pattern_extractor's reminder never reached the model, because
the manifests wrapped it. This test keeps that class of defect from returning.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = [ROOT / "hooks" / "settings.json", ROOT / "hooks" / "hooks.json"]


def wrapped_scripts(manifest: Path) -> set[str]:
    """Names of the hook scripts that a manifest runs through async_wrapper.py."""
    names: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            command = node.get("command")
            if isinstance(command, str) and "async_wrapper.py" in command:
                names.update(re.findall(r"hooks/(\w+)\.py", command))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(manifest.read_text(encoding="utf-8")))
    return names


def emits_on_stdout(script: Path) -> bool:
    """True if the script calls emit_hook_result (a call, not a mention in a comment or docstring)."""
    tree = ast.parse(script.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name == "emit_hook_result":
                return True
    return False


@pytest.mark.parametrize("manifest", MANIFESTS, ids=lambda p: p.name)
def test_no_stdout_emitting_hook_is_wrapped(manifest: Path) -> None:
    for name in sorted(wrapped_scripts(manifest)):
        script = ROOT / "hooks" / f"{name}.py"
        assert script.exists(), f"{manifest.name} wraps a missing script: {name}"
        assert not emits_on_stdout(script), (
            f"{manifest.name}: {name} emits its result on stdout but runs behind "
            "async_wrapper.py, which discards stdout"
        )


@pytest.mark.parametrize("manifest", MANIFESTS, ids=lambda p: p.name)
def test_pattern_extractor_runs_unwrapped(manifest: Path) -> None:
    assert "pattern_extractor" not in wrapped_scripts(manifest)


def test_detector_positive_control(tmp_path: Path) -> None:
    script = tmp_path / "emits.py"
    script.write_text(
        "from lib.runtime import emit_hook_result\nemit_hook_result('PostToolUse', 'x')\n",
        encoding="utf-8",
    )
    assert emits_on_stdout(script)


def test_detector_negative_control_docstring_only(tmp_path: Path) -> None:
    script = tmp_path / "mentions.py"
    script.write_text(
        '"""This hook never calls emit_hook_result."""\nprint("silent")\n', encoding="utf-8"
    )
    assert not emits_on_stdout(script)
