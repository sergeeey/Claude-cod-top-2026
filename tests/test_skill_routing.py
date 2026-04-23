"""
Eval tests for critical skill routing logic.

WHY: routing-policy, tdd-workflow, and security-audit trigger constantly but
have no automated tests for edge cases — a misroute breaks the entire pipeline.
These tests verify signal detection, priority ordering, and skill file integrity.
"""

import re
from pathlib import Path

import pytest

# WHY: prefer repo skills/ dir for CI (no install needed); fall back to
# ~/.claude/skills/ for local runs where the config is installed.
# Repo structure: skills/core/<name>/ and skills/extensions/<name>/
# Installed structure: ~/.claude/skills/<name>/
_REPO_ROOT = Path(__file__).parent.parent / "skills"


def _find_skill_dir() -> Path:
    """Return the base dir where <skill>/SKILL.md is found."""
    # Check if installed skills exist
    installed = Path.home() / ".claude" / "skills"
    if (installed / "routing-policy" / "SKILL.md").exists():
        return installed
    # Repo: skills are nested under core/ or extensions/
    for sub in ("core", "extensions"):
        candidate = _REPO_ROOT / sub
        if (candidate / "routing-policy" / "SKILL.md").exists():
            return candidate
    return installed  # fallback


SKILLS_DIR = _find_skill_dir()

# ── Signal patterns extracted from routing-policy SKILL.md ──────────────────
# WHY: priority order matters — security > tdd > debug > multi > research.
# Higher-risk routes must win when multiple signals appear in one prompt.

SIGNALS: dict[str, str] = {
    # WHY: sql alone (not "sql injection") covers "sql queries", "sql error" etc.
    # WHY: \.env without \b — dot breaks word boundary, use lookahead instead.
    "security": r"\b(audit|security|pii|sql|auth|payment)\b|\.env\b",
    "tdd": r"\b(test|tests|coverage|tdd|cover\s+with\s+tests|spec)\b",
    # WHY: crashes/crashed need explicit plural — \bcrash\b misses "app crashes".
    "debug": r"\b(crash(?:es)?|error|not\s+working|bug|fails?|broken|debug|exception|traceback)\b",
    "multi": r"\b(refactor|new\s+feature|migration|redesign|restructure)\b",
    "research": r"\b(what\s+is|how\s+does|where\s+is|why|explain|find|search)\b",
}

PRIORITY = ["security", "tdd", "debug", "multi", "research"]


def classify(prompt: str) -> str:
    """Keyword-based classifier matching routing-policy signal matrix.

    Returns the highest-priority route type, or 'simple_change' (Type 2 default).
    """
    p = prompt.lower()
    for task_type in PRIORITY:
        if re.search(SIGNALS[task_type], p):
            return task_type
    return "simple_change"


# ── routing-policy: happy path ────────────────────────────────────────────────


class TestRoutingPolicyHappyPath:
    def test_research_what_is(self):
        assert classify("what is this function") == "research"

    def test_research_explain(self):
        assert classify("explain how the hook system works") == "research"

    def test_research_find(self):
        assert classify("find where session_save is called") == "research"

    def test_debug_error(self):
        # WHY: "auth.py" contains "auth" → triggers security (correct). Use neutral prompt.
        assert classify("the import error needs fixing") == "debug"

    def test_debug_not_working(self):
        assert classify("the import is not working") == "debug"

    def test_debug_crash(self):
        assert classify("app crashes on startup") == "debug"

    def test_security_audit(self):
        assert classify("audit the login endpoint for security") == "security"

    def test_security_sql(self):
        assert classify("check for sql injection in user query") == "security"

    def test_security_env(self):
        assert classify("review .env handling in config") == "security"

    def test_security_pii(self):
        assert classify("make sure PII is not logged") == "security"

    def test_tdd_write_tests(self):
        assert classify("write tests for the parser module") == "tdd"

    def test_tdd_coverage(self):
        assert classify("increase coverage for hooks") == "tdd"

    def test_tdd_explicit(self):
        assert classify("use TDD to add the feature") == "tdd"

    def test_multi_refactor(self):
        assert classify("refactor the entire hook system") == "multi"

    def test_multi_new_feature(self):
        assert classify("add new feature for rate limiting") == "multi"

    def test_simple_default(self):
        assert classify("update the version number") == "simple_change"

    def test_simple_ambiguous_short(self):
        assert classify("help me") == "simple_change"

    def test_simple_bump_version(self):
        assert classify("bump version to 4.0") == "simple_change"


# ── routing-policy: priority ordering (edge cases) ────────────────────────────


class TestRoutingPolicyPriority:
    """Security > TDD > Debug > Multi > Research — higher risk wins."""

    def test_security_beats_tdd(self):
        # "write tests for auth payments" → security wins over tdd
        assert classify("write tests for auth payments") == "security"

    def test_security_beats_debug(self):
        # "debug the security audit" → security wins
        assert classify("debug the security audit") == "security"

    def test_debug_beats_research(self):
        # "why does it crash" → debug wins over research
        assert classify("why does it crash") == "debug"

    def test_debug_beats_multi(self):
        # "refactor crashes the app" → debug wins over multi
        assert classify("refactor crashes the app") == "debug"

    def test_tdd_beats_research(self):
        # "find how to write tests" → tdd wins
        assert classify("find how to write tests") == "tdd"

    def test_tdd_beats_multi(self):
        # "refactor with tests" → tdd wins
        assert classify("refactor with tests") == "tdd"

    def test_multi_beats_research(self):
        # "find how to refactor" → multi wins
        assert classify("find how to refactor") == "multi"

    def test_failing_test_is_tdd(self):
        # WHY: routing-policy lists TDD before debug in priority.
        # "failing" has fail signal, "test" has tdd signal → tdd wins (higher priority).
        assert classify("fix the failing test") == "tdd"

    def test_security_sql_and_tests(self):
        # "write tests for sql queries" → security (sql) beats tdd
        assert classify("write tests for sql queries") == "security"


# ── tdd-workflow: skill file integrity ────────────────────────────────────────


class TestTddWorkflowSkillFile:
    """Verify tdd-workflow SKILL.md defines the Iron Law and step process."""

    @pytest.fixture(scope="class")
    def content(self) -> str:
        p = SKILLS_DIR / "tdd-workflow" / "SKILL.md"
        assert p.exists(), "tdd-workflow/SKILL.md not found in ~/.claude/skills/"
        return p.read_text(encoding="utf-8").lower()

    def test_red_green_refactor_present(self, content):
        assert "red" in content
        assert "green" in content
        assert "refactor" in content

    def test_iron_law_or_failing_test(self, content):
        assert "failing test" in content or "iron law" in content

    def test_step_process_defined(self, content):
        assert "step 1" in content or "step1" in content

    def test_has_use_keyword(self, content):
        # skill describes when to use it (EN or RU)
        assert "use" in content or "использовать" in content or "always" in content


# ── security-audit: skill file integrity ─────────────────────────────────────


class TestSecurityAuditSkillFile:
    """Verify security-audit SKILL.md covers all required security domains."""

    @pytest.fixture(scope="class")
    def content(self) -> str:
        p = SKILLS_DIR / "security-audit" / "SKILL.md"
        assert p.exists(), "security-audit/SKILL.md not found in ~/.claude/skills/"
        return p.read_text(encoding="utf-8").lower()

    def test_pii_covered(self, content):
        assert "pii" in content

    def test_sql_injection_covered(self, content):
        assert "sql" in content

    def test_auth_covered(self, content):
        assert "auth" in content

    def test_secrets_env_covered(self, content):
        assert ".env" in content or "secret" in content

    def test_payments_covered(self, content):
        assert "payment" in content or "financial" in content

    def test_checklist_present(self, content):
        assert "checklist" in content or "[ ]" in content


# ── routing-policy: skill file integrity ─────────────────────────────────────


class TestRoutingPolicySkillFile:
    """Verify routing-policy SKILL.md defines all 6 route types and hard guards."""

    @pytest.fixture(scope="class")
    def content(self) -> str:
        p = SKILLS_DIR / "routing-policy" / "SKILL.md"
        assert p.exists(), "routing-policy/SKILL.md not found in ~/.claude/skills/"
        return p.read_text(encoding="utf-8").lower()

    def test_six_route_types_present(self, content):
        for i in range(1, 7):
            assert f"type {i}" in content, f"Type {i} missing from routing matrix"

    def test_hard_guards_present(self, content):
        assert "read before edit" in content
        assert "local before mcp" in content
        assert "plan before" in content

    def test_priority_ordering_documented(self, content):
        assert "security" in content
        assert "tdd" in content
        assert "debug" in content

    def test_complexity_hierarchy_present(self, content):
        # task types (1/2/3) define the routing hierarchy
        assert "type 1" in content or "type1" in content or "research" in content
        assert "type 2" in content or "type2" in content or "type 3" in content


# ── all critical skills: frontmatter integrity ───────────────────────────────

CRITICAL_SKILLS = [
    "routing-policy/SKILL.md",
    "tdd-workflow/SKILL.md",
    "security-audit/SKILL.md",
    "skeptic/SKILL.md",
    "brainstorming/SKILL.md",
]


class TestCriticalSkillFrontmatter:
    """All critical skills must have name + non-empty description."""

    @pytest.mark.parametrize("rel_path", CRITICAL_SKILLS)
    def test_file_exists(self, rel_path):
        assert (SKILLS_DIR / rel_path).exists(), f"Missing skill file: {rel_path}"

    @pytest.mark.parametrize("rel_path", CRITICAL_SKILLS)
    def test_has_name_field(self, rel_path):
        content = (SKILLS_DIR / rel_path).read_text(encoding="utf-8")
        assert "name:" in content, f"No 'name:' in {rel_path}"

    @pytest.mark.parametrize("rel_path", CRITICAL_SKILLS)
    def test_has_description_field(self, rel_path):
        content = (SKILLS_DIR / rel_path).read_text(encoding="utf-8")
        assert "description:" in content, f"No 'description:' in {rel_path}"

    @pytest.mark.parametrize("rel_path", CRITICAL_SKILLS)
    def test_description_not_trivial(self, rel_path):
        content = (SKILLS_DIR / rel_path).read_text(encoding="utf-8")
        lines = content.splitlines()
        idx = next((i for i, ln in enumerate(lines) if "description:" in ln), None)
        assert idx is not None
        desc_block = "\n".join(lines[idx : idx + 6])
        assert len(desc_block.strip()) > 30, f"Description too short in {rel_path}"
