"""Tests for first_run_check.py — onboarding hook for unconfigured environments."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))


class TestIsFreshInstall:
    def setup_method(self):
        import first_run_check

        self.mod = first_run_check

    def test_fresh_when_no_markers_exist(self, tmp_path):
        with patch.object(self.mod, "INSTALLED_MARKERS", [tmp_path / "missing.md"]):
            assert self.mod._is_fresh_install() is True

    def test_not_fresh_when_marker_exists(self, tmp_path):
        marker = tmp_path / "CLAUDE.md"
        marker.write_text("# config")
        with patch.object(self.mod, "INSTALLED_MARKERS", [marker]):
            assert self.mod._is_fresh_install() is False

    def test_not_fresh_when_any_marker_exists(self, tmp_path):
        existing = tmp_path / "utils.py"
        existing.write_text("# utils")
        markers = [tmp_path / "missing.md", existing]
        with patch.object(self.mod, "INSTALLED_MARKERS", markers):
            assert self.mod._is_fresh_install() is False


class TestMain:
    def setup_method(self):
        import first_run_check

        self.mod = first_run_check

    def _run_main(self, **patches):
        """Run main() with parse_stdin always mocked."""
        base = {"first_run_check.parse_stdin": lambda: None}
        base.update(patches)
        with patch.multiple("first_run_check", **{k.split(".")[-1]: v for k, v in base.items()}):
            return self.mod.main()

    def test_exits_when_recursion_guard_set(self):
        with patch("first_run_check.parse_stdin"):
            with patch("os.environ.get", return_value="agent"):
                with pytest.raises(SystemExit) as exc:
                    self.mod.main()
        assert exc.value.code == 0

    def test_exits_when_sentinel_exists(self, tmp_path):
        sentinel = tmp_path / ".first_run_done"
        sentinel.touch()
        with patch("first_run_check.parse_stdin"):
            with patch.object(self.mod, "SENTINEL", sentinel):
                with patch("os.environ.get", return_value=None):
                    with pytest.raises(SystemExit) as exc:
                        self.mod.main()
        assert exc.value.code == 0

    def test_writes_sentinel_when_config_installed(self, tmp_path):
        sentinel = tmp_path / ".first_run_done"
        marker = tmp_path / "CLAUDE.md"
        marker.write_text("# config")
        with patch("first_run_check.parse_stdin"):
            with patch.object(self.mod, "SENTINEL", sentinel):
                with patch.object(self.mod, "INSTALLED_MARKERS", [marker]):
                    with patch("os.environ.get", return_value=None):
                        with pytest.raises(SystemExit) as exc:
                            self.mod.main()
        assert exc.value.code == 0
        assert sentinel.exists()

    def test_emits_onboarding_when_fresh(self, tmp_path):
        sentinel = tmp_path / ".first_run_done"
        with patch("first_run_check.parse_stdin"):
            with patch.object(self.mod, "SENTINEL", sentinel):
                with patch.object(self.mod, "INSTALLED_MARKERS", [tmp_path / "missing.md"]):
                    with patch("os.environ.get", return_value=None):
                        with patch(
                            "first_run_check.emit_hook_result",
                            side_effect=SystemExit(0),
                        ) as mock_emit:
                            with pytest.raises(SystemExit):
                                self.mod.main()
        mock_emit.assert_called_once()
        args = mock_emit.call_args[0]
        assert "git clone" in args[1]
        assert "install.sh" in args[1]
