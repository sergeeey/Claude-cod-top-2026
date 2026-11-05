"""`git -C <dir> commit` and `git -c key=val commit` must count as commits in the five
commit-detection hooks; prose that merely mentions them must not.

WHY (2026-11-01, audit): the old check was `"git commit" in command`, which misses both
global-option forms. Each hook now asks lib.git_commands.has_git_subcommand(). This file
checks that predicate on the forms, checks that each hook really uses it, and exercises
gitnexus_reindex.should_reindex, the one pure gate among the five.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
HOOKS = ROOT / "hooks"
sys.path.insert(0, str(HOOKS))

from gitnexus_reindex import should_reindex  # noqa: E402
from lib.git_commands import has_git_subcommand  # noqa: E402

COMMIT_FORMS = [
    "git commit -m fix",
    "git -C ../repo commit -m fix",
    "git -c user.name=x commit -m fix",
    "git -c user.name=x -C ../repo commit -m fix",
    "git -C ../repo -c user.email=a@b commit -m fix",
    "env GIT_AUTHOR_DATE=x git -C ../repo commit -m fix",
    "cd ../repo && git -c core.hooksPath=/dev/null commit -m fix",
]
NOT_COMMIT_FORMS = [
    'echo "reminder: git -C ../repo commit later"',
    'grep "git -c user.name=x commit" notes.md',
    "git -C ../repo status",
    "git -c core.x=1 log --oneline -3",
    "git -C ../repo merge-base main HEAD",
]
HOOK_FILES = ["auto_capture.py", "memory_guard.py", "pattern_extractor.py", "post_commit_memory.py"]


@pytest.mark.parametrize("command", COMMIT_FORMS)
def test_global_option_commit_forms_are_commits(command):
    assert has_git_subcommand(command, "commit"), command


@pytest.mark.parametrize("command", NOT_COMMIT_FORMS)
def test_text_and_other_subcommands_are_not_commits(command):
    assert not has_git_subcommand(command, "commit"), command


@pytest.mark.parametrize("command", COMMIT_FORMS)
def test_gitnexus_reindex_triggers_on_global_option_commits(command):
    assert should_reindex(command, "") is True, command


@pytest.mark.parametrize("command", NOT_COMMIT_FORMS)
def test_gitnexus_reindex_ignores_text_and_other_subcommands(command):
    assert should_reindex(command, "") is False, command


@pytest.mark.parametrize("name", HOOK_FILES + ["gitnexus_reindex.py"])
def test_each_hook_uses_the_structural_commit_check(name):
    source = (HOOKS / name).read_text(encoding="utf-8")
    assert "has_git_subcommand(" in source, name
    assert '"git commit" not in command' not in source, name
