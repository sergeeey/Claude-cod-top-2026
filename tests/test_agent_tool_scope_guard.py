"""Unit tests for hooks/agent_tool_scope_guard.py.

WHY: this hook is the enforcement backstop for the memory:-field auto Write/Edit
grant (see hooks/agent_tool_scope_guard.py's own docstring) -- a bug here silently
lets a memory-bearing agent self-implement again, the exact class of failure this
hook exists to close.
"""

import io
import json

from agent_tool_scope_guard import _bash_looks_like_write, _find_declared_tools, main


class TestFindDeclaredTools:
    def test_boyko_agent_excludes_edit_write(self):
        declared = _find_declared_tools("boyko-agent")
        assert declared is not None
        assert "Edit" not in declared
        assert "Write" not in declared
        assert "Read" in declared

    def test_builder_includes_edit_write(self):
        declared = _find_declared_tools("builder")
        assert declared is not None
        assert "Edit" in declared
        assert "Write" in declared

    def test_reviewer_excludes_edit_write(self):
        declared = _find_declared_tools("reviewer")
        assert declared is not None
        assert "Edit" not in declared
        assert "Write" not in declared

    def test_unknown_agent_returns_none(self):
        assert _find_declared_tools("totally-unknown-agent-xyz") is None

    def test_agent_paren_syntax_not_counted_as_a_tool(self):
        # boyko-agent's tools: line includes "Agent(explorer, verifier, ...)" --
        # none of those sub-agent names must leak into the declared tool set.
        declared = _find_declared_tools("boyko-agent")
        assert "explorer" not in declared
        assert "verifier" not in declared


class TestBashLooksLikeWrite:
    """Direct tests for the pattern detector, isolated from agent-scope logic --
    catches a regex/substring regression without needing a full main() call."""

    def test_redirect_variants(self):
        assert _bash_looks_like_write("echo hi > file.txt")
        assert _bash_looks_like_write("echo hi >> file.txt")
        assert _bash_looks_like_write("cmd 1> out.log")
        assert _bash_looks_like_write("cmd 2> err.log")

    def test_tee_cp_mv_sed(self):
        assert _bash_looks_like_write("git log | tee out.txt")
        assert _bash_looks_like_write("cp a.txt b.txt")
        assert _bash_looks_like_write("mv a.txt b.txt")
        assert _bash_looks_like_write("sed -i 's/x/y/' file.txt")

    def test_plain_read_only_commands_do_not_match(self):
        # Negative control -- the whole point of the conditional gate is that
        # ordinary read-only Bash (exactly what boyko-agent needs for its real
        # job) must never trip this.
        assert not _bash_looks_like_write("git log --oneline -5")
        assert not _bash_looks_like_write("git status --short")
        assert not _bash_looks_like_write("gh pr checks 251")
        assert not _bash_looks_like_write("grep -rn pattern file.py")
        assert not _bash_looks_like_write("ls -la")
        assert not _bash_looks_like_write("git diff --stat")

    def test_quote_split_tee_cp_mv_sed_still_match(self):
        # Regression (falsification-pilot 20260824, follow-up sweep): bash
        # concatenates adjacent quoted/unquoted fragments into one word, so
        # these execute identically to their unquoted forms in
        # test_tee_cp_mv_sed above -- but the raw substring scan missed all
        # four, which meant main() would allow the write with NO scope check
        # at all (structurally the same full-bypass shape as the
        # permission_policy.py sensitive-path finding this fix is modeled
        # on). Independently reproduced before this fix.
        assert _bash_looks_like_write("t'e'e /tmp/x.txt")
        assert _bash_looks_like_write("c'p' secret.txt /tmp/leak.txt")
        assert _bash_looks_like_write("m'v' a.txt b.txt")
        assert _bash_looks_like_write("sed -'i' 's/a/b/' file.py")

    def test_curl_wget_rsync_perl_now_match(self):
        """Regression for bottleneck #3 (/boyko-project-radar autonomy-
        subsystem scan, 2026-08-29, independently confirmed by two scanners):
        these four were a full bypass of this hook's scope check before the
        pattern expansion -- an agent without Write/Edit could exfiltrate or
        overwrite a file with any of them and this function returned False,
        same full-bypass shape as the tee/cp/mv/sed quote-split gap above.
        (dd is covered separately in TestDdWritesFile below -- it needs a
        structural check, not a substring, see that class's docstring.)"""
        assert _bash_looks_like_write("curl -o /tmp/out.txt https://example.com")
        assert _bash_looks_like_write("curl --output out.txt https://example.com")
        assert _bash_looks_like_write("wget -O /tmp/out.txt https://example.com")
        assert _bash_looks_like_write("wget --output-document out.txt https://example.com")
        assert _bash_looks_like_write("rsync -a src/ dest/")
        assert _bash_looks_like_write("perl -i -pe 's/x/y/' file.py")

    def test_package_manager_install_is_not_a_false_positive(self):
        """Negative control for the SPECIFIC risk the new patterns had to
        avoid: `install` was deliberately NOT added as a bare pattern
        because it collides with pip/npm/apt's `install` subcommand, which
        is not a file-scope write this hook is meant to gate. If this ever
        starts failing, someone added a bare "install" substring back in --
        that would false-positive-block every agent's dependency install."""
        assert not _bash_looks_like_write("pip install requests")
        assert not _bash_looks_like_write("npm install --save-dev jest")
        assert not _bash_looks_like_write("apt install -y curl")


class TestDdWritesFile:
    """dd needed a structural check, not a substring, because dd's write
    flag (`of=`) collides with any other command that merely has a token
    starting with "of=". Caught in independent review, 2026-08-29: this
    file's FIRST dd fix used a bare "dd of=" substring (missed `dd if=x
    of=y`, the more common flag ordering -- dd's flags are unordered); the
    SECOND fix used a leading-space " of=" token-boundary match (fixed the
    ordering bug, but then false-positived on `echo 'of=value'`, since it
    never confirmed the command's actual executable is dd at all). This
    third version splits into statements (pipe/chain-aware, same splitter
    the rest of this file's checks use) and requires the statement's own
    first token to actually BE dd (bare or path-qualified) before treating
    an `of=` argument in that same statement as a write."""

    def test_dd_write_detected_of_after_if(self):
        assert _bash_looks_like_write("dd if=input.img of=output.img")

    def test_dd_write_detected_of_before_if(self):
        """dd's flags are unordered -- of= first must match just as well as
        if= first. This exact ordering was the bug in the first fix."""
        assert _bash_looks_like_write("dd of=output.img if=input.img")

    def test_dd_read_only_no_of_flag_allowed(self):
        assert not _bash_looks_like_write("dd if=input.img status=progress")

    def test_dd_read_only_piped_allowed(self):
        assert not _bash_looks_like_write("dd if=/dev/sda bs=1M count=1 | md5sum")

    def test_curl_url_containing_of_equals_allowed(self):
        """The exact false-positive the leading-space " of=" version
        introduced: a URL query string containing "of=" is not a dd
        invocation and must not match."""
        assert not _bash_looks_like_write("curl 'https://host/?of=value'")

    def test_echo_of_equals_allowed(self):
        """The second exact false-positive independently caught in review:
        `echo 'of=value'` has a token starting with "of=" but the command
        is echo, not dd -- must not match."""
        assert not _bash_looks_like_write("echo 'of=value'")

    def test_unrelated_proof_flag_allowed(self):
        """A flag that merely CONTAINS "of=" as a substring (--pro-of=) but
        isn't dd's own of= flag at all -- must not match regardless."""
        assert not _bash_looks_like_write("python tool.py --proof=value")

    def test_dd_piped_from_another_command_still_detected(self):
        """dd as the SECOND command in a pipe (not the first token of the
        whole line) must still be recognized -- split_shell_statements
        splits on | too, so dd's own statement starts fresh at "dd"."""
        assert _bash_looks_like_write("cat input.img | dd of=/dev/sdb")

    def test_quote_split_does_not_break_ordinary_quoted_commands(self):
        # WHY: the dequote-before-scan fix must not become a new source of
        # false positives on everyday quoted commands with no write pattern.
        assert not _bash_looks_like_write("git commit -m 'fix: something'")
        assert not _bash_looks_like_write("echo 'hello world'")


class TestMain:
    def _call_main(self, monkeypatch, data: dict) -> dict:
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
        from io import StringIO

        buf = StringIO()
        monkeypatch.setattr("sys.stdout", buf)
        main()
        return json.loads(buf.getvalue())

    def test_boyko_agent_edit_denied(self, monkeypatch):
        result = self._call_main(
            monkeypatch, {"agent_type": "boyko-agent", "tool_name": "Edit", "tool_input": {}}
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "boyko-agent" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_boyko_agent_write_denied(self, monkeypatch):
        result = self._call_main(
            monkeypatch, {"agent_type": "boyko-agent", "tool_name": "Write", "tool_input": {}}
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_builder_edit_allowed(self, monkeypatch):
        result = self._call_main(
            monkeypatch, {"agent_type": "builder", "tool_name": "Edit", "tool_input": {}}
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_no_agent_type_allowed(self, monkeypatch):
        # Main session, not a subagent -- must never be gated.
        result = self._call_main(monkeypatch, {"tool_name": "Edit", "tool_input": {}})
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_bash_with_no_command_allowed(self, monkeypatch):
        # Empty tool_input (no command field) must not crash or false-positive.
        result = self._call_main(
            monkeypatch, {"agent_type": "boyko-agent", "tool_name": "Bash", "tool_input": {}}
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_bash_readonly_command_allowed_for_readonly_agent(self, monkeypatch):
        # THE critical negative control: boyko-agent's real, legitimate use of
        # Bash (git/gh checks) must still pass through untouched.
        result = self._call_main(
            monkeypatch,
            {
                "agent_type": "boyko-agent",
                "tool_name": "Bash",
                "tool_input": {"command": "git log --oneline -20"},
            },
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_bash_redirect_denied_for_readonly_agent(self, monkeypatch):
        # The gap this whole change closes: echo/redirect from an agent with no
        # declared Write/Edit must now be denied, not silently pass through.
        result = self._call_main(
            monkeypatch,
            {
                "agent_type": "boyko-agent",
                "tool_name": "Bash",
                "tool_input": {"command": "echo findings > report.md"},
            },
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "Write/Edit" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_bash_tee_denied_for_readonly_agent(self, monkeypatch):
        result = self._call_main(
            monkeypatch,
            {
                "agent_type": "reviewer",
                "tool_name": "Bash",
                "tool_input": {"command": "git log | tee /tmp/out.txt"},
            },
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_bash_write_pattern_allowed_for_agent_with_write(self, monkeypatch):
        # An agent that DOES declare Write/Edit (e.g. builder) must not be
        # blocked from Bash-based file writes -- the gate is about Write/Edit
        # capability, not about banning redirects universally.
        result = self._call_main(
            monkeypatch,
            {
                "agent_type": "builder",
                "tool_name": "Bash",
                "tool_input": {"command": "echo done > status.txt"},
            },
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_unknown_agent_fails_open(self, monkeypatch):
        result = self._call_main(
            monkeypatch,
            {"agent_type": "totally-unknown-agent-xyz", "tool_name": "Edit", "tool_input": {}},
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_reviewer_edit_denied(self, monkeypatch):
        result = self._call_main(
            monkeypatch, {"agent_type": "reviewer", "tool_name": "Edit", "tool_input": {}}
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_empty_stdin_no_crash(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
        main()  # must not raise
