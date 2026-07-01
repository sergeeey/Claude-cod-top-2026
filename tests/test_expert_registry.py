"""Tests for expert_registry.py — RestrictedPython sandbox (PR #138 fix).

WHY: PR #138 removed `__import__` from sandbox builtins. This test suite
verifies the sandbox cannot be escaped via import statements.
"""

import pytest

try:
    import RestrictedPython  # noqa: F401

    RP_AVAILABLE = True
except ImportError:
    RP_AVAILABLE = False

pytestmark = pytest.mark.skipif(not RP_AVAILABLE, reason="RestrictedPython not installed")


class TestBuildRestrictedGlobals:
    def test_no_import_in_builtins(self):
        """PR #138: __import__ must NOT be in sandbox builtins — prevents sandbox escape."""
        import expert_registry

        g = expert_registry._build_restricted_globals()
        builtins = g["__builtins__"]
        assert "__import__" not in builtins

    def test_required_rp_helpers_present(self):
        """Sandbox globals must have all RestrictedPython execution helpers."""
        import expert_registry

        g = expert_registry._build_restricted_globals()
        for key in ("__builtins__", "_getattr_", "_getitem_", "_write_", "_getiter_"):
            assert key in g, f"Missing RestrictedPython helper: {key}"

    def test_sandbox_exec_cannot_import_os(self):
        """'import os' in sandbox raises NameError — __import__ not available."""
        import expert_registry
        from RestrictedPython import compile_restricted

        code = "import os"
        compiled = compile_restricted(code, "<sandbox_test>", "exec")
        g = expert_registry._build_restricted_globals()
        with pytest.raises((NameError, ImportError)):
            exec(compiled, g, {})  # noqa: S102

    def test_builtins_is_dict_not_module(self):
        """__builtins__ must be a dict (restricted), not the full builtins module."""
        import expert_registry

        g = expert_registry._build_restricted_globals()
        assert isinstance(g["__builtins__"], dict), (
            "__builtins__ must be a restricted dict, not the full builtins module"
        )
