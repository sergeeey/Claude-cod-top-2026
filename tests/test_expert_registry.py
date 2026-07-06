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


class TestWriteVaultNotePathTraversal:
    """Regression (HIGH, cross-model audit): `entry["name"]` was used
    directly as a filename with zero validation. `compile_expert(name=
    "../x", save_to_vault=True)` -- or worse, a name shaped like an
    absolute path -- wrote OUTSIDE knowledge/experts/ entirely, since
    pathlib's `/` operator fully replaces the base path when the
    right-hand side is itself absolute."""

    def _entry(self, name: str) -> dict:
        return {
            "name": name,
            "tags": [],
            "updated_at": "2026-07-07T00:00:00",
            "version": "1.0",
            "description": "test",
            "input_schema": "",
            "test_cases": [],
        }

    def test_legitimate_snake_case_name_still_works(self, tmp_path, monkeypatch):
        import expert_registry

        monkeypatch.setattr(expert_registry, "VAULT_PATH", tmp_path)
        result = expert_registry._write_vault_note(self._entry("my_expert_v2"))

        assert result is not None
        assert result.parent == tmp_path / "knowledge" / "experts"
        assert result.exists()

    def test_dotdot_traversal_name_rejected(self, tmp_path, monkeypatch):
        import expert_registry

        monkeypatch.setattr(expert_registry, "VAULT_PATH", tmp_path)
        result = expert_registry._write_vault_note(self._entry("../escaped"))

        assert result is None
        # WHY assert nothing escaped, not just "returned None": a None
        # return with a file still written on disk would be a false-safe
        # test -- the real bug was the FILE landing outside the folder.
        assert not (tmp_path / "escaped.md").exists()

    def test_absolute_path_shaped_name_rejected(self, tmp_path, monkeypatch):
        """The more severe variant: a name shaped like an absolute path
        doesn't just escape one level up -- pathlib's `/` operator
        discards the base folder entirely when joined with an absolute
        right-hand side, so this could write ANYWHERE on disk."""
        import expert_registry

        monkeypatch.setattr(expert_registry, "VAULT_PATH", tmp_path)
        hijack_target = tmp_path / "hijacked_elsewhere"
        hijack_target.mkdir()

        result = expert_registry._write_vault_note(self._entry(str(hijack_target / "pwned")))

        assert result is None
        assert not (hijack_target / "pwned.md").exists()

    def test_slash_in_name_rejected(self, tmp_path, monkeypatch):
        import expert_registry

        monkeypatch.setattr(expert_registry, "VAULT_PATH", tmp_path)
        result = expert_registry._write_vault_note(self._entry("sub/dir"))

        assert result is None


_MINIMAL_EXPERT_CODE = "def expert_main(input_data):\n    return {'ok': True}\n"


class TestConcurrentRegistrySaves:
    """Regression (MEDIUM, cross-model audit): compile_expert()/run_expert()/
    rollback()/delete() all did a load-mutate-save sequence sharing the same
    _save() tmp path with no locking -- concurrent calls for DIFFERENT
    experts could lose each other's run_count/last_run/newly-compiled data
    to last-writer-wins."""

    def _setup(self, tmp_path, monkeypatch):
        import expert_registry

        registry_path = tmp_path / "expert_registry.json"
        monkeypatch.setattr(expert_registry, "REGISTRY_PATH", registry_path)
        monkeypatch.setattr(expert_registry, "_LOCK_PATH", registry_path.with_suffix(".lock"))
        monkeypatch.setattr(expert_registry, "VAULT_PATH", tmp_path)
        return expert_registry

    def test_twenty_concurrent_compiles_all_persisted(self, tmp_path, monkeypatch):
        import threading

        expert_registry = self._setup(tmp_path, monkeypatch)

        def compile_one(i: int) -> None:
            expert_registry.compile_expert(f"expert_{i}", _MINIMAL_EXPERT_CODE)

        threads = [threading.Thread(target=compile_one, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final = expert_registry._load()
        assert len(final) == 20
        assert all(f"expert_{i}" in final for i in range(20))

    def test_concurrent_runs_of_different_experts_all_update_stats(self, tmp_path, monkeypatch):
        import threading

        expert_registry = self._setup(tmp_path, monkeypatch)
        for i in range(10):
            expert_registry.compile_expert(f"expert_{i}", _MINIMAL_EXPERT_CODE)

        def run_one(i: int) -> None:
            expert_registry.run_expert(f"expert_{i}", {})

        threads = [threading.Thread(target=run_one, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final = expert_registry._load()
        assert len(final) == 10
        for i in range(10):
            assert final[f"expert_{i}"]["run_count"] == 1

    def test_concurrent_reads_during_compiles_do_not_raise(self, tmp_path, monkeypatch):
        """Regression: this is the exact scenario that first exposed the
        bug -- lookup()/list_all()/search_experts() call _load() WITHOUT
        the lock by design, so an unlocked read can hit a genuine, real
        (reproducible without mocking) Windows PermissionError if it lands
        mid os.replace() from a concurrent locked compile_expert()/
        run_expert(). _save()'s retry-on-PermissionError must close this."""
        import threading

        expert_registry = self._setup(tmp_path, monkeypatch)
        errors: list[BaseException] = []

        def compile_one(i: int) -> None:
            try:
                expert_registry.compile_expert(f"expert_{i}", _MINIMAL_EXPERT_CODE)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        def read_loop() -> None:
            for _ in range(50):
                try:
                    expert_registry.list_all()
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)

        threads = [threading.Thread(target=compile_one, args=(i,)) for i in range(15)]
        threads += [threading.Thread(target=read_loop) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(expert_registry._load()) == 15
