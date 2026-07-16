"""Structure validation tests — verify repo integrity."""

import json
import re
from datetime import date
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

    def test_every_metadata_file_states_the_same_counts_as_the_filesystem(self):
        """Every metadata file that states a hooks/agents/skills count must match
        what is actually on disk.

        WHY (external audit 2026-07-16): .claude-plugin/marketplace.json claimed
        "87 deterministic hooks" while disk had 88. Two independent defects let it
        drift silently: (1) CI's check_meta loop listed only 2 of the 3 metadata
        files -- this one was absent, and (2) its "N deterministic hooks" phrasing
        does not match a plain "N hooks" pattern, so the count evaded the gate by
        adjective even where the gate did look. This test is the pytest-side
        counterpart to the hardened CI shell gate: it runs locally (CI's shell
        gate only runs on the 3.12 matrix leg) and enumerates the metadata files
        from a single list, so adding a 4th file that states counts is the only
        thing a contributor has to remember.
        """
        # Same filesystem definitions the CI "Verify doc counts" step uses.
        actual = {
            # utils.py / severity_calibrator.py are shared libraries, not counted hooks
            # (severity_calibrator is RFC-003 step 3, not wired until shadow mode = step 5).
            "hooks": len(
                [
                    p
                    for p in (ROOT / "hooks").glob("*.py")
                    if p.name not in ("utils.py", "severity_calibrator.py")
                ]
            ),
            "agents": len(list((ROOT / "agents").glob("*.md"))),
            "skills": len(list(ROOT.glob("skills/**/SKILL.md"))),
        }

        metadata_files = [
            ROOT / ".claude-plugin" / "plugin.json",
            ROOT / ".claude-plugin" / "marketplace.json",
            ROOT / "marketplace.json",
        ]

        drift = []
        for meta_file in metadata_files:
            if not meta_file.exists():
                continue
            text = meta_file.read_text(encoding="utf-8")
            for kind, expected in actual.items():
                # Allow one interstitial adjective ("88 deterministic hooks") so a
                # rephrase cannot un-gate the number the way it did in the audit.
                for stated in re.findall(rf"(\d+) (?:[a-z]+ )?{kind}\b", text):
                    if int(stated) != expected:
                        drift.append(
                            f"{meta_file.relative_to(ROOT).as_posix()} states "
                            f"{stated} {kind} but the filesystem has {expected}"
                        )

        assert not drift, "Metadata count drift:\n  " + "\n  ".join(drift)


# === Dependency graph ===


class TestDependencyBacklinks:
    """A depends_on edge must be visible from BOTH ends.

    WHY (audit 2026-07-16): registry.yaml recorded 10 real depends_on edges, but the
    relationship was only ever written down on the downstream side. A reader landing
    on skills/extensions/sci-hypothesis/SKILL.md had no way to learn that
    hypothesis-arbiter consumes its output -- the edge existed in the registry and
    nowhere in the skill itself. Nine upstream skills were missing 14 backlinks.
    One-directional edges make the catalog look like a bag of skills instead of a
    graph, which is exactly the "blocks, not system" problem this sprint addresses.

    The backlink is prose, deliberately: the point is that a human reading the
    upstream skill learns who depends on it, not that a machine can parse it.

    KNOWN LIMITATION -- this gate does NOT run in CI. It needs PyYAML to read the
    registry, and requirements.txt pins only pytest/pytest-cov/ruff/mypy, so CI
    skips it silently (same as the pre-existing test_registry_matches_disk). It is
    therefore a local-only gate: real when you run the suite, absent on the branch
    protection path. Recorded here rather than left to be rediscovered, because
    "registered but not actually enforced" is precisely the confusion the
    Verification Substrate Gate (rules/falsification-ladder.md, Step 2a) exists to
    name. Adding PyYAML to requirements.txt would close it -- deliberately not done
    here to keep this sprint's diff to metadata/docs.
    """

    # Prereqs written as "name(rule)" / "name(hook)" / "name(MCP)" are external
    # (a rule file, a hook, an MCP server) -- they have no SKILL.md to link back from.
    @staticmethod
    def _is_skill_dep(dep: str) -> bool:
        return "(" not in str(dep)

    @staticmethod
    def _find_skill_md(name: str):
        for base in ("skills/core", "skills/extensions"):
            for candidate in (ROOT / base / name / "SKILL.md", ROOT / base / f"{name}.md"):
                if candidate.exists():
                    return candidate
        return None

    def test_every_dependency_has_a_backlink_from_its_upstream_skill(self):
        yaml = pytest.importorskip(
            "yaml", reason="PyYAML absent in CI's minimal deps; gate is nice-to-have"
        )
        registry = yaml.safe_load((ROOT / "skills" / "registry.yaml").read_text(encoding="utf-8"))

        # downstream -> [upstream, ...]
        edges = {}
        for items in registry.values():
            if not isinstance(items, list):
                continue
            for skill in items:
                if not isinstance(skill, dict) or not skill.get("depends_on"):
                    continue
                deps = [d for d in skill["depends_on"] if self._is_skill_dep(d)]
                if deps:
                    edges[skill["name"]] = deps

        missing = []
        for downstream, upstreams in edges.items():
            for upstream in upstreams:
                skill_md = self._find_skill_md(upstream)
                if skill_md is None:
                    # e.g. evolve-solution lives in commands/, not skills/ -- not a
                    # backlink failure, just not a skill.
                    continue
                if downstream not in skill_md.read_text(encoding="utf-8"):
                    missing.append(
                        f"{skill_md.relative_to(ROOT).as_posix()} never mentions "
                        f"'{downstream}', which declares depends_on: [{upstream}]"
                    )

        assert not missing, (
            "Dependency edges visible from only one end:\n  "
            + "\n  ".join(sorted(missing))
            + "\n\nAdd the consumer to the upstream skill's '## Связанные скилы' section."
        )


# === Capability schema (Sprint 2.1, registry v3-lite) ===


class TestRegistryCapabilitySchema:
    """A `capability:` block is optional, but if present it must be well-formed.

    WHY (Sprint 2.1): the router (dispatcher/routing-policy) selects skills by keyword
    today. Capability fields are the evolutionary step toward selecting by what a skill
    PROVIDES and how risky it is. Adding them is opt-in per skill -- this gate does not
    require the block, it only validates the shape and referential integrity of blocks
    that exist, so a half-authored capability entry can't silently ship.

    Runs in CI now that PyYAML is a pinned dev dep (requirements.txt) -- previously the
    yaml-reading gates skipped there vacuously.
    """

    _VALID_TIERS = {"Green", "Yellow", "Red", "Black"}

    def _registry(self):
        yaml = pytest.importorskip("yaml")
        return yaml.safe_load((ROOT / "skills" / "registry.yaml").read_text(encoding="utf-8"))

    def _skills_with_capability(self):
        for items in self._registry().values():
            if not isinstance(items, list):
                continue
            for skill in items:
                if isinstance(skill, dict) and "capability" in skill:
                    yield skill["name"], skill["capability"]

    def _all_skill_names(self):
        names = set()
        for items in self._registry().values():
            if not isinstance(items, list):
                continue
            for skill in items:
                if isinstance(skill, dict) and "name" in skill:
                    names.add(skill["name"])
        return names

    def test_capability_blocks_are_wellformed(self):
        bad = []
        for name, cap in self._skills_with_capability():
            if not isinstance(cap.get("provides"), list) or not cap["provides"]:
                bad.append(f"{name}: 'provides' must be a non-empty list")
            if cap.get("risk_tier") not in self._VALID_TIERS:
                bad.append(f"{name}: 'risk_tier' must be one of {sorted(self._VALID_TIERS)}")
            if not isinstance(cap.get("verification_required"), list):
                bad.append(f"{name}: 'verification_required' must be a list (may be empty)")
        assert not bad, "Malformed capability blocks:\n  " + "\n  ".join(bad)

    _KNOWN_PACKS = {
        "core-orchestration",
        "trust-and-evidence",
        "software-engineering",
        "memory-and-learning",
        "scientific-discovery",
        "self-development",
        "claim-pipeline",
    }

    def test_pack_values_match_the_constitution_taxonomy(self):
        """A `pack:` value must be one of the packs named in PRODUCT_CONSTITUTION.md
        (sections 7-8). A skill filed under a pack that does not exist is a routing
        dead-end -- the whole point of packs is that a user installs a coherent set."""
        bad = []
        for items in self._registry().values():
            if not isinstance(items, list):
                continue
            for skill in items:
                if isinstance(skill, dict) and skill.get("pack") not in (None, *self._KNOWN_PACKS):
                    bad.append(f"{skill.get('name')}: unknown pack {skill['pack']!r}")
        assert not bad, "Skills filed under unknown packs:\n  " + "\n  ".join(bad)

    def test_verification_required_references_real_skills(self):
        """Every skill named in a verification_required list must exist in the registry.

        Non-skill gates (source_trace, safety_floor_check, at_least_one_kill_test) are
        process requirements, not skills -- they are exempt from the existence check.
        """
        process_gates = {
            "source_trace",
            "safety_floor_check",
            "at_least_one_kill_test",
        }
        names = self._all_skill_names()
        dangling = []
        for name, cap in self._skills_with_capability():
            for req in cap.get("verification_required", []):
                if req not in names and req not in process_gates:
                    dangling.append(f"{name}: verification_required references unknown '{req}'")
        assert not dangling, "Dangling capability references:\n  " + "\n  ".join(dangling)


# === Rules not duplicated across scopes ===


class TestRulesNotDuplicated:
    """A rule must not exist as a byte-identical FULL copy in both `rules/` (canonical,
    installed globally) and `.claude/rules/` (project-native).

    WHY (config audit P1): `integrity`, `rationalizations`, `doubt-driven-development` were
    full copies in both scopes. In an installed repo BOTH load, so the content duplicated;
    worse, two copies drift. The fix: `rules/` is canonical; a `.claude/rules/` file with the
    same name must be either a short POINTER stub or a genuine ADDENDUM (project delta) --
    never a full copy. This gate stops the duplication from silently returning.
    """

    def test_no_claude_rule_is_a_full_copy_of_the_canonical(self):
        canonical_dir = ROOT / "rules"
        project_dir = ROOT / ".claude" / "rules"
        offenders = []
        for proj in sorted(project_dir.glob("*.md")):
            canon = canonical_dir / proj.name
            if not canon.exists():
                continue  # project-only rule (e.g. autonomy-budget) -- fine
            proj_text = proj.read_text(encoding="utf-8")
            canon_text = canon.read_text(encoding="utf-8")
            if proj_text.strip() == canon_text.strip():
                offenders.append(f"{proj.name}: byte-identical full copy of rules/{proj.name}")
                continue
            # not identical -> must clearly defer to the canonical (stub or addendum),
            # not just be a silently-diverged fork.
            defers = ("canonical" in proj_text.lower()) or ("addendum" in proj_text.lower())
            if not defers and len(proj_text) > len(canon_text) * 0.8:
                offenders.append(
                    f"{proj.name}: a near-full divergent copy that doesn't point to the "
                    f"canonical rules/{proj.name} (make it a stub or a marked addendum)"
                )
        assert not offenders, "Rule duplication across scopes:\n  " + "\n  ".join(offenders)


# === Path-scoped rules ===


class TestPathScopedRules:
    """A rule may carry `paths:` frontmatter to scope it to matching files. If it does,
    the frontmatter must be well-formed, or Claude Code's native rule loader (and any
    tooling that reads it) will silently mis-scope or ignore the rule.

    WHY only FILE-triggered rules are scoped (coding-style, testing): a path-scoped rule
    loads only when a matching file is touched. That is correct for rules that only matter
    while editing code/tests, but WRONG for keyword/conversation-triggered rules (research
    L0 gate, evidence policy, security) — a hypothesis or a security concern can arise with
    no file edit, so those stay always-on (no `paths:`). This test just validates the shape
    of whatever scoping exists; it does not require any rule to be scoped.
    """

    _FRONTMATTER = re.compile(r"\A(?:<!--.*?-->\s*)?---\n(.*?)\n---", re.DOTALL)

    def _rules_with_frontmatter(self):
        for rule in sorted((ROOT / "rules").glob("*.md")):
            text = rule.read_text(encoding="utf-8")
            m = self._FRONTMATTER.match(text)
            if m:
                yield rule.name, m.group(1)

    def test_path_scoped_frontmatter_is_valid(self):
        yaml = pytest.importorskip("yaml")
        bad = []
        for name, block in self._rules_with_frontmatter():
            try:
                meta = yaml.safe_load(block)
            except yaml.YAMLError as e:
                bad.append(f"{name}: invalid YAML frontmatter ({e})")
                continue
            if not isinstance(meta, dict) or "paths" not in meta:
                continue  # frontmatter without paths is fine (metadata-only)
            paths = meta["paths"]
            if not isinstance(paths, list) or not paths:
                bad.append(f"{name}: 'paths' must be a non-empty list of globs")
                continue
            for p in paths:
                if not isinstance(p, str) or not p.strip():
                    bad.append(f"{name}: path entry must be a non-empty string, got {p!r}")
        assert not bad, "Malformed path-scoped rules:\n  " + "\n  ".join(bad)


# === Research sources register (Sprint 3.2) ===


class TestResearchSources:
    """docs/research-sources.yaml must not let an external idea become an internal
    'proven' fact without provenance.

    WHY (Sprint 3.2): the register exists so an adopted external claim (a paper's
    metric, a competitor's mechanism) carries where it came from and whether it was
    independently reproduced HERE. The one invariant a machine can hold: a source may
    not claim reproduced/validated internal status without pointing at a real
    experiment or null_result -- otherwise the register itself becomes the laundering
    path it was built to prevent.
    """

    _VALID_STATUS = {
        "reviewed",
        "adopted",
        "rejected",
        "rejected_as_implementation",
        "watching",
        "watched",
        "proposed",
    }

    def _sources(self):
        yaml = pytest.importorskip("yaml")
        path = ROOT / "docs" / "research-sources.yaml"
        if not path.exists():
            pytest.skip("research-sources.yaml not present")
        return yaml.safe_load(path.read_text(encoding="utf-8")).get("sources", [])

    def test_every_source_is_wellformed(self):
        bad = []
        for s in self._sources():
            if not s.get("name"):
                bad.append("a source is missing 'name'")
                continue
            if s.get("status") not in self._VALID_STATUS:
                bad.append(f"{s['name']}: invalid status {s.get('status')!r}")
        assert not bad, "Malformed research-source rows:\n  " + "\n  ".join(bad)

    def test_no_source_claims_internal_validation_without_evidence(self):
        """internal_validation may be 'none' (or absent) or must name an artifact
        (an experiment id / null_result / a dated in-repo check). The strings
        'reproduced'/'validated'/'confirmed' alone, with no artifact, are exactly the
        unverified-becomes-fact move the register guards against."""
        offenders = []
        for s in self._sources():
            iv = str(s.get("internal_validation", "none")).strip().lower()
            if iv in ("none", ""):
                continue
            claims_validation = any(w in iv for w in ("reproduced", "validated", "confirmed"))
            names_artifact = any(w in iv for w in ("experiment", "null_result", "20260", "20261"))
            if claims_validation and not names_artifact:
                offenders.append(
                    f"{s['name']}: internal_validation '{iv}' claims validation, cites no artifact"
                )
        assert not offenders, "Ungrounded internal-validation claims:\n  " + "\n  ".join(offenders)


# === Skill lifecycle ===


class TestSkillLifecycle:
    """The 60-day staleness rule from docs/anti-patterns.md, actually enforced.

    WHY (audit 2026-07-16): the rule ("skill without update for 60+ days → status
    review") was documented since March and never enforced by anything. By July,
    39 of 47 lifecycle-tagged files still advertised [STATUS: confirmed] while
    sitting 60-126 days stale. A documented rule with no gate is a preference.

    Note this checks the DECLARED review date only. It cannot know whether a human
    actually re-read the skill -- bumping the date is trivially easy and this test
    cannot tell an honest review from a date-bump. It catches drift, not dishonesty.
    """

    STALE_AFTER_DAYS = 60

    # Documentation that *shows* the frontmatter format in an example block is not
    # itself a lifecycle record -- flipping the template's status would teach the
    # wrong value to the next skill author.
    FORMAT_DOCS = {"docs/skills-guide.md", "docs/anti-patterns.md"}

    _LIFECYCLE = re.compile(r"\[STATUS: (\w+)\].*?\[REVIEWED: (\d{4}-\d{2}-\d{2})\]", re.S)

    def _lifecycle_files(self):
        for path in ROOT.rglob("*.md"):
            rel = path.relative_to(ROOT).as_posix()
            if "node_modules" in rel or rel in self.FORMAT_DOCS:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            match = self._LIFECYCLE.search(text)
            if match:
                yield rel, match.group(1), date.fromisoformat(match.group(2))

    def test_no_stale_skill_still_claims_confirmed(self):
        today = date.today()
        stale = [
            f"{rel} claims [STATUS: confirmed] but was last reviewed "
            f"{(today - reviewed).days}d ago (limit {self.STALE_AFTER_DAYS}d)"
            for rel, status, reviewed in self._lifecycle_files()
            if status == "confirmed" and (today - reviewed).days > self.STALE_AFTER_DAYS
        ]
        assert not stale, (
            "Stale skills still advertising themselves as confirmed:\n  "
            + "\n  ".join(sorted(stale))
            + "\n\nPer docs/anti-patterns.md: re-read the skill and bump [REVIEWED:], "
            "or set [STATUS: review]. Do not bump the date without actually looking."
        )

    # The retired name, but ONLY where it is actually in USE as a lifecycle field --
    # i.e. sitting next to [STATUS:] on a frontmatter line.
    _RETIRED_LIFECYCLE = re.compile(r"\[STATUS: \w+\][^\n]*\[VALIDATED: \d{4}-\d{2}-\d{2}\]")

    def test_no_lifecycle_tag_uses_the_old_validated_name(self):
        """[VALIDATED:] was renamed to [REVIEWED:] because the name overclaimed.

        Guards the rename from creeping back in via copy-paste from an old skill.

        Matches the tag in USE (beside [STATUS:] on one line), not every mention of
        the string. The first draft matched any occurrence and immediately failed on
        two innocent files: the paragraph in docs/anti-patterns.md that explains the
        rename, and activeContext.md after the post-commit hook auto-logged a commit
        message describing it. Exempting files one by one would have been whack-a-mole
        -- any changelog, memory file, or docstring may legitimately name a retired
        tag in order to discuss it. Matching the tag's SHAPE is the real invariant:
        prose talks about the tag, frontmatter uses it.
        """
        offenders = sorted(
            rel
            for rel, path in ((p.relative_to(ROOT).as_posix(), p) for p in ROOT.rglob("*.md"))
            if "node_modules" not in rel
            and self._RETIRED_LIFECYCLE.search(path.read_text(encoding="utf-8", errors="ignore"))
        )
        assert not offenders, (
            f"[VALIDATED:] is retired -- use [REVIEWED:] for the lifecycle date, or an "
            f"integrity.md evidence marker if you mean an actual measurement: {offenders}"
        )


# === Evidence citations ===


class TestEvidenceCitations:
    """Docs that cite evidence must cite evidence that exists.

    WHY (audit 2026-07-16): docs/positioning.md's "Current status (honest, not
    aspirational)" section cited two experiment directories as dogfood evidence.
    Neither had ever been committed -- the runs were real, but performed in a
    parallel clone and only their conclusions were backported, so a reader could
    not check the claim against anything. A repo whose stated purpose is making
    claims checkable cannot cite evidence a reader cannot open.
    """

    def test_positioning_evidence_paths_exist(self):
        positioning = ROOT / "docs" / "positioning.md"
        text = positioning.read_text(encoding="utf-8")

        # Backticked repo-relative paths used as evidence citations.
        cited = set(
            re.findall(
                r"`((?:experiments|docs|hooks|rules|null_results)/[\w./-]+)`",
                text,
            )
        )
        assert cited, "positioning.md cites no evidence paths -- pattern likely stale"

        missing = sorted(p for p in cited if not (ROOT / p).exists())
        assert not missing, (
            f"docs/positioning.md cites evidence that does not exist: {missing}. "
            f"Either commit the artifact or stop citing it -- an unopenable citation "
            f"is exactly the unverifiable claim this repo exists to catch."
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

    def test_validation_theater_guard_wired_to_every_supported_tool(self):
        """validation_theater_guard.py's own VALIDATION_TOOL_NAMES must match
        which PostToolUse matchers actually wire it up in settings.json.

        WHY (external audit 2026-07-15/16, AI-02 finding): the code has
        supported tool_name == "Bash" since it was written (see
        VALIDATION_TOOL_NAMES = {"Write", "Bash"} and
        check_bash_for_perfect_scores() in validation_theater_guard.py), but
        an earlier settings.json revision only wired the guard to
        "Skill|Agent" — Bash output with a synthetic F1=1.000 claim would
        never reach the guard despite the code being fully capable of
        catching it. That gap was independently re-verified as already
        closed by this repo's own commit history before this test was
        written, but the fix was never protected against silent regression:
        someone editing settings.json (or a merge conflict resolution) could
        drop a matcher without any test catching it, since the existing
        `test_settings_hook_refs_exist` only checks that referenced hook
        FILES exist, not that a given hook is wired to every tool its own
        code declares support for. This test closes that specific gap.
        """
        import sys

        sys.path.insert(0, str(ROOT / "hooks"))
        from validation_theater_guard import VALIDATION_TOOL_NAMES

        data = json.loads((ROOT / "hooks" / "settings.json").read_text(encoding="utf-8"))
        post_tool_use = data["hooks"]["PostToolUse"]

        wired_matchers: set[str] = set()
        for entry in post_tool_use:
            commands = " ".join(h.get("command", "") for h in entry.get("hooks", []))
            if "validation_theater_guard.py" in commands:
                # WHY split on "|": a matcher like "Skill|Agent" or "Edit|Write"
                # covers multiple tool names in one settings.json entry.
                wired_matchers.update(entry.get("matcher", "").split("|"))

        missing = sorted(VALIDATION_TOOL_NAMES - wired_matchers)
        assert not missing, (
            f"validation_theater_guard.py declares support for {sorted(VALIDATION_TOOL_NAMES)} "
            f"via VALIDATION_TOOL_NAMES, but settings.json PostToolUse only wires it to "
            f"{sorted(wired_matchers)} -- missing: {missing}. A tool_name the code can "
            f"detect synthetic/perfect-score evidence in will silently bypass this guard."
        )


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
        class of shared library. severity_calibrator.py (RFC-003 step 3) is the
        same: a pure-function library, NOT wired as a hook yet -- shadow-mode
        wiring is step 5. It joins the exclusion until then.
        """
        excluded = {"utils", "hook_state", "severity_calibrator"}
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
