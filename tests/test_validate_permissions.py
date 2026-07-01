"""Tests for scripts/validate_permissions.py — structured permission pattern validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from validate_permissions import validate_file, validate_settings


class TestValidSettings:
    def test_empty_lists(self):
        result = validate_settings({"permissions": {"allow": [], "deny": []}})
        assert result.ok
        assert result.errors == []

    def test_bare_known_tool(self):
        result = validate_settings({"permissions": {"allow": ["Bash", "Read"], "deny": []}})
        assert result.ok

    def test_tool_with_glob(self):
        result = validate_settings(
            {"permissions": {"allow": ["Bash(git *)"], "deny": ["Write(*.env)"]}}
        )
        assert result.ok

    def test_no_permissions_key(self):
        result = validate_settings({})
        assert result.ok  # missing key -> treated as empty dict -> no errors


class TestMalformedPatterns:
    def test_starts_with_digit(self):
        result = validate_settings({"permissions": {"allow": ["123bad"], "deny": []}})
        assert not result.ok
        assert any("malformed" in e for e in result.errors)

    def test_empty_glob(self):
        result = validate_settings({"permissions": {"allow": ["Bash()"], "deny": []}})
        assert not result.ok
        assert any("empty glob" in e for e in result.errors)

    def test_nonstring_pattern(self):
        result = validate_settings({"permissions": {"allow": [42], "deny": []}})
        assert not result.ok
        assert any("non-string" in e for e in result.errors)


class TestContradictions:
    def test_same_pattern_in_allow_and_deny(self):
        result = validate_settings(
            {
                "permissions": {
                    "allow": ["Bash(git *)"],
                    "deny": ["Bash(git *)"],
                }
            }
        )
        assert not result.ok
        assert any("contradiction" in e for e in result.errors)

    def test_different_patterns_no_contradiction(self):
        result = validate_settings(
            {
                "permissions": {
                    "allow": ["Bash(git status)"],
                    "deny": ["Bash(rm -rf *)"],
                }
            }
        )
        assert result.ok


class TestMcpPatterns:
    def test_valid_mcp_three_parts(self):
        result = validate_settings({"permissions": {"allow": ["mcp__server__tool"], "deny": []}})
        assert result.ok
        assert result.warnings == []

    def test_mcp_too_short_warns(self):
        result = validate_settings({"permissions": {"allow": ["mcp__server"], "deny": []}})
        assert result.ok  # warning, not error
        assert any("fewer than 3 parts" in w for w in result.warnings)


class TestUnknownTools:
    def test_unknown_tool_name_warns_not_errors(self):
        result = validate_settings({"permissions": {"allow": ["FutureTool(*)"], "deny": []}})
        assert result.ok
        assert any("unrecognized tool" in w for w in result.warnings)

    def test_known_tools_no_warning(self):
        result = validate_settings(
            {"permissions": {"allow": ["Bash", "Read", "Write", "Edit"], "deny": []}}
        )
        assert result.ok
        assert result.warnings == []


class TestSchemaErrors:
    def test_permissions_not_dict(self):
        result = validate_settings({"permissions": "bad_value"})
        assert not result.ok

    def test_allow_not_list(self):
        result = validate_settings({"permissions": {"allow": "Bash", "deny": []}})
        assert not result.ok

    def test_deny_not_list(self):
        result = validate_settings({"permissions": {"allow": [], "deny": "Write"}})
        assert not result.ok


class TestValidateFile:
    def test_file_not_found(self, tmp_path):
        result = validate_file(tmp_path / "nonexistent.json")
        assert not result.ok
        assert any("cannot read" in e for e in result.errors)

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not json}", encoding="utf-8")
        result = validate_file(p)
        assert not result.ok
        assert any("invalid JSON" in e for e in result.errors)

    def test_valid_file(self, tmp_path):
        p = tmp_path / "settings.json"
        p.write_text(
            json.dumps({"permissions": {"allow": ["Bash", "Read"], "deny": ["Bash(rm -rf *)"]}})
        )
        result = validate_file(p)
        assert result.ok
