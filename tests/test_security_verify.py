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

    def test_malformed_json_asks_instead_of_silent(self, monkeypatch):
        """Regression (issue #195 follow-up, external audit 2026-07-15):
        malformed JSON previously fell through parse_stdin()'s {} default
        and exited silently -- identical to "nothing to check", so a
        sensitive-file edit riding alongside a broken hook input would never
        be flagged. Now escalates to "ask", matching this hook's own
        established response to a genuine sensitive-file match."""
        import security_verify

        monkeypatch.setattr("sys.stdin", io.StringIO("not valid json {"))
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            try:
                security_verify.main()
            except SystemExit:
                pass
        out = buf.getvalue()
        assert '"permissionDecision": "ask"' in out or '"permissionDecision":"ask"' in out

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
        hook_out = parsed["hookSpecificOutput"]
        # WHY: migrated to permissionDecision protocol — reason is in permissionDecisionReason,
        # additionalContext carries the SEC-VERIFY inline hint for Claude's context window
        assert hook_out.get("permissionDecision") == "ask"
        reason = hook_out.get("permissionDecisionReason", "")
        assert "Sensitive file detected" in reason

    def test_warning_contains_file_path(self, monkeypatch):
        data = {"tool_name": "Edit", "tool_input": {"file_path": ".env"}}
        out = self._run_main(monkeypatch, data)
        parsed = json.loads(out.strip())
        hook_out = parsed["hookSpecificOutput"]
        # File path appears in permissionDecisionReason (surfaced to user)
        reason = hook_out.get("permissionDecisionReason", "")
        assert ".env" in reason

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

    def test_bash_redirect_into_dotenv_triggers_warning(self, monkeypatch):
        """Regression (MEDIUM): a Bash command has no file_path field at all,
        so "printf secret > .env" previously bypassed this gate entirely --
        it only ever looked at tool_input["file_path"]."""
        data = {"tool_name": "Bash", "tool_input": {"command": "printf secret > .env"}}
        out = self._run_main(monkeypatch, data)
        assert out != ""
        parsed = json.loads(out.strip())
        reason = parsed["hookSpecificOutput"].get("permissionDecisionReason", "")
        assert ".env" in reason

    def test_bash_append_redirect_into_secrets_triggers_warning(self, monkeypatch):
        data = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo token >> config/secrets.yml"},
        }
        out = self._run_main(monkeypatch, data)
        assert out != ""

    def test_bash_redirect_into_non_sensitive_file_is_silent(self, monkeypatch):
        data = {"tool_name": "Bash", "tool_input": {"command": "echo hello > notes.txt"}}
        out = self._run_main(monkeypatch, data)
        assert out == ""

    def test_bash_without_redirect_is_silent(self, monkeypatch):
        data = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        out = self._run_main(monkeypatch, data)
        assert out == ""

    def test_bash_force_redirect_operator_into_dotenv_triggers_warning(self, monkeypatch):
        """Regression (cross-model review): ">|" (force-overwrite) previously
        made the target-capture group swallow the "|" itself instead of the
        real filename."""
        data = {"tool_name": "Bash", "tool_input": {"command": "printf SECRET >| .env"}}
        out = self._run_main(monkeypatch, data)
        assert out != ""

    def test_bash_tee_into_dotenv_triggers_warning(self, monkeypatch):
        """Regression: tee reads stdin and writes via its own argument --
        there's no ">" at all, so the old regex-only approach missed it."""
        data = {"tool_name": "Bash", "tool_input": {"command": "printf SECRET | tee .env"}}
        out = self._run_main(monkeypatch, data)
        assert out != ""

    def test_bash_tee_append_flag_into_secrets_triggers_warning(self, monkeypatch):
        data = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo token | tee -a config/secrets.yml"},
        }
        out = self._run_main(monkeypatch, data)
        assert out != ""

    def test_bash_dd_of_into_dotenv_triggers_warning(self, monkeypatch):
        """Regression: dd's target is an "of=" keyword argument, not a shell
        redirect, so it also had no ">" for the old regex to match."""
        data = {"tool_name": "Bash", "tool_input": {"command": "dd if=/dev/null of=.env"}}
        out = self._run_main(monkeypatch, data)
        assert out != ""

    def test_bash_redirect_into_quoted_path_with_space_triggers_warning(self, monkeypatch):
        """Regression: a bare \\S+ capture previously grabbed only the quote
        plus first word ("safe) of a quoted, space-containing target."""
        data = {
            "tool_name": "Bash",
            "tool_input": {"command": 'printf SECRET > "safe dir/.env"'},
        }
        out = self._run_main(monkeypatch, data)
        assert out != ""

    def test_bash_tee_stops_at_chained_command_operator(self, monkeypatch):
        """Sanity check: tee-target extraction must not wander past a chained
        command into treating "&&"/"rm"/"-rf" as tee's own file arguments in
        a way that would ever suppress or corrupt the real warning."""
        data = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo x | tee notes.txt && rm -rf /tmp/scratch"},
        }
        out = self._run_main(monkeypatch, data)
        # notes.txt is not sensitive, so this specific command stays silent --
        # the point of this test is that main() doesn't raise/misbehave when
        # a chained command follows tee's target.
        assert out == ""
