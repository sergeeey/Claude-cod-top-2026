"""Tests for expert_registry.py's F-08 fix: refuse unsandboxed execution.

WHY a separate file, not added to test_expert_registry.py: that file's
entire suite is `pytest.mark.skipif(not RP_AVAILABLE)` -- RestrictedPython
is not installed anywhere in this repo (not in requirements.txt, not in
CI), so those tests never run at all (confirmed: this is exactly the "12
skipped" seen in every `pytest tests/` run in this repo). This file tests
the OPPOSITE, always-live path: what happens when RestrictedPython is
NOT available -- which is the actual, currently-exercised behavior in
this repo's real environment, not a hypothetical.

Regression (F-08, security audit 2026-07-12): before this fix, `_execute()`
silently fell back to plain `exec(compiled, {}, namespace)` when sandboxing
failed -- an empty globals dict still gets the real `__builtins__` injected
by Python, so this was full, unrestricted code execution disguised as a
"sandbox". The fix: refuse to run instead of silently degrading.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch


def test_execute_refuses_when_unsandboxed(monkeypatch) -> None:
    """_execute() must return an error, never call exec(), when
    _compile_expert_code reports sandboxed=False -- regardless of whether
    that's because RestrictedPython is absent or rejected the code."""
    import expert_registry

    entry = {"code": "def expert_main(input_data):\n    return {'ok': True}\n"}

    # WHY monkeypatch _compile_expert_code directly instead of relying on
    # RestrictedPython's real absence: makes this test deterministic
    # regardless of what's installed in the environment running it.
    fake_compiled = compile("x = 1", "<fake>", "exec")
    monkeypatch.setattr(
        expert_registry, "_compile_expert_code", lambda code: (fake_compiled, False)
    )

    with patch("expert_registry.exec") as mock_exec:
        result = expert_registry._execute(entry, {})

    mock_exec.assert_not_called()
    assert "error" in result
    assert "unsandboxed" in result["error"].lower()
    assert "output" not in result


def test_execute_refuses_when_restrictedpython_genuinely_absent() -> None:
    """End-to-end (no monkeypatch on _compile_expert_code itself): in THIS
    repo's real environment, RestrictedPython is not installed, so
    _compile_expert_code must report sandboxed=False and _execute() must
    refuse -- not silently run the code unsandboxed."""
    import expert_registry

    try:
        import pytest
        import RestrictedPython  # noqa: F401

        pytest.skip("RestrictedPython is installed in this environment")
    except ImportError:
        pass

    entry = {"code": "def expert_main(input_data):\n    return {'ok': True}\n"}
    result = expert_registry._execute(entry, {})

    assert "error" in result
    assert "output" not in result


def test_execute_error_does_not_leak_builtins_access() -> None:
    """Sanity: the refuse-path error dict must not accidentally still have
    executed attacker-controlled code before returning the error (e.g. via
    a bug where _compile_expert_code's compile() call itself runs code)."""
    import expert_registry

    entry = {
        "code": "import os\nos.environ['SHOULD_NOT_BE_SET'] = 'pwned'\n"
        "def expert_main(input_data):\n    return {'ok': True}\n"
    }
    result = expert_registry._execute(entry, {})

    assert "error" in result
    import os

    assert "SHOULD_NOT_BE_SET" not in os.environ


def test_compile_expert_code_returns_false_without_restrictedpython(monkeypatch) -> None:
    """Direct unit test of _compile_expert_code's ImportError branch."""
    import builtins

    import expert_registry

    real_import = builtins.__import__

    def blocking_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "RestrictedPython":
            raise ImportError("simulated: RestrictedPython not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocking_import)

    compiled, sandboxed = expert_registry._compile_expert_code(
        "def expert_main(input_data):\n    return {}\n"
    )

    assert sandboxed is False
    assert compiled is not None  # still compiles via plain compile(), just not run


class TestRegressionCheckBudget:
    """F-14 (security audit 2026-07-12): compile_expert()'s regression-check
    loop runs under the registry lock -- a hung/slow expert there held the
    lock indefinitely. Fix: a cumulative wall-clock budget, checked before
    each test-case call (not mid-call -- exec() itself can't be safely
    interrupted cross-platform)."""

    def _setup(self, tmp_path, monkeypatch):
        import expert_registry

        registry_path = tmp_path / "expert_registry.json"
        monkeypatch.setattr(expert_registry, "REGISTRY_PATH", registry_path)
        monkeypatch.setattr(expert_registry, "_LOCK_PATH", registry_path.with_suffix(".lock"))
        monkeypatch.setattr(expert_registry, "VAULT_PATH", tmp_path)
        return expert_registry

    def test_budget_exceeded_aborts_before_next_test_case(self, tmp_path, monkeypatch) -> None:
        expert_registry = self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(expert_registry, "_REGRESSION_CHECK_BUDGET_SECONDS", 0.05)

        code = "def expert_main(input_data):\n    return {'ok': True}\n"
        expert_registry.compile_expert(
            "slow_expert",
            code,
            test_cases=[
                {"input": {"i": 0}, "expected": {"ok": True}},
                {"input": {"i": 1}, "expected": {"ok": True}},
                {"input": {"i": 2}, "expected": {"ok": True}},
            ],
        )

        call_count = 0

        def slow_execute(entry: dict, input_data: dict) -> dict:
            nonlocal call_count
            call_count += 1
            import time

            time.sleep(0.08)  # exceeds the 0.05s budget after the first call
            return {"output": {"ok": True}, "elapsed": 0.08}

        monkeypatch.setattr(expert_registry, "_execute", slow_execute)

        import pytest

        with pytest.raises(ValueError, match="exceeded.*budget"):
            expert_registry.compile_expert("slow_expert", code + "\n# recompiled\n")

        # WHY assert call_count < 3, not == 1: the budget check runs BEFORE
        # each call, so exactly how many calls happen before the check trips
        # depends on timing, but it must never reach all 3 test cases.
        assert call_count < 3, "budget check did not abort before exhausting all test cases"

    def test_fast_test_cases_stay_within_budget(self, tmp_path, monkeypatch) -> None:
        """Sanity: the budget must not reject legitimate fast test cases."""
        expert_registry = self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(expert_registry, "_REGRESSION_CHECK_BUDGET_SECONDS", 5.0)

        code = "def expert_main(input_data):\n    return {'ok': True}\n"
        expert_registry.compile_expert(
            "fast_expert",
            code,
            test_cases=[{"input": {}, "expected": {"ok": True}}],
        )

        monkeypatch.setattr(
            expert_registry,
            "_execute",
            lambda entry, input_data: {"output": {"ok": True}, "elapsed": 0.001},
        )

        # Must not raise.
        expert_registry.compile_expert("fast_expert", code + "\n# recompiled\n")
