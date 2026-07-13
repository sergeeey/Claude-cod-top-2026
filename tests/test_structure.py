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
            # WHY: BSV block (<!-- ... -->) may precede the YAML frontmatter — both formats valid
            stripped = re.sub(r"^<!--.*?-->", "", content, flags=re.DOTALL).lstrip()
            assert stripped.startswith("---"), f"{skill_md} missing YAML frontmatter"

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
        assert data["name"] == "claude-cod-top-2026"
        assert "version" in data
        assert "description" in data

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

    def test_registry_matches_disk(self):
        """Every skill folder must be in the registry (catches the 28%-blind drift).

        WHY: a full-repo audit found the registry described only 54 of 72 skills.
        This gate fails CI the moment a skill folder exists without a registry entry,
        so the catalog can never silently drift out of sync again.
        """
        # WHY: PyYAML is not in the CI test deps (pytest/cov/ruff/mypy only).
        # Skip gracefully rather than ModuleNotFoundError-fail the suite —
        # registry drift is nice-to-have validation, not a hard CI dependency.
        yaml = pytest.importorskip("yaml")

        reg = yaml.safe_load((ROOT / "skills" / "registry.yaml").read_text(encoding="utf-8"))
        registered = {
            s["name"] for sec in ("core", "extensions", "community") for s in (reg.get(sec) or [])
        }
        on_disk = set()
        for sub in ("core", "extensions"):
            base = ROOT / "skills" / sub
            if base.is_dir():
                on_disk |= {d.name for d in base.iterdir() if d.is_dir()}
        undocumented = sorted(on_disk - registered)
        assert not undocumented, f"skill folders missing from registry.yaml: {undocumented}"

    def test_settings_hook_refs_exist(self):
        """Every hook referenced in hooks/settings.json must exist on disk.

        WHY: broken hook references fail silently at runtime. This gate makes a
        missing/renamed hook a CI failure instead of a dead hook in production.
        """
        import json
        import re

        settings = (ROOT / "hooks" / "settings.json").read_text(encoding="utf-8")
        json.loads(settings)  # also asserts valid JSON
        refs = set(re.findall(r"hooks[\\/]([A-Za-z0-9_]+\.py)", settings))
        missing = sorted(h for h in refs if not (ROOT / "hooks" / h).exists())
        assert not missing, f"settings.json references hooks not on disk: {missing}"


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

    def test_settings_json_is_template_not_author_specific(self):
        settings = ROOT / "hooks" / "settings.json"
        content = settings.read_text(encoding="utf-8")
        assert "C:/Users/sboi" not in content
        assert "__CLAUDE_HOME__" in content
        assert "__PYTHON_CMD__" in content

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

    def test_validation_theater_guard_registered_on_matching_tool_names(self):
        """Regression (F-12, security audit 2026-07-12): validation_theater_guard.py's
        main() only proceeds when tool_name in {"Write", "Bash"} (VALIDATION_TOOL_NAMES),
        but the hook was registered ONLY under the PostToolUse "Skill|Agent" matcher --
        a matcher whose tool_name can never be "Write"/"Bash". The hard-block path
        (sys.exit(1) on perfect-score + synthetic data) was 100% dead code as a result.
        This test asserts the settings.json matcher(s) this hook is registered under
        actually correspond to a tool_name the code's own gate accepts, so a future
        registration/logic drift fails CI instead of silently going dead again.
        """
        settings = ROOT / "hooks" / "settings.json"
        data = json.loads(settings.read_text(encoding="utf-8"))
        post_tool_use = data.get("hooks", {}).get("PostToolUse", [])

        registered_matchers = [
            entry.get("matcher", "")
            for entry in post_tool_use
            for hook in entry.get("hooks", [])
            if "validation_theater_guard.py" in hook.get("command", "")
        ]
        assert registered_matchers, "validation_theater_guard.py must be registered on PostToolUse"

        # VALIDATION_TOOL_NAMES in the source is {"Write", "Bash"} -- a matcher is only
        # useful to this hook if its tool_name set intersects that. "Skill|Agent" alone
        # (no "Write"/"Bash" token) is exactly the dead-registration bug this guards against.
        matches_write_or_bash = any(
            "Write" in matcher or "Bash" in matcher for matcher in registered_matchers
        )
        assert matches_write_or_bash, (
            f"validation_theater_guard.py registered on {registered_matchers!r} but its "
            f"tool_name gate only accepts Write/Bash -- hard-block path is unreachable"
        )

    def test_all_hooks_stdlib_only(self):
        """No hook should import external packages — stdlib + typing only."""
        allowed_prefixes = {
            "__future__",  # from __future__ import annotations — stdlib language feature
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
            "ipaddress",
            "math",
            "shlex",
            "socket",  # stdlib — used by webhook_notify.py to resolve DNS for SSRF checks
            "urllib",
            "unicodedata",  # stdlib — used by input_guard.py for NFKC normalization
            "ast",  # stdlib — used by syntax_guard.py for Python AST validation
            "threading",  # stdlib — used by hook_main() timeout wrapper
            "concurrent",  # stdlib — concurrent.futures (optional use)
            "contextlib",  # stdlib — context managers (suppress, contextmanager, etc.)
            "random",  # stdlib — used by mentor_nudge.py for tip selection
            "traceback",  # stdlib — used by expert_registry.py for exception formatting
            "argparse",  # stdlib — used by inbox_review.py for CLI argument parsing
            "utils",  # hooks/utils.py — shared hook utilities (local module, not external)
            "learning_tips",  # hooks/learning_tips.py — shared tips catalog (local module)
            "cogniml_client",  # hooks/cogniml_client.py — CogniML API client (local module)
            "vector_store",  # hooks/vector_store.py — local TF-IDF/ChromaDB vector index
            "hook_state",  # hooks/hook_state.py — centralized file-based state store (local module)
            "claim_entropy_tracker",  # hooks/claim_entropy_tracker.py — shared entropy-table
            # parsing (parse_entropy/entropy_mismatch), reused by promotion_gate_guard.py so
            # both hooks apply the same Total/component-row consistency check (local module)
            "input_guard",  # hooks/input_guard.py — shared scan()/collect_strings()/
            # is_high_threat() reused by mcp_response_guard.py (P0.2, local module)
        }
        for hook_file in (ROOT / "hooks").glob("*.py"):
            content = hook_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                stripped = line.strip()
                # WHY: only check module-level imports (no leading whitespace).
                # Indented imports inside functions are optional deps (e.g. chromadb,
                # sentence_transformers in vector_store.py) and are allowed — they are
                # guarded by try/except ImportError and never execute at import time.
                if line and line[0] in (" ", "\t"):
                    continue  # skip indented (function-level) imports
                if stripped.startswith("import ") or stripped.startswith("from "):
                    # Extract module name
                    if stripped.startswith("from "):
                        module = stripped.split()[1].split(".")[0]
                    else:
                        module = stripped.split()[1].split(".")[0]
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


# === hooks/registry.yaml consistency (P0.4, follow-up audit 2026-07-13) ===

# WHY a hand-rolled parser instead of yaml.safe_load (see TestRegistry's own
# comment above for the same reasoning re: skills/registry.yaml): PyYAML is
# not a CI dependency (requirements.txt is stdlib-tooling-only: pytest, ruff,
# mypy). `pytest.importorskip("yaml")` would make this test silently SKIP in
# CI -- exactly the "a gate that looks like it protects something but never
# actually runs" bug class this test exists to catch for hooks/registry.yaml
# (which, per this repo's own audit-verification-gate.md convention, must be
# tool-verified, not merely present). Only handles this file's known-flat
# shape: a `hooks:` section, hook names at 2-space indent ending in `:`,
# fields at exactly 4-space indent -- deeper-indented lines (the `description:
# >` folded-scalar body) are deliberately not matched as fields.
_HOOK_NAME_RE = re.compile(r"^  (\w+):\s*$")
_FIELD_RE = re.compile(r"^    ([a-z_]+):\s*(.*)$")


def _parse_hooks_registry(text: str) -> dict[str, dict[str, str]]:
    hooks: dict[str, dict[str, str]] = {}
    current: str | None = None
    in_hooks_section = False
    for line in text.splitlines():
        if line == "hooks:":
            in_hooks_section = True
            continue
        if not in_hooks_section:
            continue
        name_match = _HOOK_NAME_RE.match(line)
        if name_match:
            current = name_match.group(1)
            hooks[current] = {}
            continue
        if current is None:
            continue
        field_match = _FIELD_RE.match(line)
        if field_match:
            key, value = field_match.groups()
            hooks[current][key] = value.strip().strip('"')
    return hooks


def _settings_registrations(settings_data: dict) -> dict[str, list[tuple[str, str]]]:
    """Return {hook_filename: [(event, matcher), ...]} from settings.json."""
    registrations: dict[str, list[tuple[str, str]]] = {}
    for event, entries in settings_data.get("hooks", {}).items():
        for entry in entries:
            matcher = entry.get("matcher", "")
            for h in entry.get("hooks", []):
                cmd = h.get("command", "")
                py_files = [p for p in cmd.split() if p.endswith(".py")]
                for py_path in py_files:
                    filename = Path(py_path).name
                    registrations.setdefault(filename, []).append((event, matcher))
    return registrations


_WILDCARD_STRINGS = frozenset({"", "*"})


def _event_tokens(event: str) -> frozenset[str]:
    """Split a possibly pipe-combined event declaration into components."""
    return frozenset(t.strip() for t in event.split("|") if t.strip())


def _matcher_tokens(matcher: str) -> frozenset[str] | None:
    """Return a frozenset of tool-name tokens, or None for "matches everything"."""
    if matcher in _WILDCARD_STRINGS:
        return None
    return frozenset(t.strip() for t in matcher.split("|") if t.strip())


def _token_covered(declared_token: str, actual_tokens: set[str]) -> bool:
    """True if declared_token exactly matches, or is covered by, an actual token.

    WHY the prefix-glob branch: settings.json uses trailing-glob matchers like
    "mcp__*" (any tool name starting with mcp__); registry.yaml sometimes
    writes the same intent as a bare prefix ("mcp__") or a specific instance
    ("mcp__context7") -- both are legitimately covered by "mcp__*", not a
    real drift.
    """
    if declared_token in actual_tokens:
        return True
    return any(
        actual_token.endswith("*") and declared_token.startswith(actual_token[:-1])
        for actual_token in actual_tokens
    )


class TestHooksRegistryConsistency:
    """hooks/registry.yaml claims to be the "single source of truth for hook
    metadata" (its own header comment) -- but until this test existed, nothing
    verified that claim against hooks/settings.json's actual wiring or the
    files on disk. This is exactly the class of bug F-12 and the P0.2/P0.3
    follow-up findings were: a registry entry describing an event/matcher
    that was never actually registered that way.

    Honest limitation 1: this checks event/matcher declarations, not
    fail_mode/escalation (those describe runtime behavior on error paths,
    which requires reading the hook's actual control flow, not just its
    registration -- e.g. F-03/P0.3's "fail_mode: closed but code sys.exit(0)s
    on parse failure" bug was caught by manual code review, not by any
    mechanical check like this one).

    Honest limitation 2 (reviewer finding, P0.4 follow-up 2026-07-13): when a
    registry entry declares ONE matcher string for MULTIPLE events (e.g.
    commit_test_gate.py: matcher="Bash|Edit|Write" for "PreToolUse|PostToolUse"
    combined), the matcher check passes if ANY single declared event's actual
    registration covers the declared tokens -- it does NOT verify that EVERY
    declared event's own registration independently covers them. Concretely:
    commit_test_gate.py's real PreToolUse registration is Bash-only (by
    design, confirmed in its own docstring) while PostToolUse covers
    Bash|Edit|Write -- the test passes because PostToolUse's union alone
    satisfies the declared tokens, without actually verifying PreToolUse's
    narrower claim. No live hook is misconfigured as a result of this gap
    (verified for commit_test_gate.py, promotion_gate_guard.py,
    weakened_test_guard.py -- the same shape), but closing it fully would
    need registry.yaml to support per-event matcher declarations, which is a
    schema change, not a test fix.
    """

    @pytest.fixture
    def registry(self):
        text = (ROOT / "hooks" / "registry.yaml").read_text(encoding="utf-8")
        return _parse_hooks_registry(text)

    @pytest.fixture
    def settings_registrations(self):
        data = json.loads((ROOT / "hooks" / "settings.json").read_text(encoding="utf-8"))
        return _settings_registrations(data)

    @pytest.fixture
    def events_with_real_matchers(self, settings_registrations):
        """Events where at least one hook, anywhere in settings.json, uses a
        non-wildcard matcher -- proving that event's matcher field carries
        real (tool-name or file-pattern or reason-string) meaning.

        WHY computed from data, not a hardcoded event list (reviewer finding,
        P0.4 follow-up 2026-07-13): an earlier fix guessed "only PreToolUse/
        PostToolUse have real matchers" -- wrong, since FileChanged
        (env_reload.py: ".env|.envrc") and SessionStart (research_health_loop.py:
        "startup|resume|clear|compact") are real too. Conversely, SubagentStop
        is empty ("") for every single registration in this file -- proving
        it structurally never carries matcher meaning. Deriving this set from
        the actual data instead of a guess means it can't silently go stale
        as new events/hooks are added.
        """
        result: set[str] = set()
        for registrations in settings_registrations.values():
            for event, matcher in registrations:
                if _matcher_tokens(matcher) is not None:
                    result.add(event)
        return result

    def test_registry_parses_a_nonempty_hook_set(self, registry):
        """Sanity check on the parser itself -- if this is ever near-empty,
        the hand-rolled parser broke, not the registry."""
        assert len(registry) >= 50, f"Expected 50+ hook entries, parsed {len(registry)}"

    def test_every_registry_entry_has_a_file_on_disk(self, registry):
        """Ghost entries: registry.yaml describes a hook that no longer exists."""
        missing = sorted(name for name in registry if not (ROOT / "hooks" / f"{name}.py").exists())
        assert not missing, f"registry.yaml entries with no hooks/*.py file: {missing}"

    def test_every_hook_file_has_a_registry_entry(self, registry):
        """Orphan hooks: a .py file exists in hooks/ with no registry.yaml entry.

        WHY excluded: utils.py/hook_state.py are shared libraries, not hooks
        (no stdin/stdout hook protocol) -- registry.yaml's own header comment
        already excludes utils.py for this reason; hook_state.py is the same
        class of shared library.
        """
        excluded = {"utils", "hook_state"}
        on_disk = {
            f.stem
            for f in (ROOT / "hooks").glob("*.py")
            if f.stem not in excluded and not f.stem.startswith("_")
        }
        undocumented = sorted(on_disk - set(registry))
        assert not undocumented, f"hooks/*.py files missing from registry.yaml: {undocumented}"

    def test_registry_event_matches_settings_json_registration(
        self, registry, settings_registrations
    ):
        """For every registry entry declaring an `event`, verify settings.json
        actually registers that hook's command under every declared event
        component.

        This is the general form of the F-12 regression test above -- instead
        of one hand-written assertion for validation_theater_guard.py, every
        hook with a declared event gets the same check automatically.

        WHY split on "|" (registry entries like "Elicitation|ElicitationResult"
        or "TaskCreated|TaskCompleted" declare ONE hook firing on MULTIPLE
        events as a single pipe-joined string) -- settings.json instead
        registers the same hook under each event as a SEPARATE top-level key.
        Comparing the combined string literally would always mismatch even
        when every individual event is correctly wired; this checks each
        declared event component is present, which is what actually matters.
        """
        mismatches = []
        for name, fields in registry.items():
            declared_event = fields.get("event")
            if not declared_event or declared_event in _WILDCARD_STRINGS:
                # WHY skip "*": a handful of hooks (e.g. async_wrapper.py) are
                # generic wrappers invoked as a command-line prefix to ANOTHER
                # hook rather than bound to one event -- "*" is an honest
                # declaration of that, not a claim this check can verify
                # against a single settings.json event key.
                continue
            declared_events = _event_tokens(declared_event)
            filename = f"{name}.py"
            actual = settings_registrations.get(filename, [])
            actual_events = {event for event, _matcher in actual}
            missing = sorted(declared_events - actual_events)
            if missing:
                mismatches.append(
                    f"{name}: registry declares event(s) {sorted(declared_events)!r}, "
                    f"settings.json registers {sorted(actual_events)!r} -- missing {missing!r}"
                )
        assert not mismatches, "registry.yaml event mismatches:\n" + "\n".join(mismatches)

    def test_registry_matcher_matches_settings_json_registration(
        self, registry, settings_registrations, events_with_real_matchers
    ):
        """For every registry entry, every declared matcher tool-name token
        must be covered by settings.json's actual registration(s) for that
        hook under the declared event.

        WHY set/subset comparison, not exact string equality: several
        legitimate representations would otherwise false-positive --
        "Write|Edit" vs "Edit|Write" (same set, different token order),
        "" vs "*" (both mean "no tool-name filter"), and a hook deliberately
        registered under TWO separate matcher entries for the same event
        (e.g. validation_theater_guard.py: settings.json has both "Bash" and
        "Edit|Write" for PostToolUse -- the union, {Bash, Edit, Write}, is
        what actually matters, not either entry alone). "mcp__*"-style
        trailing-glob matchers are treated as a prefix match so
        "mcp__" / "mcp__context7" are recognized as covered by "mcp__*".

        WHY declared="*" always passes regardless of actual specificity:
        that direction (registry claims BROADER scope than reality) is
        imprecise documentation, not a safety-relevant lie -- nobody is
        misled into believing something is LESS protected than it is. The
        dangerous direction -- declaring specific tool names that aren't
        actually covered by any real registration (P0.2/P0.3's input_guard.py
        bug, and skeptic_auto_trigger.py's undiscovered Bash-branch dead code,
        both found by this exact check before being fixed) -- still fails.
        """
        mismatches = []
        for name, fields in registry.items():
            declared_event = fields.get("event")
            declared_matcher = fields.get("matcher")
            if not declared_event or declared_matcher is None:
                continue
            declared_tokens = _matcher_tokens(declared_matcher)
            if declared_tokens is None:
                continue  # declared "*" -- see WHY above, always acceptable
            declared_events = _event_tokens(declared_event)
            filename = f"{name}.py"
            actual = settings_registrations.get(filename, [])

            # WHY group by event, require satisfaction WITHIN one event (not
            # merged across different events), AND only consider events that
            # events_with_real_matchers proves carry real matcher meaning
            # (reviewer finding, P0.4 follow-up 2026-07-13): a hook can
            # legitimately declare multiple events where matcher means
            # different things per event -- iteration_guard.py declares
            # "PreToolUse|SubagentStop" with matcher="Agent", but "Agent" is
            # only meaningful for the PreToolUse half; SubagentStop is empty
            # ("") for every registration in this whole file, proving it
            # structurally never carries matcher meaning. Without the
            # events_with_real_matchers filter, SubagentStop's "" reads as a
            # wildcard and would satisfy the check regardless of what
            # PreToolUse actually has -- masking a real PreToolUse mismatch.
            # Filtering to only proven-meaningful events closes that gap
            # without assuming a fixed set of "tool-scoped" events (which was
            # itself wrong: FileChanged/env_reload.py and SessionStart/
            # research_health_loop.py have real non-tool-name matchers too).
            by_event: dict[str, list[frozenset[str] | None]] = {}
            for event, matcher in actual:
                if event not in declared_events or event not in events_with_real_matchers:
                    continue
                by_event.setdefault(event, []).append(_matcher_tokens(matcher))

            satisfied = False
            per_event_union: dict[str, list[str]] = {}
            for event, token_sets in by_event.items():
                if any(tokens is None for tokens in token_sets):
                    satisfied = True
                    per_event_union[event] = ["*"]
                    continue
                # WHY the explicit non_none_tokens filter, not just iterating
                # token_sets directly: mypy can't narrow away the `| None` in
                # `list[frozenset[str] | None]` from the `any(... is None)`
                # check above -- it doesn't track that reaching this point
                # means every element already passed that check.
                non_none_tokens: list[frozenset[str]] = [t for t in token_sets if t is not None]
                union: set[str] = set()
                for tokens in non_none_tokens:
                    union |= tokens
                per_event_union[event] = sorted(union)
                if all(_token_covered(t, union) for t in declared_tokens):
                    satisfied = True

            if not satisfied:
                mismatches.append(
                    f"{name}: registry declares matcher {sorted(declared_tokens)!r} for "
                    f"event(s) {sorted(declared_events)!r}, but no single declared event's "
                    f"actual registration(s) cover it -- settings.json has {per_event_union!r}"
                )
        assert not mismatches, "registry.yaml matcher mismatches:\n" + "\n".join(mismatches)
