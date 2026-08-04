"""Tests for scripts/sync_plugin_hooks.py — hooks.json generator from settings.json.

WHY: 0% coverage before this file. SETTINGS/OUT are module-level Path
constants pointing at the real hooks/settings.json and hooks/hooks.json --
tests monkeypatch both to tmp_path files with small controlled content, so
generation/drift-check logic is verified without depending on this repo's
real (large, frequently-changing) settings.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import sync_plugin_hooks
from sync_plugin_hooks import _substitute, generate, main

SAMPLE_SETTINGS = {
    "hooks": {
        "PostToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "command": "__PYTHON_CMD__ __CLAUDE_HOME__/hooks/example.py",
                    }
                ],
            }
        ]
    }
}


class TestSubstitute:
    def test_replaces_python_cmd_placeholder_in_string(self):
        assert _substitute("__PYTHON_CMD__ foo.py") == "python3 foo.py"

    def test_replaces_claude_home_placeholder_in_string(self):
        result = _substitute("__CLAUDE_HOME__/hooks/x.py")
        assert result == '"${CLAUDE_PLUGIN_ROOT}"/hooks/x.py'

    def test_recurses_into_nested_dicts_and_lists(self):
        data = {"a": [{"b": "__PYTHON_CMD__"}, "__CLAUDE_HOME__"]}
        result = _substitute(data)
        assert result["a"][0]["b"] == "python3"
        assert result["a"][1] == '"${CLAUDE_PLUGIN_ROOT}"'

    def test_leaves_non_placeholder_values_untouched(self):
        assert _substitute(42) == 42
        assert _substitute({"matcher": "Bash"}) == {"matcher": "Bash"}


def _write_settings(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


class TestGenerate:
    def test_produces_hooks_only_json_with_substitutions(self, tmp_path, monkeypatch):
        settings_path = tmp_path / "settings.json"
        _write_settings(settings_path, SAMPLE_SETTINGS)
        monkeypatch.setattr(sync_plugin_hooks, "SETTINGS", settings_path)

        result = generate()
        parsed = json.loads(result)

        assert "hooks" in parsed
        assert "matcher" not in parsed  # only the "hooks" sub-object is kept
        cmd = parsed["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
        assert cmd == 'python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/example.py'

    def test_ends_with_trailing_newline(self, tmp_path, monkeypatch):
        settings_path = tmp_path / "settings.json"
        _write_settings(settings_path, SAMPLE_SETTINGS)
        monkeypatch.setattr(sync_plugin_hooks, "SETTINGS", settings_path)

        assert generate().endswith("\n")


class TestMain:
    def _setup(self, tmp_path, monkeypatch):
        settings_path = tmp_path / "settings.json"
        out_path = tmp_path / "hooks.json"
        _write_settings(settings_path, SAMPLE_SETTINGS)
        monkeypatch.setattr(sync_plugin_hooks, "SETTINGS", settings_path)
        monkeypatch.setattr(sync_plugin_hooks, "OUT", out_path)
        return settings_path, out_path

    def test_check_mode_reports_drift_when_out_missing(self, tmp_path, monkeypatch, capsys):
        self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(sys, "argv", ["sync_plugin_hooks.py", "--check"])

        code = main()

        assert code == 1
        assert "DRIFT" in capsys.readouterr().out

    def test_check_mode_writes_nothing(self, tmp_path, monkeypatch):
        _settings_path, out_path = self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(sys, "argv", ["sync_plugin_hooks.py", "--check"])

        main()

        assert not out_path.exists()

    def test_no_check_mode_writes_generated_file(self, tmp_path, monkeypatch, capsys):
        _settings_path, out_path = self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(sys, "argv", ["sync_plugin_hooks.py"])

        code = main()

        assert code == 0
        assert out_path.exists()
        assert "regenerated" in capsys.readouterr().out

    def test_check_mode_passes_when_already_in_sync(self, tmp_path, monkeypatch, capsys):
        _settings_path, out_path = self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(sys, "argv", ["sync_plugin_hooks.py"])
        main()  # first run writes OUT
        capsys.readouterr()
        monkeypatch.setattr(sys, "argv", ["sync_plugin_hooks.py", "--check"])

        code = main()

        assert code == 0
        assert "already matches" in capsys.readouterr().out
