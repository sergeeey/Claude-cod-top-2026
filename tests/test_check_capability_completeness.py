"""Tests for scripts/check_capability_completeness.py — the registry
capability-completeness gate added 2026-09-12.

Focuses on the pure decision function (find_incomplete_new_or_modified) with
synthetic in-memory registries -- deliberately NOT mutating the real
skills/registry.yaml here (that was verified by hand, mutation-tested, and
reverted via `git checkout` during development; see this file's sibling PR).
A live-registry smoke test at the bottom confirms the real repo currently
passes the gate as-is.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_capability_completeness import (  # noqa: E402
    find_incomplete_new_or_modified,
    main,
    resolve_base_ref,
)

_CAP = {
    "provides": ["x.y"],
    "risk_tier": "Green",
    "verification_required": [],
}


def _skill(name, maturity="wired", capability=None, **extra):
    d = {"name": name, "kind": "methodology", "maturity": maturity, **extra}
    if capability is not None:
        d["capability"] = capability
    return d


def _registry(*skills):
    return {"core": list(skills)}


class TestFindIncompleteNewOrModified:
    def test_new_wired_skill_without_capability_is_flagged(self):
        old = _registry()
        current = _registry(_skill("new-skill"))
        errors = find_incomplete_new_or_modified(old, current)
        assert len(errors) == 1
        assert "new-skill" in errors[0]
        assert "new" in errors[0]

    def test_new_wired_skill_with_capability_is_not_flagged(self):
        old = _registry()
        current = _registry(_skill("new-skill", capability=_CAP))
        assert find_incomplete_new_or_modified(old, current) == []

    def test_new_described_skill_without_capability_is_exempt(self):
        """`described` maturity means "not yet real" per
        docs/skill-maturity-criteria.md -- must not be forced to declare a
        contract before it is even wired."""
        old = _registry()
        current = _registry(_skill("new-skill", maturity="described"))
        assert find_incomplete_new_or_modified(old, current) == []

    def test_untouched_pre_existing_skill_without_capability_is_never_flagged(self):
        """The whole point of this gate: it must NOT demand a retrofit on the
        ~119 pre-existing skills that never got a capability block."""
        skill = _skill("old-skill")
        old = _registry(skill)
        current = _registry(skill)
        assert find_incomplete_new_or_modified(old, current) == []

    def test_modified_skill_without_capability_is_flagged(self):
        old = _registry(_skill("existing-skill", description="v1"))
        current = _registry(_skill("existing-skill", description="v2"))
        errors = find_incomplete_new_or_modified(old, current)
        assert len(errors) == 1
        assert "existing-skill" in errors[0]
        assert "modified" in errors[0]

    def test_modified_skill_that_gains_capability_is_not_flagged(self):
        old = _registry(_skill("existing-skill", description="v1"))
        current = _registry(_skill("existing-skill", description="v1", capability=_CAP))
        assert find_incomplete_new_or_modified(old, current) == []

    def test_unmodified_capability_present_skill_stays_clean(self):
        skill = _skill("existing-skill", capability=_CAP)
        old = _registry(skill)
        current = _registry(dict(skill))
        assert find_incomplete_new_or_modified(old, current) == []

    def test_multiple_sections_all_scanned(self):
        old = {"core": [], "extensions": [], "community": []}
        current = {
            "core": [_skill("a")],
            "extensions": [_skill("b", capability=_CAP)],
            "community": [_skill("c")],
        }
        errors = find_incomplete_new_or_modified(old, current)
        flagged = {e.split("'")[1] for e in errors}
        assert flagged == {"a", "c"}


class TestResolveBaseRef:
    def test_explicit_ref_wins_when_it_resolves(self):
        assert resolve_base_ref("HEAD") == "HEAD"

    def test_returns_none_when_nothing_resolves(self, monkeypatch):
        import check_capability_completeness as mod

        monkeypatch.setattr(mod, "_run_git", lambda args: None)
        assert resolve_base_ref(None) is None
        assert resolve_base_ref("some-nonexistent-ref-xyz") is None


class TestMainFailsOpenOnUnresolvableBaseRef:
    def test_exits_zero_when_base_ref_cannot_resolve(self, monkeypatch, capsys):
        import check_capability_completeness as mod

        monkeypatch.setattr(mod, "resolve_base_ref", lambda explicit: None)
        rc = main(["--check"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "skipping" in captured.err


class TestLiveRegistrySmoke:
    def test_real_repo_currently_passes_the_gate(self):
        """Not a mutation test (those were done by hand during development and
        reverted via git checkout) -- just confirms the script runs clean
        against the actual current registry.yaml + git history, i.e. that
        this PR's own registry changes (none) don't trip the new gate."""
        result = subprocess.run(
            [sys.executable, "scripts/check_capability_completeness.py", "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
