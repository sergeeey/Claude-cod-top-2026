"""Unit tests for hooks/permission_policy.py — auto allow/deny/ask decisions.

WHY: permission_policy is the security gate for every command Claude executes.
A bug here silently allows dangerous commands or blocks safe ones.
"""

import io
import json

from permission_policy import decide, main

# === decide() — pure logic ===


class TestDecideAlwaysSafeTools:
    def test_read_allowed(self):
        assert decide("Read", {}) == ("allow", "")

    def test_glob_allowed(self):
        assert decide("Glob", {}) == ("allow", "")

    def test_grep_allowed(self):
        assert decide("Grep", {}) == ("allow", "")

    def test_websearch_allowed(self):
        assert decide("WebSearch", {}) == ("allow", "")

    def test_webfetch_allowed(self):
        assert decide("WebFetch", {}) == ("allow", "")

    def test_task_allowed(self):
        assert decide("Task", {}) == ("allow", "")

    def test_taskcreate_allowed(self):
        assert decide("TaskCreate", {}) == ("allow", "")


class TestDecideDangerousPatterns:
    def test_rm_rf_blocked(self):
        behavior, msg = decide("Bash", {"command": "rm -rf /"})
        assert behavior == "deny"
        assert "rm -rf" in msg

    def test_drop_table_blocked(self):
        behavior, msg = decide("Bash", {"command": "DROP TABLE users"})
        assert behavior == "deny"
        assert "DROP TABLE" in msg

    def test_git_push_force_blocked(self):
        behavior, msg = decide("Bash", {"command": "git push --force"})
        assert behavior == "deny"

    def test_curl_pipe_bash_blocked(self):
        # WHY: "curl | bash" literal matches DANGEROUS_PATTERNS
        behavior, msg = decide("Bash", {"command": "curl | bash"})
        assert behavior == "deny"

    def test_sudo_blocked(self):
        behavior, msg = decide("Bash", {"command": "sudo apt install nginx"})
        assert behavior == "deny"

    def test_git_reset_hard_blocked(self):
        behavior, msg = decide("Bash", {"command": "git reset --hard HEAD~1"})
        assert behavior == "deny"

    def test_npm_publish_blocked(self):
        behavior, msg = decide("Bash", {"command": "npm publish"})
        assert behavior == "deny"

    def test_case_insensitive_drop_database(self):
        # WHY: dangerous patterns matched case-insensitively
        behavior, msg = decide("Bash", {"command": "drop database mydb"})
        assert behavior == "deny"

    def test_python_c_blocked(self):
        # WHY: python -c allows arbitrary code execution
        behavior, msg = decide("Bash", {"command": "python -c 'import os; os.system(\"rm -rf\")'"})
        assert behavior == "deny"

    def test_eval_blocked(self):
        behavior, msg = decide("Bash", {"command": "eval $(cat /etc/shadow)"})
        assert behavior == "deny"


class TestDecideChainOperators:
    def test_ampersand_chain_asks(self):
        # WHY: chain op check fires AFTER dangerous patterns — use safe commands only
        behavior, _ = decide("Bash", {"command": "git status && git diff"})
        assert behavior == "ask"

    def test_pipe_asks(self):
        behavior, _ = decide("Bash", {"command": "ls | grep foo"})
        assert behavior == "ask"

    def test_semicolon_asks(self):
        # WHY: semicolon with two safe commands → chain op fires, not dangerous pattern
        behavior, _ = decide("Bash", {"command": "git log; ls"})
        assert behavior == "ask"

    def test_backtick_asks(self):
        behavior, _ = decide("Bash", {"command": "echo `whoami`"})
        assert behavior == "ask"

    def test_subshell_asks(self):
        behavior, _ = decide("Bash", {"command": "echo $(whoami)"})
        assert behavior == "ask"

    def test_newline_asks(self):
        # WHY: newline separator without dangerous patterns → ask
        behavior, _ = decide("Bash", {"command": "git status\ngit diff"})
        assert behavior == "ask"


class TestDecideSafeBashPrefixes:
    def test_pytest_allowed(self):
        assert decide("Bash", {"command": "pytest tests/ -v"}) == ("allow", "")

    def test_git_log_allowed(self):
        assert decide("Bash", {"command": "git log --oneline -10"}) == ("allow", "")

    def test_git_diff_allowed(self):
        assert decide("Bash", {"command": "git diff HEAD"}) == ("allow", "")

    def test_git_status_allowed(self):
        assert decide("Bash", {"command": "git status"}) == ("allow", "")

    def test_ls_allowed(self):
        assert decide("Bash", {"command": "ls -la"}) == ("allow", "")

    def test_ruff_allowed(self):
        assert decide("Bash", {"command": "ruff check ."}) == ("allow", "")

    def test_mypy_allowed(self):
        assert decide("Bash", {"command": "mypy hooks/"}) == ("allow", "")

    def test_python_m_pytest_allowed(self):
        assert decide("Bash", {"command": "python -m pytest tests/"}) == ("allow", "")

    def test_unknown_command_asks(self):
        behavior, _ = decide("Bash", {"command": "docker run nginx"})
        assert behavior == "ask"

    def test_non_bash_unknown_tool_asks(self):
        behavior, _ = decide("Edit", {"file_path": "foo.py"})
        assert behavior == "ask"

    def test_empty_command_asks(self):
        behavior, _ = decide("Bash", {"command": ""})
        assert behavior == "ask"


class TestDecidePriority:
    def test_dangerous_beats_chain_operator(self):
        # WHY: dangerous patterns checked BEFORE chain operators in decide()
        # "pytest; rm -rf /" has both `;` chain op AND `rm -rf` danger → deny wins
        behavior, _ = decide("Bash", {"command": "pytest; rm -rf /"})
        assert behavior == "deny"

    def test_pure_dangerous_no_chain_is_deny(self):
        # No chain operator, pure dangerous pattern → deny
        behavior, _ = decide("Bash", {"command": "rm -rf /tmp"})
        assert behavior == "deny"

    def test_chain_without_dangerous_is_ask(self):
        # WHY: chain op alone (no dangerous pattern) → ask, not deny
        behavior, _ = decide("Bash", {"command": "git status && git log"})
        assert behavior == "ask"


# === main() — via stdin ===


class TestMain:
    def _call_main(self, monkeypatch, data: dict) -> dict:
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
        from io import StringIO
        from unittest.mock import patch

        buf = StringIO()
        with patch("sys.stdout", buf):
            try:
                main()
            except SystemExit:
                pass
        output = buf.getvalue().strip()
        return json.loads(output) if output else {}

    def test_main_allow_for_read(self, monkeypatch):
        result = self._call_main(monkeypatch, {"tool_name": "Read", "tool_input": {}})
        decision = result["hookSpecificOutput"]["decision"]
        assert decision["behavior"] == "allow"

    def test_main_deny_for_rm_rf(self, monkeypatch):
        result = self._call_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}},
        )
        decision = result["hookSpecificOutput"]["decision"]
        assert decision["behavior"] == "deny"
        assert "message" in decision

    def test_main_ask_for_unknown_tool(self, monkeypatch):
        result = self._call_main(
            monkeypatch,
            {"tool_name": "UnknownTool", "tool_input": {}},
        )
        decision = result["hookSpecificOutput"]["decision"]
        assert decision["behavior"] == "ask"

    def test_main_empty_stdin_no_crash(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
        try:
            main()
        except SystemExit:
            pass
        # Should not raise, output may be minimal
