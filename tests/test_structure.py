"""Structure validation tests — verify repo integrity."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SKILLS_CORE = ROOT / "skills" / "core"
SKILLS_EXT = ROOT / "skills" / "extensions"


# === Core skills structure ===


class TestCoreSkills:
    def test_core_directory_exists(self):
        assert SKILLS_CORE.is_dir(), "skills/core/ directory must exist"

    def test_core_has_minimum_skills(self):
        dirs = [d for d in SKILLS_CORE.iterdir() if d.is_dir()]
        assert len(dirs) >= 4, f"Expected 4+ core skills, found {len(dirs)}"

    @pytest.mark.parametrize(
        "skill_name",
        ["routing-policy", "brainstorming", "tdd-workflow", "git-worktrees", "mentor-mode"],
    )
    def test_core_skill_has_skill_md(self, skill_name):
        skill_md = SKILLS_CORE / skill_name / "SKILL.md"
        assert skill_md.exists(), f"Core skill {skill_name} missing SKILL.md"


# === Extension skills structure ===


class TestExtensionSkills:
    def test_extensions_directory_exists(self):
        assert SKILLS_EXT.is_dir(), "skills/extensions/ directory must exist"

    @pytest.mark.parametrize(
        "skill_name",
        ["security-audit", "archcode-genomics", "geoscan", "notebooklm", "suno-music"],
    )
    def test_extension_has_skill_md(self, skill_name):
        skill_md = SKILLS_EXT / skill_name / "SKILL.md"
        assert skill_md.exists(), f"Extension {skill_name} missing SKILL.md"

    @pytest.mark.parametrize(
        "skill_name",
        ["security-audit", "archcode-genomics", "geoscan", "notebooklm", "suno-music"],
    )
    def test_extension_has_plugin_json(self, skill_name):
        plugin = SKILLS_EXT / skill_name / "plugin.json"
        assert plugin.exists(), f"Extension {skill_name} missing plugin.json"

    @pytest.mark.parametrize(
        "skill_name",
        ["security-audit", "archcode-genomics", "geoscan", "notebooklm", "suno-music"],
    )
    def test_plugin_json_is_valid(self, skill_name):
        plugin = SKILLS_EXT / skill_name / "plugin.json"
        data = json.loads(plugin.read_text(encoding="utf-8"))
        assert "name" in data
        assert "description" in data
        assert "category" in data


# === SKILL.md frontmatter validation ===


class TestSkillFrontmatter:
    def _get_all_skill_mds(self):
        """Collect all SKILL.md files across core and extensions."""
        results = []
        for base in [SKILLS_CORE, SKILLS_EXT]:
            if not base.exists():
                continue
            for skill_dir in base.iterdir():
                if skill_dir.is_dir():
                    skill_md = skill_dir / "SKILL.md"
                    if skill_md.exists():
                        results.append(skill_md)
        return results

    def test_all_skills_have_frontmatter(self):
        for skill_md in self._get_all_skill_mds():
            content = skill_md.read_text(encoding="utf-8")
            assert content.startswith("---"), f"{skill_md} missing YAML frontmatter"

    def test_all_skills_have_name_field(self):
        for skill_md in self._get_all_skill_mds():
            content = skill_md.read_text(encoding="utf-8")
            assert re.search(r"^name:", content, re.MULTILINE), f"{skill_md} missing 'name'"

    def test_all_skills_have_description_field(self):
        for skill_md in self._get_all_skill_mds():
            content = skill_md.read_text(encoding="utf-8")
            assert re.search(r"^description:", content, re.MULTILINE), (
                f"{skill_md} missing 'description'"
            )


# === Plugin manifests ===


class TestPluginManifests:
    def test_root_plugin_json_valid(self):
        plugin = ROOT / ".claude-plugin" / "plugin.json"
        assert plugin.exists()
        data = json.loads(plugin.read_text(encoding="utf-8"))
        assert data["name"] == "claude-code-config"
        assert "skills" in data
        assert len(data["skills"]) >= 5

    def test_marketplace_json_valid(self):
        marketplace = ROOT / ".claude-plugin" / "marketplace.json"
        assert marketplace.exists()
        data = json.loads(marketplace.read_text(encoding="utf-8"))
        assert "plugins" in data
        assert "extensions" in data
        assert len(data["extensions"]) >= 4

    def test_marketplace_extensions_match_filesystem(self):
        marketplace = ROOT / ".claude-plugin" / "marketplace.json"
        data = json.loads(marketplace.read_text(encoding="utf-8"))
        for ext in data["extensions"]:
            source_path = ROOT / ext["source"]
            assert source_path.exists(), (
                f"Marketplace references {ext['source']} but it doesn't exist"
            )


# === Registry ===


class TestRegistry:
    def test_registry_exists(self):
        registry = ROOT / "skills" / "registry.yaml"
        assert registry.exists()

    def test_registry_has_core_and_extensions(self):
        registry = ROOT / "skills" / "registry.yaml"
        content = registry.read_text(encoding="utf-8")
        assert "core:" in content
        assert "extensions:" in content


# === Hooks integrity ===


class TestHooksIntegrity:
    def test_hooks_directory_exists(self):
        hooks = ROOT / "hooks"
        assert hooks.is_dir()

    def test_minimum_hook_count(self):
        hooks = list((ROOT / "hooks").glob("*.py"))
        assert len(hooks) >= 10, f"Expected 10+ hooks, found {len(hooks)}"

    def test_settings_json_exists(self):
        settings = ROOT / "hooks" / "settings.json"
        assert settings.exists()
        data = json.loads(settings.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_settings_hooks_reference_existing_files(self):
        """Every command in settings.json must point to a .py file that exists in hooks/."""
        settings = ROOT / "hooks" / "settings.json"
        data = json.loads(settings.read_text(encoding="utf-8"))
        hooks_section = data.get("hooks", {})
        for _event, matchers in hooks_section.items():
            for matcher_entry in matchers:
                for hook in matcher_entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    # Extract the .py filename from the command
                    parts = cmd.split()
                    py_files = [p for p in parts if p.endswith(".py")]
                    for py_path in py_files:
                        filename = Path(py_path).name
                        # File must exist in hooks/ or scripts/
                        exists_in_hooks = (ROOT / "hooks" / filename).exists()
                        exists_in_scripts = (ROOT / "scripts" / filename).exists()
                        assert exists_in_hooks or exists_in_scripts, (
                            f"Hook references {filename} but it doesn't exist"
                        )

    def test_all_hooks_stdlib_only(self):
        """No hook should import external packages — stdlib + typing only."""
        allowed_prefixes = {
            "json",
            "sys",
            "re",
            "os",
            "time",
            "pathlib",
            "typing",
            "datetime",
            "collections",
            "subprocess",
            "hashlib",
            "io",
            "functools",
            "itertools",
            "textwrap",
            "shutil",
            "tempfile",
            "glob",
            "string",
            "enum",
            "dataclasses",
            "abc",
            "copy",
            "math",
        }
        for hook_file in (ROOT / "hooks").glob("*.py"):
            content = hook_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("import ") or line.startswith("from "):
                    # Extract module name
                    if line.startswith("from "):
                        module = line.split()[1].split(".")[0]
                    else:
                        module = line.split()[1].split(".")[0]
                    assert module in allowed_prefixes, (
                        f"{hook_file.name} imports external package: {module}"
                    )

    def test_all_agents_have_content(self):
        """Every agent .md file should have non-trivial content."""
        agents_dir = ROOT / "agents"
        if not agents_dir.exists():
            pytest.skip("agents/ directory not found")
        for agent_md in agents_dir.glob("*.md"):
            content = agent_md.read_text(encoding="utf-8").strip()
            assert len(content) > 50, f"Agent {agent_md.name} is empty or trivial"

    def test_claude_md_under_token_limit(self):
        """CLAUDE.md should be compact — under 100 lines for ~800 tokens."""
        claude_md = ROOT / "claude-md" / "CLAUDE.md"
        if not claude_md.exists():
            pytest.skip("claude-md/CLAUDE.md not found")
        lines = claude_md.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 120, (
            f"CLAUDE.md has {len(lines)} lines — should be under 120 for token efficiency"
        )

    def test_rules_have_no_todos(self):
        """Rules should not contain TODO/FIXME/HACK markers."""
        rules_dir = ROOT / "rules"
        if not rules_dir.exists():
            pytest.skip("rules/ directory not found")
        for rule_file in rules_dir.glob("*.md"):
            content = rule_file.read_text(encoding="utf-8")
            for marker in ["TODO", "FIXME", "HACK", "XXX"]:
                assert marker not in content, (
                    f"Rule {rule_file.name} contains {marker} — clean up before shipping"
                )

    def test_install_has_all_profiles(self):
        """install.sh must reference all 3 installation profiles."""
        install_sh = ROOT / "install.sh"
        assert install_sh.exists()
        content = install_sh.read_text(encoding="utf-8")
        for profile in ["minimal", "standard", "full"]:
            assert profile in content, f"install.sh missing profile: {profile}"
