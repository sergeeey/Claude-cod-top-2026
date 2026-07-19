#!/usr/bin/env python3
"""Sync hooks/agents/skills/rules count literals across the ~5 CI-gated
metadata files from the filesystem-authoritative source — never by hand.

WHY (HS-02, P1 hotspot in docs/architecture-coupling/06-hotspots.md; recurring
count-drift with 7+ historical "sync count" fix commits; this session alone
caught a 3rd-file miss (root marketplace.json) that the existing verify-only
test (tests/test_structure.py) had to flag after the fact): the counts are
hand-copied prose/JSON literals with no single source of truth. This script
IS that source of truth — the same filesystem definitions CI's own
"Verify doc counts match filesystem" step, its separate check_pattern/
check_meta loop (.github/workflows/ci.yml, ~17 calls), and test_structure.py's
TestPluginManifests all use — and rewrites the known anchor occurrences across
5 files to match, instead of catching drift only after a human forgot one.

WHY 18 anchors, not the original ~13 (reviewer finding, 2026-07-19): the first
version of this script covered only the "Verify doc counts match filesystem"
step's 3 numbers and missed 5 more real total-count occurrences (a README
section header, 4 file-tree lines for agents/rules/core-skills/ext-skills)
that ci.yml's separate check_pattern/check_meta loop ALSO gates -- the exact
bug class this script exists to kill, resurfacing through its own
incompleteness. tests/test_sync_doc_counts.py's TestAnchorsCoverCIChecks
cross-references every check_pattern/check_meta label in ci.yml against
_ANCHORS so this specific gap class cannot silently recur.

Deliberately NOT a blanket "replace any number before the word hooks/agents/
skills" regex: README.md alone has 4 numbers that use those words but are NOT
a total ci.yml gates (e.g. "4 agents with persistent memory", "39 more hooks",
architecture.md's unrelated "8 skills" token-cost example). Each anchor below
is scoped with enough literal context that it can only match the ONE real
total-count occurrence it targets — verified by hand against the live files
before being encoded here (2026-07-19).

Does NOT touch: the 14 frozen docs/ historical/audit-snapshot mentions (they
are point-in-time records; rewriting them would corrupt history, not fix
drift) or README's test/coverage badges (scripts/sync_readme_from_ci.py's
job — different data source, since local pytest count differs from CI's by
platform-dependent tests; hooks/agents/skills counts have no such variance,
so THIS script reads the local filesystem directly, no CI round-trip needed).

Usage:
    python scripts/sync_doc_counts.py            # read filesystem, update files
    python scripts/sync_doc_counts.py --check     # report drift, write nothing (exit 1 if drift)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Same filesystem definitions as CI's "Verify doc counts match filesystem"
# step and tests/test_structure.py::TestPluginManifests. Keep all three in
# sync if this list ever changes.
_HOOK_EXCLUDED = {"utils.py", "severity_calibrator.py", "hook_state.py"}


def actual_counts() -> dict[str, int]:
    hooks = len([p for p in (REPO / "hooks").glob("*.py") if p.name not in _HOOK_EXCLUDED])
    agents = len([p for p in (REPO / "agents").glob("*.md") if p.name != "CLAUDE.md"])
    skills = len(list(REPO.glob("skills/**/SKILL.md")))
    rules = len(list((REPO / "rules").glob("*.md")))
    core_skills = len([p for p in (REPO / "skills" / "core").iterdir() if p.is_dir()])
    ext_skills = len([p for p in (REPO / "skills" / "extensions").iterdir() if p.is_dir()])
    return {
        "hooks": hooks,
        "agents": agents,
        "skills": skills,
        "rules": rules,
        "core_skills": core_skills,
        "ext_skills": ext_skills,
    }


# Each entry: (file relative to REPO, regex pattern, kinds).
# `kinds[i]` names which `actual_counts()` key capture-group (i+1) represents;
# `None` marks a literal passthrough group (re-emitted unchanged, but still
# part of the match so the anchor stays precise). Groups must alternate
# literal/numeric exactly as the pattern's parenthesized groups do.
_ANCHORS: list[tuple[str, str, tuple[str | None, ...]]] = [
    # README.md
    ("README.md", r"(badge/hooks-)(\d+)(_guards)", (None, "hooks", None)),
    ("README.md", r"(badge/agents-)(\d+)(_%2B_3_teams)", (None, "agents", None)),
    (
        "README.md",
        r"(Backed by )(\d+)( hooks · )(\d+)( agents \+ 3 teams · )",
        (None, "hooks", None, "agents", None),
    ),
    (
        "README.md",
        r"(\d+)( agents \+ 3 squads · )(\d+)( skills · )(\d+)( hooks · ~10 MB)",
        ("agents", None, "skills", None, "hooks", None),
    ),
    (
        "README.md",
        r"(\+ )(\d+)( hooks \+ )(\d+)( agents \+ all )(\d+)( skills)",
        (None, "hooks", None, "agents", None, "skills", None),
    ),
    (
        "README.md",
        r"(├── hooks/\s+)(\d+)( hooks \+ utils\.py)",
        (None, "hooks", None),
    ),
    ("README.md", r"(All )(\d+)( hooks with examples)", (None, "hooks", None)),
    ("README.md", r"(badge/)(\d+)(_hooks-always_on)", (None, "hooks", None)),
    ("README.md", r'(alt=")(\d+)( hooks always on")', (None, "hooks", None)),
    # README.md -- found via reviewer cross-check against .github/workflows/
    # ci.yml's full check_pattern/check_meta call list (2026-07-19): the
    # first version of this script only covered the "Verify doc counts match
    # filesystem" step's 3 numbers, missing 5 more real total-count
    # occurrences that ci.yml's separate check_pattern/check_meta loop (17
    # calls) ALSO gates -- the exact bug class this script exists to kill,
    # resurfacing through the tool's own incompleteness.
    ("README.md", r"(## )(\d+)( Hooks)", (None, "hooks", None)),
    (
        "README.md",
        r"(agents/\s+)(\d+)( active \+ 3 teams)",
        (None, "agents", None),
    ),
    ("README.md", r"(rules/\s+)(\d+)( modular rules)", (None, "rules", None)),
    (
        "README.md",
        r"(core/\s+)(\d+)( universal skills)",
        (None, "core_skills", None),
    ),
    (
        "README.md",
        r"(extensions/\s+)(\d+)( domain skills)",
        (None, "ext_skills", None),
    ),
    # docs/architecture.md
    (
        "docs/architecture.md",
        r"(\d+)( agents \(\+ 3 teams\) cover:)",
        ("agents", None),
    ),
    (
        "docs/architecture.md",
        r"(\d+)( hooks across 25 event types)",
        ("hooks", None),
    ),
    # .claude-plugin/plugin.json -- "14 rules" is now a real numeric group
    # (tied to the "rules" key), not a hardcoded literal: a literal would
    # have made this anchor silently stop matching ("anchor not found") the
    # moment rules/ actually changed, instead of syncing correctly.
    (
        ".claude-plugin/plugin.json",
        r"(\d+)( hooks · )(\d+)( agents · )(\d+)( skills · )(\d+)( rules)",
        ("hooks", None, "agents", None, "skills", None, "rules", None),
    ),
    # .claude-plugin/marketplace.json
    (
        ".claude-plugin/marketplace.json",
        r"(\d+)( hooks across 25 events, )(\d+)"
        r"( agents \+ 3 teams, )(\d+)( skills, 3 MCP profiles)",
        ("hooks", None, "agents", None, "skills", None),
    ),
    # root marketplace.json (the 3rd, easy-to-forget copy — caught by
    # test_structure.py this session after a hand-sync missed it)
    (
        "marketplace.json",
        r"(\d+)( hooks, )(\d+)( agents, )(\d+)( skills, )(\d+)( rules)",
        ("hooks", None, "agents", None, "skills", None, "rules", None),
    ),
]


def _apply_anchor(
    text: str, pattern: str, kinds: tuple[str | None, ...], actual: dict[str, int]
) -> tuple[str, bool, str | None]:
    """Return (new_text, changed, error). error is set if the anchor's group
    count doesn't match `kinds` (a template bug, not a drift finding) or the
    anchor isn't found at all (the anchor text itself drifted — needs a human,
    not a silent no-op)."""
    compiled = re.compile(pattern)
    match = compiled.search(text)
    if match is None:
        return text, False, f"anchor not found: {pattern!r}"
    if len(match.groups()) != len(kinds):
        return text, False, f"kinds length mismatch for {pattern!r}"

    changed = False

    def repl(m: re.Match) -> str:
        nonlocal changed
        parts = []
        for i, kind in enumerate(kinds, start=1):
            g = m.group(i)
            if kind is None:
                parts.append(g)
                continue
            new_val = str(actual[kind])
            if g != new_val:
                changed = True
            parts.append(new_val)
        return "".join(parts)

    new_text = compiled.sub(repl, text, count=1)
    return new_text, changed, None


def main() -> int:
    check_only = "--check" in sys.argv
    actual = actual_counts()
    print(
        f"[sync-doc-counts] filesystem: {actual['hooks']} hooks, "
        f"{actual['agents']} agents, {actual['skills']} skills"
    )

    by_file: dict[str, str] = {}
    errors: list[str] = []
    any_drift = False

    for rel_path, pattern, kinds in _ANCHORS:
        if rel_path not in by_file:
            by_file[rel_path] = (REPO / rel_path).read_text(encoding="utf-8")
        text = by_file[rel_path]
        new_text, changed, error = _apply_anchor(text, pattern, kinds, actual)
        if error:
            errors.append(f"{rel_path}: {error}")
            continue
        if changed:
            any_drift = True
            print(f"[sync-doc-counts] drift in {rel_path}: {pattern}")
        by_file[rel_path] = new_text

    if errors:
        for e in errors:
            print(f"[sync-doc-counts] ERROR: {e}", file=sys.stderr)
        return 1  # a template/anchor bug is not a drift finding -- always fail

    if not any_drift:
        print("[sync-doc-counts] all files already match the filesystem — nothing to do.")
        return 0

    if check_only:
        print("[sync-doc-counts] DRIFT detected (run without --check to fix).")
        return 1

    for rel_path, text in by_file.items():
        (REPO / rel_path).write_text(text, encoding="utf-8")
    print("[sync-doc-counts] updated files to match the filesystem.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
