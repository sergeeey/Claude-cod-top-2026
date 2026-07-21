"""Tests for pre_vault_write.py — vault write validation (PR #138 fix: Path.home()).

WHY: PR #138 replaced hardcoded 'C:/Users/serge' with Path.home().
Tests verify the hook works for any user, not just the original developer.
"""

import io
import json
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

    def test_substring_special_file_false_positive_now_fixed(self, tmp_path):
        """Regression (external review, 2026-07-21): a path merely CONTAINING the
        substring "_auto" (inside "not_auto_but_contains_auto") used to skip the
        ## Path: requirement entirely -- `"_auto" in file_path` matched it even
        though the file isn't actually in a special directory. Path-component
        matching must NOT treat this as special."""
        import pre_vault_write

        target = _vault_path(tmp_path, "projects", "not_auto_but_contains_auto", "x.md")
        content = "# X\n\nNo path field here."

        with patch.object(Path, "home", return_value=tmp_path):
            result = pre_vault_write.validate_vault_write(target, content)

        assert result["allowed"] is False  # still requires ## Path:, not silently skipped

    def test_uppercase_md_extension_is_validated(self, tmp_path):
        """Regression: `file_path.endswith(".md")` was case-sensitive, so
        PROJECT.MD on Windows bypassed Check 2 entirely."""
        import pre_vault_write

        target = _vault_path(tmp_path, "projects", "MY-PROJECT.MD")
        content = "# My Project\n\nNo path field here."

        with patch.object(Path, "home", return_value=tmp_path):
            result = pre_vault_write.validate_vault_write(target, content)

        assert result["allowed"] is False

    def test_type_mentioned_in_prose_body_does_not_trigger_check3(self, tmp_path):
        """Regression: the old regex searched the WHOLE document for
        `type:\\s*(roadmap|...)`, so ordinary prose mentioning a config example
        like "type: plan" (not in frontmatter) false-triggered Check 3."""
        import pre_vault_write

        target = _vault_path(tmp_path, "projects", "example.md")
        content = (
            "# Example\n\n## Path: D:/Example/\n\n"
            "Here's a config sample:\n\n```\ntype: plan\n```\n\nMore text."
        )

        with patch.object(Path, "home", return_value=tmp_path):
            result = pre_vault_write.validate_vault_write(target, content)

        assert result.get("allowed", True) is True

    def test_type_in_real_frontmatter_still_triggers_check3(self, tmp_path):
        """Control for the fix above: a genuine frontmatter `type: plan` must
        still be caught -- the fix narrows the match, it must not blind it."""
        import pre_vault_write

        target = _vault_path(tmp_path, "projects", "roadmap.md")
        content = (
            "---\ntitle: Roadmap\ntype: plan\n---\n\n# Roadmap\n\n## Path: D:/Roadmap/\n\nContent."
        )

        with patch.object(Path, "home", return_value=tmp_path):
            result = pre_vault_write.validate_vault_write(target, content)

        assert result["allowed"] is False
        assert "type=plan" in result.get("reason", "")

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


class TestRealHookEntrypoint:
    """Regression (HIGH, external re-audit 2026-07-07): main() read
    hook_input["parameters"] instead of the real "tool_input" field the
    Claude Code PreToolUse envelope actually uses -- file_path was always ""
    so this hook silently allowed every write, and it was also never
    registered in settings.json at all. Both are now fixed; these tests
    exercise the real envelope shape via stdin, matching security_verify.py's
    test convention (TestMain)."""

    def _run_main(self, monkeypatch, data: dict) -> str:
        import pre_vault_write

        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            pre_vault_write.main()
        return buf.getvalue()

    def test_real_envelope_denies_repo_intel_personal_project(self, tmp_path, monkeypatch):
        with patch.object(Path, "home", return_value=tmp_path):
            target = _vault_path(tmp_path, "repo-intel", "my-repo.md")
            data = {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": target,
                    "content": "# My Repo\ngithub.com/sergeeey/my-repo\nsome content",
                },
            }
            out = self._run_main(monkeypatch, data)

        assert '"permissionDecision": "deny"' in out or '"permissionDecision":"deny"' in out
        assert "repo-intel" in out.lower()

    def test_real_envelope_silent_on_valid_write(self, tmp_path, monkeypatch):
        """Matches security_verify.py's convention: no objection -> no output."""
        with patch.object(Path, "home", return_value=tmp_path):
            target = _vault_path(tmp_path, "projects", "my-project.md")
            data = {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": target,
                    "content": "# My Project\n\n## Path: D:/my-project/\n\nDescription.",
                },
            }
            out = self._run_main(monkeypatch, data)

        assert out == ""

    def test_non_write_edit_tool_silent(self, monkeypatch):
        data = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
        out = self._run_main(monkeypatch, data)
        assert out == ""

    def test_missing_file_path_silent(self, monkeypatch):
        data = {"tool_name": "Write", "tool_input": {"content": "no path here"}}
        out = self._run_main(monkeypatch, data)
        assert out == ""

    def test_malformed_json_fails_closed(self, monkeypatch):
        """Regression (issue #195, external audit 2026-07-15 follow-up):
        parse_stdin()'s old default {} return on bad JSON was
        indistinguishable from "nothing to check", so main()'s `if not
        hook_input: return` silently allowed the write -- fail_closed=True
        on hook_main never saw an exception to react to. Now uses
        parse_stdin(strict=True) and explicitly denies instead."""
        import pre_vault_write

        monkeypatch.setattr("sys.stdin", io.StringIO("not valid json {"))
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            pre_vault_write.main()  # WHY no pytest.raises: caught internally, still doesn't crash
        out = buf.getvalue()
        assert '"permissionDecision": "deny"' in out or '"permissionDecision":"deny"' in out

    def test_edit_reconstructs_full_content_not_just_new_string(self, tmp_path, monkeypatch):
        """Regression: checking new_string alone would miss a repo-intel
        violation that's already in the file and untouched by this specific
        edit -- reconstruction against the real on-disk content catches it."""
        with patch.object(Path, "home", return_value=tmp_path):
            target_path = Path(_vault_path(tmp_path, "repo-intel", "my-repo.md"))
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(
                "# My Repo\ngithub.com/sergeeey/my-repo\nold content", encoding="utf-8"
            )
            data = {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(target_path),
                    "old_string": "old content",
                    "new_string": "new content, unrelated to the violation",
                },
            }
            out = self._run_main(monkeypatch, data)

        assert '"permissionDecision": "deny"' in out or '"permissionDecision":"deny"' in out

    def test_edit_reconstruction_honors_replace_all(self, tmp_path):
        """Regression (external review, 2026-07-21): a hardcoded count=1 in
        str.replace() undercounts when the real Edit used replace_all=True --
        a violation introduced only by the SECOND occurrence of old_string
        would be invisible to validate_vault_write()'s reconstructed view."""
        import pre_vault_write

        target_path = Path(_vault_path(tmp_path, "projects", "x.md"))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text("# X\n\nold\n\nmore text\n\nold\n\nend", encoding="utf-8")
        tool_input = {
            "file_path": str(target_path),
            "old_string": "old",
            "new_string": "type: plan",
            "replace_all": True,
        }

        reconstructed = pre_vault_write._reconstruct_content(str(target_path), tool_input)
        assert reconstructed.count("old") == 0
        assert reconstructed.count("type: plan") == 2

    def test_edit_reconstruction_without_replace_all_replaces_only_first(self, tmp_path):
        """Control for the fix above: without replace_all, behavior must stay count=1,
        matching what a real (non-replace_all) Edit call actually does."""
        import pre_vault_write

        target_path = Path(_vault_path(tmp_path, "projects", "x.md"))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text("old\n\nmore text\n\nold\n\nend", encoding="utf-8")
        tool_input = {
            "file_path": str(target_path),
            "old_string": "old",
            "new_string": "new",
        }

        reconstructed = pre_vault_write._reconstruct_content(str(target_path), tool_input)
        assert reconstructed.count("old") == 1
        assert reconstructed.count("new") == 1
