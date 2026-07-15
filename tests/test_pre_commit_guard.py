"""Tests for pre_commit_guard.py.

WHY: pre_commit_guard is a security-critical hook. It blocks commits to main/master
and pushes to public repos. Tests guarantee that critical checks work
via mocking stdin and run_git, without real git operations.
"""

import io
import json
import os
import sys

# WHY: hooks live one level above tests/. insert(0) ensures priority
# over site-packages during import.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402


def make_stdin(data: dict) -> io.StringIO:
    """Helper function to mock stdin with JSON data."""
    return io.StringIO(json.dumps(data))


def make_bash_input(command: str) -> dict:
    """Create typical hook data for a Bash command."""
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


class TestExtractCommandCwd:
    """Tests for extract_command_cwd() — parsing a leading `cd <dir> &&`."""

    def test_extracts_quoted_path_before_double_ampersand(self) -> None:
        import pre_commit_guard

        cwd = pre_commit_guard.extract_command_cwd('cd "E:\\path with spaces" && git commit -m "x"')
        assert cwd == "E:\\path with spaces"

    def test_extracts_unquoted_path_before_semicolon(self) -> None:
        import pre_commit_guard

        cwd = pre_commit_guard.extract_command_cwd("cd /repo/other; git commit -m x")
        assert cwd == "/repo/other"

    def test_returns_none_when_no_leading_cd(self) -> None:
        import pre_commit_guard

        assert pre_commit_guard.extract_command_cwd('git commit -m "no cd here"') is None

    def test_returns_none_for_bare_cd_with_nothing_chained(self) -> None:
        """WHY: `cd X` with nothing chained after doesn't confirm a
        directory-then-command pattern — must not false-match."""
        import pre_commit_guard

        assert pre_commit_guard.extract_command_cwd("cd /some/dir") is None


class TestCommandHasGitCommit:
    """Tests for _command_has_git_commit() — token-wise detection that
    survives global options like `-C <repo>` between `git` and `commit`."""

    def test_plain_git_commit(self) -> None:
        import pre_commit_guard

        assert pre_commit_guard._command_has_git_commit('git commit -m "x"') is True

    def test_dash_capital_c_bypass_now_detected(self) -> None:
        """Regression (HIGH, hooks-02 audit): `git -C <repo> commit` bypassed
        the old literal-substring `"git commit" not in command` check."""
        import pre_commit_guard

        assert pre_commit_guard._command_has_git_commit('git -C /other/repo commit -m "x"') is True

    def test_dash_lowercase_c_config_override_bypass_now_detected(self) -> None:
        import pre_commit_guard

        assert (
            pre_commit_guard._command_has_git_commit('git -c user.name=bot commit -m "x"') is True
        )

    def test_quoted_dash_capital_c_value_with_space(self) -> None:
        import pre_commit_guard

        assert pre_commit_guard._command_has_git_commit('git -C "my repo" commit -m "x"') is True

    def test_commit_after_cd_chain(self) -> None:
        import pre_commit_guard

        assert pre_commit_guard._command_has_git_commit('cd /tmp && git commit -m "x"') is True

    def test_commit_on_second_line_of_multiline_command(self) -> None:
        import pre_commit_guard

        assert pre_commit_guard._command_has_git_commit("echo preparing\ngit commit -m x") is True

    def test_non_commit_git_invocation_not_flagged(self) -> None:
        import pre_commit_guard

        assert pre_commit_guard._command_has_git_commit("git status") is False

    def test_unrelated_command_not_flagged(self) -> None:
        import pre_commit_guard

        assert pre_commit_guard._command_has_git_commit("ls -la") is False

    def test_heredoc_body_mentioning_git_commit_not_flagged(self) -> None:
        """Regression (P2, cross-model review of this same fix): splitting
        on bare newline treated a heredoc BODY line as its own statement, so
        `cat <<EOF\\ngit commit -m test\\nEOF` false-positived as a real
        commit -- that text is payload for `cat`, never executed. Mirrors
        the heredoc-awareness already proven correct in commit_test_gate.py."""
        import pre_commit_guard

        cmd = "cat <<EOF > notes.txt\ngit commit -m test\nEOF"
        assert pre_commit_guard._command_has_git_commit(cmd) is False

    def test_heredoc_indented_terminator_still_recognized(self) -> None:
        """`<<-TERM` allows the terminator line to be indented -- must still
        correctly close the heredoc, not treat everything after as one
        giant unterminated block."""
        import pre_commit_guard

        cmd = "cat <<-EOF\n\tgit commit -m test\n\tEOF\ngit commit -m real"
        assert pre_commit_guard._command_has_git_commit(cmd) is True

    def test_real_commit_after_heredoc_still_detected(self) -> None:
        import pre_commit_guard

        cmd = 'cat <<EOF > notes.txt\nsome notes\nEOF\ngit commit -m "real commit"'
        assert pre_commit_guard._command_has_git_commit(cmd) is True


class TestCommandPushesPublicMain:
    """Tests for _command_pushes_public_main()."""

    def test_plain_push_public_main(self) -> None:
        import pre_commit_guard

        assert pre_commit_guard._command_pushes_public_main("git push public main") is True

    def test_push_public_master(self) -> None:
        import pre_commit_guard

        assert pre_commit_guard._command_pushes_public_main("git push public master") is True

    def test_push_after_cd_chain_now_detected(self) -> None:
        """Regression (MEDIUM, hooks-02 audit): only `command.split("\\n")[0]`
        was checked, so a leading `cd <repo> &&` prefix bypassed detection
        entirely since the resulting first line didn't start with "git push"."""
        import pre_commit_guard

        assert (
            pre_commit_guard._command_pushes_public_main("cd /tmp/repo && git push public main")
            is True
        )

    def test_push_on_second_line_now_detected(self) -> None:
        import pre_commit_guard

        assert pre_commit_guard._command_pushes_public_main("echo hi\ngit push public main") is True

    def test_refspec_form_head_colon_main(self) -> None:
        import pre_commit_guard

        assert pre_commit_guard._command_pushes_public_main("git push public HEAD:main") is True

    def test_branch_name_containing_main_as_substring_not_flagged(self) -> None:
        """Regression (LOW, hooks-02 audit): the old substring check
        (`"main" in first_line`) false-positived on any branch name merely
        CONTAINING "main", e.g. "domain-fix" -- must require an exact
        branch-name match, not a substring match."""
        import pre_commit_guard

        assert pre_commit_guard._command_pushes_public_main("git push public domain-fix") is False

    def test_push_feature_branch_not_flagged(self) -> None:
        import pre_commit_guard

        assert pre_commit_guard._command_pushes_public_main("git push public feature/x") is False

    def test_push_main_to_origin_not_public_not_flagged(self) -> None:
        import pre_commit_guard

        assert pre_commit_guard._command_pushes_public_main("git push origin main") is False


class TestPreCommitGuardMain:
    """Tests for main() via mocking stdin and run_git."""

    def test_branch_check_passes_extracted_cwd_to_run_git(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression: Check 1 must pass the real target repo's cwd (parsed from
        a leading `cd X &&`) to run_git, instead of relying on the hook process's
        own cwd — otherwise the branch-check always inspects the WRONG repo in a
        multi-repo session."""
        data = make_bash_input('cd "/target/repo" && git commit -m "feat: x"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        captured_calls: list[tuple[list, dict]] = []

        def mock_run_git(args: list, **kwargs) -> str:
            captured_calls.append((args, kwargs))
            return "feature/ok"  # non-main → no block, main() returns early after Check 1

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            pre_commit_guard.main()

        branch_call = next(c for c in captured_calls if "--abbrev-ref" in c[0])
        assert branch_call[1].get("cwd") == "/target/repo"

    def test_skips_non_git_commit(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Command 'ls' — not git commit, hook should exit without output."""
        data = make_bash_input("ls -la")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import pre_commit_guard

        pre_commit_guard.main()

        captured = capsys.readouterr()
        # WHY: hook does early return — no output to stdout/stderr
        assert captured.out == ""
        assert captured.err == ""

    def test_blocks_commit_to_main(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Commit to main → permissionDecision:deny + exit(0) (SDK protocol)."""
        data = make_bash_input('git commit -m "feat: some change"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        # WHY: mock run_git returns "main" for rev-parse --abbrev-ref HEAD
        with patch("pre_commit_guard.run_git", return_value="main"):
            import pre_commit_guard

            with pytest.raises(SystemExit) as exc_info:
                pre_commit_guard.main()

        # WHY: exit(0) after permissionDecision — block is in JSON, not exit code
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert '"permissionDecision": "deny"' in captured.out
        assert "main" in captured.out

    def test_blocks_commit_to_master(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Commit to master → permissionDecision:deny + exit(0) (SDK protocol)."""
        data = make_bash_input('git commit -m "fix: hotfix"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        with patch("pre_commit_guard.run_git", return_value="master"):
            import pre_commit_guard

            with pytest.raises(SystemExit) as exc_info:
                pre_commit_guard.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert '"permissionDecision": "deny"' in captured.out
        assert "master" in captured.out

    def test_allows_commit_to_feature(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Commit to feature branch is allowed — hook does not call sys.exit(2)."""
        data = make_bash_input('git commit -m "feat: voice input"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        # WHY: run_git is called 3 times: rev-parse, diff --cached --name-only, diff --cached
        # Return feature branch and empty diffs — no branch warnings
        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/voice-input"
            return ""

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            # Should not raise SystemExit(2)
            pre_commit_guard.main()

        # Verify there was no blocking (no exit with code 2)
        # Test passes if main() completes without an exception

    def test_high_confidence_secret_file_blocks_commit(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Regression (HIGH, external security audit 2026-07-07, user-confirmed
        decision): a staged .env previously only generated a WARNING, never
        blocked the commit. High-confidence secret-file patterns (.env, .pem,
        id_rsa, ...) now hard-block via permissionDecision:deny -- a warning
        can be ignored, but once a secret reaches git history it requires a
        history rewrite to remove."""
        data = make_bash_input('git commit -m "feat: add config"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))
        monkeypatch.delenv("ALLOW_SECRET_COMMIT", raising=False)

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/test"
            if "--name-only" in args:
                return ".env"
            return ""  # diff --cached is empty

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            with pytest.raises(SystemExit) as exc:
                pre_commit_guard.main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert '"permissionDecision": "deny"' in captured.out
        assert ".env" in captured.out

    def test_secret_in_staged_content_of_innocuous_filename_blocks_commit(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """F-09 (external audit 2026-07-15): a real secret pasted into a
        file with an ordinary, non-suspicious name (config.py) previously
        went undetected entirely -- Check 2 only ever scanned staged FILE
        NAMES, never staged CONTENT. An AWS access key added to config.py
        must now hard-block the same as a staged .env file would."""
        data = make_bash_input('git commit -m "feat: add config"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))
        monkeypatch.delenv("ALLOW_SECRET_COMMIT", raising=False)

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/test"
            if "--name-only" in args:
                return "config.py"
            # plain `diff --cached` -- the actual staged content
            return "+AWS_KEY = 'AKIAABCDEFGHIJKLMNOP'\n"

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            with pytest.raises(SystemExit) as exc:
                pre_commit_guard.main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert '"permissionDecision": "deny"' in captured.out

    def test_medium_confidence_secret_file_still_warns_only(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """A generic "credentials"/"secret" filename (no high-confidence
        pattern) stays WARNING-only -- these have real false-positive risk
        (e.g. test_credentials.py) so they are not hard-blocked."""
        data = make_bash_input('git commit -m "feat: add config"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/test"
            if "--name-only" in args:
                return "credentials.json"
            return ""  # diff --cached is empty

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            pre_commit_guard.main()

        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert '"permissionDecision"' not in captured.out

    def test_env_example_is_not_flagged(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """.env.example is a recognized safe-lookalike convention -- must
        neither block nor warn."""
        data = make_bash_input('git commit -m "docs: add env example"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/test"
            if "--name-only" in args:
                return ".env.example"
            return ""

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            pre_commit_guard.main()

        assert capsys.readouterr().out == ""

    def test_key_substring_in_ordinary_filenames_not_flagged(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Regression (P1, reviewer-agent pass, 2026-07-07): the old
        unanchored ".key" substring match hard-blocked ordinary, non-secret
        filenames like keychain.py, config.keystore.py, and hot.keys.json.
        Anchoring to \\.key(\\.|$) (a real extension boundary, not a
        mid-word fragment) must let these through with no output at all."""
        data = make_bash_input('git commit -m "feat: add keychain helper"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/test"
            if "--name-only" in args:
                return "keychain.py\nconfig.keystore.py\nhot.keys.json\napp.keychain"
            return ""

        class _RuffOk:
            returncode = 0
            stdout = ""
            stderr = ""

        with (
            patch("pre_commit_guard.run_git", side_effect=mock_run_git),
            patch("subprocess.run", return_value=_RuffOk()),
        ):
            import pre_commit_guard

            pre_commit_guard.main()

        captured = capsys.readouterr()
        assert '"permissionDecision": "deny"' not in captured.out
        assert "sensitive" not in captured.out.lower()

    def test_key_as_true_extension_still_blocks(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """A file using .key as an actual extension-position component
        (e.g. api.key.ts) still gets hard-blocked -- the anchor narrows the
        false-positive surface without disabling detection of the real
        secret-file shape."""
        data = make_bash_input('git commit -m "feat: add api key"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/test"
            if "--name-only" in args:
                return "src/routing.key.ts"
            return ""

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            with pytest.raises(SystemExit):
                pre_commit_guard.main()

        assert '"permissionDecision": "deny"' in capsys.readouterr().out

    def test_explicit_override_allows_commit_and_logs(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """ALLOW_SECRET_COMMIT=1 + a reason bypasses the block, but the
        override itself is logged (stderr) and surfaced as a warning
        (stdout), not silent."""
        data = make_bash_input('git commit -m "test: add fixture"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))
        monkeypatch.setenv("ALLOW_SECRET_COMMIT", "1")
        monkeypatch.setenv("ALLOW_SECRET_COMMIT_REASON", "test fixture with fake key")

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/test"
            if "--name-only" in args:
                return "id_rsa"
            return ""

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            pre_commit_guard.main()

        captured = capsys.readouterr()
        assert '"permissionDecision": "deny"' not in captured.out
        assert "OVERRIDE" in captured.err
        assert "test fixture with fake key" in captured.err

    def test_override_without_reason_still_blocks(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """ALLOW_SECRET_COMMIT=1 alone, with no reason, does NOT bypass the
        block -- the override must be explicit AND explained."""
        data = make_bash_input('git commit -m "feat: x"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))
        monkeypatch.setenv("ALLOW_SECRET_COMMIT", "1")
        monkeypatch.delenv("ALLOW_SECRET_COMMIT_REASON", raising=False)

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/test"
            if "--name-only" in args:
                return "id_rsa"
            return ""

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            with pytest.raises(SystemExit):
                pre_commit_guard.main()

        assert '"permissionDecision": "deny"' in capsys.readouterr().out

    def test_detects_debug_statements(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """An added line with print() in diff should generate a warning."""
        data = make_bash_input('git commit -m "feat: logging"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/test"
            if "--name-only" in args:
                return "app.py"
            # diff --cached contains the added print()
            return "+    print(foo)\n+    result = compute()"

        # WHY: mock subprocess.run so ruff check (Check 4) doesn't try to open
        # a non-existent app.py from the test's mock staging area.
        class _RuffOk:
            returncode = 0
            stdout = ""
            stderr = ""

        with (
            patch("pre_commit_guard.run_git", side_effect=mock_run_git),
            patch("subprocess.run", return_value=_RuffOk()),
        ):
            import pre_commit_guard

            pre_commit_guard.main()

        captured = capsys.readouterr()
        assert "print(" in captured.out or "Debug" in captured.out or "debug" in captured.out

    def test_ignores_removed_debug(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Removed lines with print() (starting with '-') should not trigger a warning."""
        data = make_bash_input('git commit -m "refactor: clean up"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/clean"
            if "--name-only" in args:
                return "app.py"
            # WHY: line starts with '-' — it is a removed line, hook ignores it
            return "-    print(foo)\n+    logger.debug('foo')"

        class _RuffOk:
            returncode = 0
            stdout = ""
            stderr = ""

        with (
            patch("pre_commit_guard.run_git", side_effect=mock_run_git),
            patch("subprocess.run", return_value=_RuffOk()),
        ):
            import pre_commit_guard

            pre_commit_guard.main()

        captured = capsys.readouterr()
        # The debug-statements warning should NOT contain "print("
        # (logger.debug is not in debug_patterns)
        output_data = json.loads(captured.out) if captured.out.strip() else {}
        context = output_data.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "print(" not in context

    def test_ruff_errors_block_commit(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """ruff lint errors in staged .py files → permissionDecision:deny (Check 4)."""
        data = make_bash_input('git commit -m "feat: new feature"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/test"
            if "--name-only" in args:
                return "app.py"
            return ""

        class _RuffFail:
            returncode = 1
            stdout = "app.py:1:1: F821 Undefined name `foo`\nFound 1 error."
            stderr = ""

        with (
            patch("pre_commit_guard.run_git", side_effect=mock_run_git),
            patch("subprocess.run", return_value=_RuffFail()),
        ):
            import pre_commit_guard

            with pytest.raises(SystemExit) as exc_info:
                pre_commit_guard.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert '"permissionDecision": "deny"' in captured.out
        assert "ruff" in captured.out.lower()

    def test_ruff_pass_allows_commit(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """ruff clean staged files → commit proceeds normally (Check 4 passes)."""
        data = make_bash_input('git commit -m "feat: new feature"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/test"
            if "--name-only" in args:
                return "app.py"
            return ""

        class _RuffOk:
            returncode = 0
            stdout = ""
            stderr = ""

        with (
            patch("pre_commit_guard.run_git", side_effect=mock_run_git),
            patch("subprocess.run", return_value=_RuffOk()),
        ):
            import pre_commit_guard

            pre_commit_guard.main()  # Should NOT raise SystemExit

        captured = capsys.readouterr()
        # No deny decision — commit allowed through
        assert '"permissionDecision": "deny"' not in captured.out

    def test_all_checks_after_branch_use_extracted_cwd(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression (MEDIUM, hooks-02 audit): only the branch check (Check 1)
        passed cmd_cwd through -- Check 2 (sensitive files), Check 3 (debug
        diff), and Check 4 (ruff's staged-file list + repo-root lookup) all
        still ran against the hook's OWN cwd. A `cd <other-repo> && git commit`
        correctly checked the right branch but silently checked the WRONG
        repo for everything else."""
        data = make_bash_input('cd "/target/repo" && git commit -m "feat: x"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        captured_calls: list[tuple[list, dict]] = []

        def mock_run_git(args: list, **kwargs) -> str:
            captured_calls.append((args, kwargs))
            if "rev-parse" in args and "--abbrev-ref" in args:
                return "feature/ok"
            if "--show-toplevel" in args:
                return "/target/repo"
            if "--name-only" in args:
                return ""  # no staged files -> skip Check 4's ruff subprocess entirely
            return ""

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            pre_commit_guard.main()

        # every run_git call this session made must have used the SAME
        # target-repo cwd, not a mix of "/target/repo" and None/hook-cwd
        cwds = {kwargs.get("cwd") for _args, kwargs in captured_calls}
        assert cwds == {"/target/repo"}

    def test_ruff_timeout_emits_visible_warning_not_silent_skip(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Regression (MEDIUM, hooks-02 audit): a missing/hung ruff previously
        exited 0 with ZERO output -- the "enforcement, not reminder" lint gate
        silently didn't run, with no signal to the user or Claude that it
        hadn't. Must still fail-open (never block), but must say so."""
        data = make_bash_input('git commit -m "feat: x"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/test"
            if "--name-only" in args:
                return "app.py"
            return ""

        import subprocess

        def raise_timeout(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd="ruff", timeout=30)

        with (
            patch("pre_commit_guard.run_git", side_effect=mock_run_git),
            patch("subprocess.run", side_effect=raise_timeout),
        ):
            import pre_commit_guard

            with pytest.raises(SystemExit) as exc_info:
                pre_commit_guard.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.out != ""
        assert "ruff" in captured.out.lower()
        assert "skip" in captured.out.lower()

    def test_blocks_push_to_public_main(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """git push public main → permissionDecision:deny + exit(0) (SDK protocol)."""
        data = make_bash_input("git push public main")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import pre_commit_guard

        with pytest.raises(SystemExit) as exc_info:
            pre_commit_guard.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert '"permissionDecision": "deny"' in captured.out
        assert "public" in captured.out

    def test_allows_push_feature_to_public(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """git push public feature/x is allowed — only main/master are blocked."""
        data = make_bash_input("git push public feature/voice-input")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import pre_commit_guard

        # Should not raise SystemExit(2)
        pre_commit_guard.main()

        captured = capsys.readouterr()
        assert captured.err == ""


class TestReadmeTestCountFreshness:
    """Check 5: a plain reminder (not a count comparison) when a commit
    touches tests/ or skills/, pointing at scripts/sync_readme_from_ci.py.

    WHY not a local-vs-badge count comparison (reviewer P1, caught before
    merge -- the first version of this check did exactly that): local
    `pytest --collect-only` counts MORE tests than CI (env-dependent tests
    -- see scripts/sync_readme_from_ci.py's own docstring). Measured
    directly: local --collect-only reported 2034 against a README badge of
    2009 that CI had JUST correctly synced -- a 25-test gap with zero real
    staleness. A check comparing those two numbers would warn on nearly
    every relevant commit regardless of whether anything was actually
    wrong, reproducing the exact "cried wolf" pattern this whole exercise
    was meant to fix. Only CI can answer "is the badge correct"; this
    check just surfaces the reminder at commit time instead of only
    reactively when CI complains."""

    def test_staged_files_touch_doc_count_inputs(self):
        import pre_commit_guard

        assert pre_commit_guard._staged_files_touch_doc_count_inputs(
            ["tests/test_foo.py", "README.md"]
        )
        assert pre_commit_guard._staged_files_touch_doc_count_inputs(
            ["skills/extensions/foo/SKILL.md"]
        )
        assert not pre_commit_guard._staged_files_touch_doc_count_inputs(
            ["hooks/foo.py", "README.md"]
        )

    def test_main_warns_when_tests_staged(self, monkeypatch, capsys):
        """Staging a tests/ file must produce a WARNING pointing at the
        sync script -- no pytest subprocess call, no count comparison."""
        data = make_bash_input('git commit -m "test: add new test case"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args, **kwargs):
            if "--abbrev-ref" in args:
                return "feature/add-test"
            if "--name-only" in args:
                return "tests/test_new_thing.py"
            return ""

        # WHY mock subprocess.run too: the staged file ends in .py, so
        # Check 4 (ruff) also runs -- a real ruff invocation would 404 on
        # this nonexistent test fixture path (E902) and deny before Check 5
        # ever runs.
        class _RuffOk:
            returncode = 0
            stdout = ""
            stderr = ""

        with (
            patch("pre_commit_guard.run_git", side_effect=mock_run_git),
            patch("subprocess.run", return_value=_RuffOk()),
        ):
            import pre_commit_guard

            pre_commit_guard.main()

        captured = capsys.readouterr()
        assert "sync_readme_from_ci.py" in captured.out
        assert "tests/ or skills/" in captured.out

    def test_main_warns_when_skills_staged(self, monkeypatch, capsys):
        data = make_bash_input('git commit -m "feat(skills): add new skill"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args, **kwargs):
            if "--abbrev-ref" in args:
                return "feature/new-skill"
            if "--name-only" in args:
                return "skills/extensions/foo/SKILL.md"
            return ""

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            pre_commit_guard.main()

        captured = capsys.readouterr()
        assert "sync_readme_from_ci.py" in captured.out

    def test_main_skips_check_when_no_test_or_skill_files_staged(self, monkeypatch, capsys):
        """A commit touching only hooks/ must never trigger this check, and
        must never invoke a pytest subprocess (Check 5 doesn't run pytest at
        all in this design, but confirm no unexpected subprocess call either)."""
        data = make_bash_input('git commit -m "fix: unrelated hook change"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args, **kwargs):
            if "--abbrev-ref" in args:
                return "feature/hook-fix"
            if "--name-only" in args:
                return "hooks/some_hook.py"
            if "--diff-filter=ACM" in args:
                return "hooks/some_hook.py"
            return ""

        class _RuffOk:
            returncode = 0
            stdout = ""
            stderr = ""

        with (
            patch("pre_commit_guard.run_git", side_effect=mock_run_git),
            patch("subprocess.run", return_value=_RuffOk()),
        ):
            import pre_commit_guard

            pre_commit_guard.main()

        captured = capsys.readouterr()
        assert "sync_readme_from_ci.py" not in captured.out
