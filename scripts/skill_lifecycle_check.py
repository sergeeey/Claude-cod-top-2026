"""Skill lifecycle regression check.

WHY this exists (2026-09-06): skills/registry.yaml's maturity ladder and
skill-audit (personal skill) both grade a SKILL SET (promote/keep/merge/
delete), and skill-self-update only edits a skill FROM feedback. None of
them catch a skill silently losing a hard-won behavioral rule during an
edit -- documented as a real, repeated failure mode in this project's own
skill changelogs (e.g. boyko-scientific-consortium v1.1/v1.2 fixed the exact
same class of regression twice: a mandatory instruction present in prose
was silently not followed, because nothing re-checked the file itself after
each edit). This is the "test the skill, not just the code inside it" gap
named by mattpocock/skills' lifecycle.test.js concept -- reimplemented here
from the concept only (that repo's own test source was never fetched by
this project's graphify pass; see the fixture's own README for that
provenance note).

A skill is a markdown instruction file, not code -- so "testing" it here
means: does its current text still contain the exact phrases a past
regression proved must survive edits? This is a content-regression check,
not a claim that the check verifies the skill's real-world behavior.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "skills" / "lifecycle_tests"


@dataclass
class RequiredString:
    text: str
    why: str = ""


@dataclass
class LifecycleFixture:
    skill: str
    skill_file: str
    required_strings: list[RequiredString] = field(default_factory=list)


@dataclass
class CheckResult:
    skill: str
    status: str  # PASS / FAIL / SKIPPED
    missing: list[RequiredString] = field(default_factory=list)
    reason: str = ""


def load_fixture(path: Path) -> LifecycleFixture:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    required = [RequiredString(**r) for r in data.get("required_strings", [])]
    return LifecycleFixture(
        skill=data["skill"], skill_file=data["skill_file"], required_strings=required
    )


def check_fixture(fixture: LifecycleFixture) -> CheckResult:
    skill_path = Path(fixture.skill_file)
    if not skill_path.exists():
        # WHY: fixtures may point at a personal, machine-local skill (outside
        # this repo, e.g. under C:/Users/<user>/.claude/skills/) -- same
        # precedent as check_global_hooks.py hardcoding a personal path.
        # On CI (Linux) or a different machine that path legitimately does
        # not exist. Absence of the file is not evidence the skill regressed.
        return CheckResult(
            skill=fixture.skill,
            status="SKIPPED",
            reason=f"skill_file not found on this machine: {fixture.skill_file}",
        )

    content = skill_path.read_text(encoding="utf-8", errors="ignore")
    missing = [r for r in fixture.required_strings if r.text not in content]
    if missing:
        return CheckResult(skill=fixture.skill, status="FAIL", missing=missing)
    return CheckResult(skill=fixture.skill, status="PASS")


def run_all(fixtures_dir: Path = FIXTURES_DIR) -> list[CheckResult]:
    results: list[CheckResult] = []
    if not fixtures_dir.exists():
        return results
    for path in sorted(fixtures_dir.glob("*.yaml")):
        fixture = load_fixture(path)
        results.append(check_fixture(fixture))
    return results


def main() -> int:
    results = run_all()
    if not results:
        print("[skill-lifecycle] no fixtures found under", FIXTURES_DIR)
        return 0

    exit_code = 0
    for r in results:
        if r.status == "PASS":
            print(f"[PASS] {r.skill}")
        elif r.status == "SKIPPED":
            print(f"[SKIPPED] {r.skill} — {r.reason}")
        else:
            exit_code = 1
            print(f"[FAIL] {r.skill} — {len(r.missing)} required string(s) missing:")
            for m in r.missing:
                print(f"    - {m.text!r}")
                if m.why:
                    print(f"      (why this matters: {m.why})")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
