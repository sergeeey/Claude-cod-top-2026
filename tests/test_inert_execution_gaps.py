"""Gaps in the inert-text exemption, found by Codex review of PR #523.

- sed and awk execute code (`sed 'e CMD'`, `awk ... system(...)`), so they must not be
  treated as inert text; the dangerous text inside them must still be denied.
- A redirection into a block device is destructive even when the program only copies text.
- Commits inside a subshell or command substitution must still be recognised, so the commit
  hooks do not silently skip their work.

Dangerous text is built at runtime so this file itself stays inert.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

import permission_policy as pp  # noqa: E402
from lib.git_commands import has_git_subcommand  # noqa: E402

RM_RF = "rm " + "-rf"


@pytest.mark.parametrize(
    "command",
    [
        f"sed 'e {RM_RF} /tmp/victim' input.txt",
        f"awk 'BEGIN {{system(\"{RM_RF} /tmp/victim\")}}'",
        "cat disk.img > /dev/sdb",
    ],
)
def test_execution_capable_text_processors_and_block_writes_are_denied(command):
    decision, _ = pp.decide("Bash", {"command": command})
    assert decision == "deny", command


@pytest.mark.parametrize(
    "command",
    [
        "(git commit -m fix)",
        "HASH=$(git commit -m fix)",
        "git -C ../repo commit -m fix && (git commit -m again)",
    ],
)
def test_commit_inside_subshell_or_substitution_is_recognised(command):
    assert has_git_subcommand(command, "commit"), command


@pytest.mark.parametrize("command", ['echo "git commit later"', "git status"])
def test_plain_text_without_execution_context_is_not_a_commit(command):
    assert not has_git_subcommand(command, "commit"), command
