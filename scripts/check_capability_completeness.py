#!/usr/bin/env python3
"""Registry capability-completeness gate — regression-only, not a retrofit demand.

WHY this exists (P0-adjacent item of the 2026-09-12 routing-telemetry session,
from comparing this repo's `skills/registry.yaml` `capability:` contract
against an external "capability contract" proposal): the contract schema
already exists (architecture/capability.schema.json) and is already validated
for every skill THAT HAS ONE (scripts/check_architecture.py's
gate_capability_schema, every CI run) -- but nothing stops coverage from
staying frozen at its current ~15/135 skills forever, because nothing
requires a newly-added or newly-touched skill to declare a contract at all.

The schema's own docstring is explicit that a blanket requirement across all
135 existing skills would be wrong ("adoption is evolutionary, not
big-bang") -- hand-rewriting 120+ pre-existing entries just to satisfy a new
gate is exactly the kind of busywork this repo's own Structure-Bias Guard and
"Using Wheels First" conventions warn against. So this gate is deliberately
REGRESSION-ONLY: it diffs the registry against a base ref and only requires a
`capability:` block on a skill that is NEW in this diff, or whose entry was
MODIFIED in this diff, and whose `maturity` is `wired`/`dogfooded`/
`benchmarked` (i.e. an actually-used skill per docs/skill-maturity-criteria.md
-- `described` skills are explicitly "not yet real" and exempted). Untouched
pre-existing skills, however incomplete, are never flagged.

Once a block exists, its own field-level correctness is already covered by
check_architecture.py's gate_capability_schema -- this script does not
duplicate that validation, only decides WHEN a block must exist at all.

Base ref resolution failure (no git history, shallow clone, no origin/main)
fails OPEN (prints a warning, exits 0) rather than blocking unrelated PRs on
an infrastructure problem this brand-new gate cannot itself fix -- matching
this repo's own Substrate Gate discipline (falsification-ladder.md Step 2a):
"the test could not run" must never be recorded as if it were a real failure.

KNOWN SCOPE LIMIT (skeptic-reviewed, 2026-09-12, not fixed here -- a
different concern from this gate's own job): `find_incomplete_new_or_modified`
compares skills by NAME via a dict built from `iter_skills()`, which itself
does not deduplicate. Nothing in this repo currently gates skill-name
uniqueness at all (checked: no such test in tests/test_structure.py or
scripts/check_architecture.py) -- a byte-identical duplicate entry added
under a second section, or the same content moved between sections, can
slip past THIS gate's new-vs-modified diff because the old/current dicts
compare equal. Fixing that would mean adding registry-wide name-uniqueness
enforcement, which is a separate, pre-existing gap this gate inherits rather
than introduces -- flagged here rather than silently left undocumented.

Usage:
    python scripts/check_capability_completeness.py            # human report, exit 0/1
    python scripts/check_capability_completeness.py --check    # CI mode, quiet on success
    python scripts/check_capability_completeness.py --base-ref origin/main
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - PyYAML is a pinned CI dep
    print("ERROR: PyYAML is required (pip install -r requirements.txt)", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_architecture import iter_skills  # noqa: E402

REGISTRY = ROOT / "skills" / "registry.yaml"

# Maturities considered "actually used" per docs/skill-maturity-criteria.md --
# `described` explicitly means "not yet real" and is exempt from this gate.
_REAL_MATURITIES = {"wired", "dogfooded", "benchmarked"}

_BASE_REF_CANDIDATES = ["origin/main", "main"]


def _run_git(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def resolve_base_ref(explicit: str | None) -> str | None:
    """Return the first git ref that actually resolves, or None if none do."""
    candidates = [explicit] if explicit else _BASE_REF_CANDIDATES
    for ref in candidates:
        if ref and _run_git(["rev-parse", "--verify", f"{ref}^{{commit}}"]) is not None:
            return ref
    return None


def load_registry_at_ref(ref: str) -> dict[str, Any] | None:
    content = _run_git(["show", f"{ref}:skills/registry.yaml"])
    if content is None:
        return None
    try:
        loaded: dict[str, Any] | None = yaml.safe_load(content)
    except yaml.YAMLError:
        return None
    return loaded


def load_current_registry() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return loaded


def find_incomplete_new_or_modified(
    old_registry: dict[str, Any], current_registry: dict[str, Any]
) -> list[str]:
    old_by_name = {s["name"]: s for s in iter_skills(old_registry)}
    errors: list[str] = []

    for skill in iter_skills(current_registry):
        name = skill["name"]
        maturity = skill.get("maturity")
        if maturity not in _REAL_MATURITIES:
            continue

        old_skill = old_by_name.get(name)
        is_new = old_skill is None
        is_modified = old_skill is not None and old_skill != skill

        if not (is_new or is_modified):
            continue

        if "capability" not in skill:
            reason = "new" if is_new else "modified"
            errors.append(
                f"skill '{name}' ({reason}, maturity={maturity}) has no `capability:` block -- "
                f"see architecture/capability.schema.json for the required shape"
            )

    return errors


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="CI mode, quiet on success")
    parser.add_argument("--base-ref", default=None, help="git ref to diff against")
    args = parser.parse_args(argv)

    base_ref = resolve_base_ref(args.base_ref)
    if base_ref is None:
        print(
            "[check-capability-completeness] no resolvable base ref "
            f"(tried: {args.base_ref or ', '.join(_BASE_REF_CANDIDATES)}) -- "
            "skipping (fail-open, infra gap not a registry defect)",
            file=sys.stderr,
        )
        return 0

    old_registry = load_registry_at_ref(base_ref)
    if old_registry is None:
        print(
            f"[check-capability-completeness] could not read skills/registry.yaml at "
            f"'{base_ref}' -- skipping (fail-open)",
            file=sys.stderr,
        )
        return 0

    current_registry = load_current_registry()
    errors = find_incomplete_new_or_modified(old_registry, current_registry)

    if errors:
        print("Capability completeness: FAIL", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if not args.check:
        print(f"Capability completeness: OK (diffed against {base_ref})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
