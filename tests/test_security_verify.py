"""Unit tests for hooks/security_verify.py — sensitive file edit warnings.

WHY: security_verify is the PreToolUse guard for high-risk file edits.
Silent failure here means no warning before editing .env or auth files.
"""

import io
import json
from unittest.mock import patch

from utils import is_sensitive_file

# === is_sensitive_file (from utils) ===


class TestIsSensitiveFile:
    def test_env_file_sensitive(self):
        assert is_sensitive_file(".env") is True

    def test_env_local_sensitive(self):
        assert is_sensitive_file(".env.local") is True

    def test_env_production_sensitive(self):
        assert is_sensitive_file(".env.production") is True

    def test_secret_in_path_sensitive(self):
        assert is_sensitive_file("config/secret_config.py") is True

    def test_auth_module_sensitive(self):
        assert is_sensitive_file("hooks/auth_handler.py") is True

    def test_payment_file_sensitive(self):
        assert is_sensitive_file("services/payment_processor.py") is True

    def test_migration_sensitive(self):
        assert is_sensitive_file("db/migrations/0001_initial.py") is True

    def test_token_file_sensitive(self):
        assert is_sensitive_file("config/token_store.py") is True

    def test_crypto_file_sensitive(self):
        assert is_sensitive_file("utils/crypto_helper.py") is True

    def test_regular_utils_not_sensitive(self):
        assert is_sensitive_file("utils/helpers.py") is False

    def test_readme_not_sensitive(self):
        assert is_sensitive_file("README.md") is False

    def test_test_file_not_sensitive(self):
        assert is_sensitive_file("tests/test_input_guard.py") is False

    def test_case_insensitive_auth(self):
        # WHY: is_sensitive_file lowercases path before matching
        assert is_sensitive_file("AUTH_CONFIG.PY") is True

    def test_case_insensitive_payment(self):
        assert is_sensitive_file("PAYMENT_HANDLER.py") is True


# === main() — via stdin ===


class TestMain:
    def _run_main(self, monkeypatch, data: dict) -> str:
        import security_verify

        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            try:
                security_verify.main()
            except SystemExit:
                pass
        return buf.getvalue()

    def test_empty_data_exits_silently(self, monkeypatch):
        out = self._run_main(monkeypatch, {})
        assert out == ""

    def test_no_file_path_exits_silently(self, monkeypatch):
        data = {"tool_name": "Edit", "tool_input": {}}
        out = self._run_main(monkeypatch, data)
        assert out == ""

    def test_non_sensitive_file_no_output(self, monkeypatch):
        data = {"tool_name": "Edit", "tool_input": {"file_path": "utils/helpers.py"}}
        out = self._run_main(monkeypatch, data)
        assert out == ""

    def test_env_file_emits_warning(self, monkeypatch):
        data = {"tool_name": "Edit", "tool_input": {"file_path": ".env"}}
        out = self._run_main(monkeypatch, data)
        assert out != ""
        parsed = json.loads(out.strip())
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "SEC-VERIFY" in ctx
        assert "Sensitive file detected" in ctx

    def test_warning_contains_file_path(self, monkeypatch):
        data = {"tool_name": "Edit", "tool_input": {"file_path": ".env"}}
        out = self._run_main(monkeypatch, data)
        parsed = json.loads(out.strip())
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert ".env" in ctx

    def test_auth_file_triggers_warning(self, monkeypatch):
        data = {"tool_name": "Write", "tool_input": {"file_path": "auth/login.py"}}
        out = self._run_main(monkeypatch, data)
        assert out != ""
        assert "SEC-VERIFY" in out

    def test_payment_file_triggers_warning(self, monkeypatch):
        data = {"tool_name": "Edit", "tool_input": {"file_path": "services/payment/stripe.py"}}
        out = self._run_main(monkeypatch, data)
        assert out != ""
        assert "SEC-VERIFY" in out

    def test_migration_file_triggers_warning(self, monkeypatch):
        data = {"tool_name": "Edit", "tool_input": {"file_path": "db/migrations/002_add_users.py"}}
        out = self._run_main(monkeypatch, data)
        assert out != ""

    def test_nested_tool_input_format(self, monkeypatch):
        # WHY: some hooks receive flat format, not nested tool_input dict
        data = {"file_path": ".env.local"}
        out = self._run_main(monkeypatch, data)
        assert out != ""
