"""Tests for hooks/lib/git_commands.py -- real git invocations vs text that mentions them.

WHY: three hooks used a substring test ("git push --force" in cmd) and fired on
grep patterns, heredoc notes, `git merge-base`, and on the protected
`--force-with-lease=<ref>:<sha>` form. These cases pin the replacement.
"""

import pytest
from lib.git_commands import (
    force_push_in,
    force_push_reason,
    git_invocations,
    has_git_subcommand,
    invocations,
    is_inert_text_command,
    neutralize_explicit_leases,
    runs_unparsed_shell,
)

SHA = "a" * 40
LEASE = f"refs/heads/b:{SHA}"


class TestForcePushDenied:
    @pytest.mark.parametrize(
        "command",
        [
            "git push --force",
            "git push -f origin x",
            "git push -uf origin x",
            "git push origin +main",
            "git push origin HEAD:+main",
            "git push --force-with-lease origin x",
            "git push --force-with-lease=main origin x",
            "git push --force-with-lease=main: origin x",
            "git push origin x --force",
            "cd repo && git push --force",
            "FOO=1 git push -f",
            "sudo git push --force",
            "env -i X=1 git push -f",
            "git -C some/dir push --force",
            'bash -c "git push --force"',
            "sh -c 'git push -f origin x'",
            'ssh host "git push --force origin x"',
            'powershell -Command "git push --force"',
        ],
    )
    def test_denied(self, command):
        assert force_push_in(command, allow_explicit_lease=True), command


class TestForcePushAllowed:
    @pytest.mark.parametrize(
        "command",
        [
            "git push origin main",
            "git push -u origin feature/x",
            f"git push --force-with-lease={LEASE} origin x",
            f"git -C D:/x push --force-with-lease={LEASE} github c:refs/heads/b",
            'grep -n "git push --force" file.py',
            'echo "the hook blocks git push --force here"',
            'git commit -m "docs: mention git push --force"',
            "cat >> note.md <<'EOF'\nthe hook blocks git push --force here\nEOF",
            "git merge-base main feature",
            "git log --grep='git push -f'",
        ],
    )
    def test_not_a_force_push(self, command):
        assert force_push_in(command, allow_explicit_lease=True) is None, command

    def test_explicit_lease_still_counts_for_checkpoint_guard(self):
        # checkpoint_guard asks the stricter question: does this overwrite history at all?
        assert force_push_in(f"git push --force-with-lease={LEASE} origin x") is not None

    def test_short_lease_value_rejected(self):
        # a 3-char "sha" is not an expected value worth trusting
        assert force_push_reason(["--force-with-lease=main:abc"], allow_explicit_lease=True)


class TestInvocations:
    def test_quoted_text_is_not_a_command(self):
        assert git_invocations('echo "git commit -m x"') == []

    def test_heredoc_body_is_not_a_command(self):
        assert git_invocations("cat <<EOF\ngit merge main\nEOF") == []

    def test_subcommand_after_global_options(self):
        assert git_invocations("git -C x -c a=b --no-pager log -1") == [("log", ["-1"])]

    def test_merge_base_is_not_merge(self):
        assert not has_git_subcommand("git merge-base a b", "merge")
        assert has_git_subcommand("git merge main", "merge")

    def test_wrapped_rm_is_found(self):
        assert ("rm", ["-rf", "x"]) in invocations("sudo rm -rf x")

    def test_chain_gives_each_statement(self):
        subs = [s for s, _ in git_invocations("git add f && git commit -m m; git push")]
        assert subs == ["add", "commit", "push"]


class TestInertText:
    @pytest.mark.parametrize(
        "command",
        [
            'grep -n "git push --force" notes.md',
            'echo "never run git push --force"',
            'git commit -m "docs: git push --force"',
            "cat >> n.md <<'EOF'\ngit push --force\nEOF",
            'cd x && echo "git push -f"',
        ],
    )
    def test_inert(self, command):
        assert is_inert_text_command(command), command

    @pytest.mark.parametrize(
        "command",
        [
            "echo $(git push --force)",
            "echo `git push --force`",
            "( git push --force )",
            "{ git push --force; }",
            'echo "git push --force" | bash',
            "python -I run.py",
            "git push origin main",
            "xargs git push --force",
        ],
    )
    def test_not_inert(self, command):
        assert not is_inert_text_command(command), command

    def test_explicit_lease_is_neutralised_for_text_scans(self):
        text = f"git push --force-with-lease={LEASE} origin x"
        assert "--force" not in neutralize_explicit_leases(text)
        # a bare lease or a lease with a short value is left alone
        assert "--force-with-lease" in neutralize_explicit_leases(
            "git push --force-with-lease origin"
        )
        assert "--force-with-lease=main:abc" in neutralize_explicit_leases(
            "git push --force-with-lease=main:abc"
        )


class TestUnparsedShell:
    def test_piped_into_bash(self):
        assert runs_unparsed_shell('echo "git push --force" | bash')

    def test_inline_code_flag_is_parsed_not_flagged(self):
        assert not runs_unparsed_shell('bash -c "ls"')

    def test_plain_git(self):
        assert not runs_unparsed_shell("git status")
