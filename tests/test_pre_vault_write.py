"""Tests for pre_vault_write.py — vault write validation (PR #138 fix: Path.home()).

WHY: PR #138 replaced hardcoded 'C:/Users/serge' with Path.home().
Tests verify the hook works for any user, not just the original developer.
"""

from pathlib import Path
from unittest.mock import patch


def _vault_path(home: Path, *parts: str) -> str:
    """Build an absolute path inside the fake vault."""
    p = home / ".claude" / "memory"
    for part in parts:
        p = p / part
    return str(p)


class TestValidateVaultWrite:
    def test_path_home_not_hardcoded(self, tmp_path):
        """PR #138: vault_root uses Path.home() — any username works, not just 'serge'."""
        import pre_vault_write

        fake_home = tmp_path / "anyuser"
        fake_home.mkdir()
        target = _vault_path(fake_home, "projects", "test.md")
        content = "# Test\n\n## Path: D:/Test/\n\nContent."

        with patch.object(Path, "home", return_value=fake_home):
            result = pre_vault_write.validate_vault_write(target, content)

        # Reaches vault validation and passes (has ## Path:)
        assert result.get("allowed", True) is True

    def test_outside_vault_always_allowed(self, tmp_path):
        """File outside the vault skips all validation."""
        import pre_vault_write

        result = pre_vault_write.validate_vault_write(str(tmp_path / "not_in_vault.md"), "anything")
        assert result.get("allowed", True) is True

    def test_personal_project_in_repo_intel_blocked(self, tmp_path):
        """repo-intel entry referencing personal GitHub URL is blocked."""
        import pre_vault_write

        target = _vault_path(tmp_path, "repo-intel", "my-repo.md")
        content = "# My Repo\ngithub.com/sergeeey/my-repo\nsome content"

        with patch.object(Path, "home", return_value=tmp_path):
            result = pre_vault_write.validate_vault_write(target, content)

        assert result["allowed"] is False
        assert "repo-intel" in result.get("reason", "").lower()

    def test_project_missing_path_field_blocked(self, tmp_path):
        """Project .md without ## Path: field is blocked."""
        import pre_vault_write

        target = _vault_path(tmp_path, "projects", "my-project.md")
        content = "# My Project\n\nNo path field here."

        with patch.object(Path, "home", return_value=tmp_path):
            result = pre_vault_write.validate_vault_write(target, content)

        assert result["allowed"] is False

    def test_project_with_path_field_allowed(self, tmp_path):
        """Project .md with ## Path: field passes validation."""
        import pre_vault_write

        target = _vault_path(tmp_path, "projects", "my-project.md")
        content = "# My Project\n\n## Path: D:/my-project/\n\nDescription."

        with patch.object(Path, "home", return_value=tmp_path):
            result = pre_vault_write.validate_vault_write(target, content)

        assert result.get("allowed", True) is True

    def test_auto_folder_write_blocked(self, tmp_path):
        """Writes to _auto/ are blocked — auto-generated content is read-only."""
        import pre_vault_write

        target = _vault_path(tmp_path, "_auto", "patterns.md")
        content = "# Patterns"

        with patch.object(Path, "home", return_value=tmp_path):
            result = pre_vault_write.validate_vault_write(target, content)

        assert result["allowed"] is False
        assert "_auto" in result.get("reason", "")

    def test_auto_folder_traversal_bypass_now_blocked(self, tmp_path):
        """Regression (HIGH, cross-model audit): a path like
        ".../projects/../_auto/foo.md" kept its literal ".." segment through
        relative_to(), so rel_path never started with "_auto/" and the
        read-only guard was silently bypassed -- even though the OS resolves
        the ".." and actually writes into _auto/ when the tool really runs.
        Resolving both sides before relative_to() closes this."""
        import pre_vault_write

        target = _vault_path(tmp_path, "projects", "..", "_auto", "sneaky.md")
        content = "# Sneaky"

        with patch.object(Path, "home", return_value=tmp_path):
            result = pre_vault_write.validate_vault_write(target, content)

        assert result["allowed"] is False
        assert "_auto" in result.get("reason", "")

    def test_repo_intel_traversal_bypass_now_blocked(self, tmp_path):
        """Same traversal class applied to the repo-intel check (Check 1),
        not just _auto/ (Check 4) -- both rely on the same normalized
        rel_path_str now."""
        import pre_vault_write

        target = _vault_path(tmp_path, "projects", "..", "repo-intel", "my-repo.md")
        content = "# My Repo\ngithub.com/sergeeey/my-repo\nsome content"

        with patch.object(Path, "home", return_value=tmp_path):
            result = pre_vault_write.validate_vault_write(target, content)

        assert result["allowed"] is False
        assert "repo-intel" in result.get("reason", "").lower()
