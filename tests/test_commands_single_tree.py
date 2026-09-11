"""One command tree, and the installer reads it.

WHY this file exists (2026-09-11): `commands/` and `.claude/commands/` both
existed with DIFFERENT content for the same command names, and `install.sh` read
the smaller, frozen one. Consequences measured on a real install before the fix:

  - evolve-solution shipped at 2005 B instead of 6398 B
  - revive-project shipped at 3421 B instead of 11188 B
  - release-scout.md was never installed by any path, because it existed only
    in the tree the installer did not read

Nothing caught it. `commands/` is uncounted by sync_doc_counts and invisible to
live_drift_guard, whose only occurrence of the word "commands" is a comment
about shell commands. The discrepancy was found by listing both trees by hand.

These two tests close the class rather than the instance: the first fails if a
second tree reappears under any name, the second fails if the installer is ever
repointed at a non-canonical source.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent
CANONICAL = ROOT / "commands"


class TestSingleCommandTree:
    def test_no_second_tree_shadows_a_canonical_command(self):
        """No command name may exist in two trees at once.

        Deliberately checks for NAME COLLISION rather than for the absence of a
        specific directory. A rule phrased as ".claude/commands must not exist"
        would pass the moment someone created .claude/slash/ or commands2/ --
        the defect is two homes for one command, not one particular path.
        """
        canonical = {p.name for p in CANONICAL.glob("*.md")}
        assert canonical, "commands/ is empty — the canonical tree disappeared"

        collisions = []
        for other in ROOT.rglob("commands/*.md"):
            if other.parent.resolve() == CANONICAL.resolve():
                continue
            if any(part in {".git", "node_modules", ".venv"} for part in other.parts):
                continue
            if other.name in canonical:
                collisions.append(str(other.relative_to(ROOT)))

        assert not collisions, (
            "these files duplicate a command that already lives in commands/: "
            f"{collisions}. Two trees for one command is how evolve-solution "
            "shipped at 2005 B instead of 6398 B."
        )

    def test_installer_reads_the_canonical_tree(self):
        """install.sh must copy from commands/, not from a sibling tree.

        Pinned as source text rather than by running the installer: the failure
        being guarded is a one-word path change, and a smoke install would pass
        either way as long as SOME directory was copied.
        """
        install_sh = (ROOT / "install.sh").read_text(encoding="utf-8")
        assert 'local src="$SCRIPT_DIR/commands"' in install_sh, (
            "install_commands() no longer sources $SCRIPT_DIR/commands — "
            "check whether it was repointed at a stale duplicate tree"
        )
        assert 'local src="$SCRIPT_DIR/.claude/commands"' not in install_sh, (
            "install.sh is reading .claude/commands again — that tree was the "
            "frozen 2026-06-30 copy and shipping it is the original bug"
        )

    def test_release_scout_is_in_the_installed_tree(self):
        """The file that was never installed, pinned by name.

        Kept as a separate named case on purpose: the two tests above would both
        pass in a world where release-scout.md had simply been deleted to make
        the trees agree. That would "fix" the collision by losing the command.
        """
        assert (CANONICAL / "release-scout.md").is_file(), (
            "release-scout.md is missing from commands/ — it was the command "
            "that no install path delivered, and removing it is not the fix"
        )
