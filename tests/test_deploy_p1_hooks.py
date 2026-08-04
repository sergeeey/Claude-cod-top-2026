"""Tests for scripts/deploy_p1_hooks.py — methodology-hook global deploy.

WHY: 0% coverage before this file. Every line runs at import time
(no function wrapping the copy loop), and both REPO_HOOKS (derived from
__file__) and GLOBAL_DIR (derived from Path.home()) are module-level
constants. Tests re-import the REAL module fresh each time (not a copy at a
different path -- that would attribute coverage to the wrong file) with
Path.home() monkeypatched to a sandbox dir, so GLOBAL_DIR is always safe;
REPO_HOOKS still resolves to this repo's real hooks/ (all 7 named hooks
genuinely exist there, verified before writing this file). The "hook
missing from this worktree -> SKIP" branch is exercised by narrowly
monkeypatching Path.exists() for exactly one real hook's source path,
delegating every other call to the original implementation.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

MODULE_NAME = "deploy_p1_hooks"
ALL_HOOK_NAMES = [
    "null_results_pre_check",
    "promotion_gate_guard",
    "reject_gate_guard",
    "null_retroscan",
    "weakened_test_guard",
    "commit_test_gate",
    "iteration_guard",
]


def _fresh_import():
    sys.modules.pop(MODULE_NAME, None)
    return importlib.import_module(MODULE_NAME)


def _sandbox_home(tmp_path, monkeypatch):
    home_dir = tmp_path / "home"
    global_dir = home_dir / ".claude" / "hooks"
    global_dir.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home_dir)
    return global_dir


class TestDeployAllPresent:
    def test_copies_every_real_hook_to_sandboxed_global_dir(self, tmp_path, monkeypatch, capsys):
        global_dir = _sandbox_home(tmp_path, monkeypatch)

        _fresh_import()

        for name in ALL_HOOK_NAMES:
            dest = global_dir / f"{name}.py"
            assert dest.exists()
            # WHY compare byte-for-byte against the real repo source, not a
            # stub: confirms shutil.copy2 copied the actual file, not just
            # created a same-named placeholder.
            real_src = Path(__file__).parent.parent / "hooks" / f"{name}.py"
            assert dest.read_bytes() == real_src.read_bytes()

    def test_prints_deployed_line_per_hook_and_done_at_end(self, tmp_path, monkeypatch, capsys):
        _sandbox_home(tmp_path, monkeypatch)

        _fresh_import()

        out = capsys.readouterr().out
        assert "deployed reject_gate_guard.py ->" in out
        assert out.strip().endswith("Done.")


class TestDeploySomeMissing:
    def test_skips_hook_absent_from_worktree_without_crashing(self, tmp_path, monkeypatch, capsys):
        global_dir = _sandbox_home(tmp_path, monkeypatch)
        original_exists = Path.exists

        def fake_exists(self, *args, **kwargs):
            if self.name == "iteration_guard.py" and self.parent.name == "hooks":
                return False
            return original_exists(self, *args, **kwargs)

        monkeypatch.setattr(Path, "exists", fake_exists)

        _fresh_import()

        out = capsys.readouterr().out
        assert "SKIP iteration_guard.py (not in this worktree)" in out
        assert not (global_dir / "iteration_guard.py").exists()
        # The other 6 real hooks were unaffected by the narrow patch.
        assert (global_dir / "promotion_gate_guard.py").exists()
