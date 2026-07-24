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

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Same filesystem definitions as CI's "Verify doc counts match filesystem"
# step and tests/test_structure.py::TestPluginManifests. Keep all three in
# sync if this list ever changes.
_HOOK_EXCLUDED = {"utils.py", "severity_calibrator.py", "hook_state.py"}


def actual_counts() -> dict[str, int]:
    # WHY exactly these 6 keys and no more: tests/test_sync_doc_counts.py's
    # TestAnchorsCoverCIChecks enforces the invariant that EVERY key here is
    # gated by a matching ci.yml `check_pattern` (the legacy bash loop). The
    # `events` dimension (added 2026-07-24) is gated by a DIFFERENT path -- the
    # `sync_doc_counts.py --check` CI step over the anchors -- not that bash
    # loop, so it is merged in at the main() call site (see event_count()),
    # deliberately NOT added here, to keep that invariant true.
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


def event_count() -> int:
    """Number of wired event types = top-level keys under "hooks" in
    settings.json. Filesystem-authoritative, same as actual_counts(), but kept
    separate (see actual_counts() docstring). Added 2026-07-24: an external
    audit found "25 events" hand-copied into README/CITATION/AGENTS/
    architecture.md/marketplace.json while settings.json actually had 24 -- and
    the literal "25" was even FROZEN INTO two of this script's own anchor
    patterns, so the gate was pinning the wrong number instead of checking it.
    """
    settings = REPO / "hooks" / "settings.json"
    if not settings.exists():
        return 0  # minimal test fixtures omit it; real repo always has it
    return len(json.loads(settings.read_text(encoding="utf-8")).get("hooks", {}))


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
    # README.md section header event count (audit 2026-07-24: said "25 Events",
    # settings.json has 24). Separate anchor from the "## N Hooks" one above
    # because they target different numbers on the same line.
    ("README.md", r"(Hooks — )(\d+)( Events)", (None, "events", None)),
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
        r"(\d+)( hooks across )(\d+)( event types)",
        ("hooks", None, "events", None),
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
    # .claude-plugin/marketplace.json (the "25" was hardcoded in this anchor's
    # own literal too -- now a real numeric group tied to the events count)
    (
        ".claude-plugin/marketplace.json",
        r"(\d+)( hooks across )(\d+)( events, )(\d+)"
        r"( agents \+ 3 teams, )(\d+)( skills, 3 MCP profiles)",
        ("hooks", None, "events", None, "agents", None, "skills", None),
    ),
    # root marketplace.json (the 3rd, easy-to-forget copy — caught by
    # test_structure.py this session after a hand-sync missed it)
    (
        "marketplace.json",
        r"(\d+)( hooks, )(\d+)( agents, )(\d+)( skills, )(\d+)( rules)",
        ("hooks", None, "agents", None, "skills", None, "rules", None),
    ),
    # CITATION.cff -- ADDED 2026-07-24 (external audit): this file was NEVER
    # gated and had drifted furthest of all (89 hooks / 25 events / 125 skills
    # / 14 rules, vs real 95/24/128/15). Ungated = guaranteed drift. Its
    # test/coverage numbers were deliberately REMOVED from the abstract (not
    # gated here) because those are CI-variant, same reason this script leaves
    # README's test/coverage badges to sync_readme_from_ci.py -- a citation
    # abstract does not need an exact, drift-prone test count.
    # WHY \s+ between "agents" and "+ 3 teams": CITATION.cff is a YAML folded
    # (`>-`) block, so the abstract wraps mid-sentence with a real newline +
    # 2-space indent right there. A literal single space would never match.
    # The \s+ group is a None-passthrough, so the original wrapping whitespace
    # is re-emitted unchanged.
    (
        "CITATION.cff",
        r"(Includes )(\d+)( hooks across )(\d+)( event types, )(\d+)"
        r"( agents\s+\+ 3 teams, )(\d+)( skills, )(\d+)( rule files)",
        (None, "hooks", None, "events", None, "agents", None, "skills", None, "rules", None),
    ),
    # AGENTS.md -- ADDED 2026-07-24 (external audit): stale project-structure
    # block (49 hooks / 27 events / 14 agents / 32 skills, from 2026-04-26) that
    # CI never checked. Its frozen "1093 tests passing as of DATE" clause was
    # removed rather than gated (CI-variant, and a dev-command doc does not need
    # a pinned test count).
    (
        "AGENTS.md",
        r"(hooks/\s+)(\d+)( Python hooks \+ shared libs \()(\d+)( events in settings\.json\))",
        (None, "hooks", None, "events", None),
    ),
    ("AGENTS.md", r"(agents/\s+)(\d+)( agent definitions)", (None, "agents", None)),
    (
        "AGENTS.md",
        r"(skills/\s+)(\d+)( skills — core/ \()(\d+)(\) \+ extensions/ \()(\d+)(\))",
        (None, "skills", None, "core_skills", None, "ext_skills", None),
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
    # WHY merged here, not inside actual_counts(): keeps that function's key set
    # equal to the ci.yml-bash-loop-gated kinds (test invariant), while still
    # letting `events`-referencing anchors resolve `actual["events"]`.
    actual["events"] = event_count()
    print(
        f"[sync-doc-counts] filesystem: {actual['hooks']} hooks, "
        f"{actual['agents']} agents, {actual['skills']} skills"
    )

    by_file: dict[str, str] = {}
    errors: list[str] = []
    any_drift = False

    for rel_path, pattern, kinds in _ANCHORS:
        if rel_path not in by_file:
            # WHY newline="": disables universal-newline translation on both
            # read and write (see the write_text call below). Without it,
            # Path.write_text() on Windows translates every "\n" in the string
            # to os.linesep ("\r\n") when writing -- silently flipping an
            # ENTIRE file from LF to CRLF even though .gitattributes mandates
            # `*.md text eol=lf` / `*.json text eol=lf` for every file this
            # script touches. Found live (2026-07-19): a bare read+write_text
            # roundtrip on README.md converted all 594 LF line endings to
            # CRLF. Git's own attribute-based normalization likely fixes the
            # STORED blob on the next `git add`/commit, but that's a fragile
            # thing to depend on -- write the correct bytes in the first
            # place instead of relying on git to clean up afterward.
            #
            # WHY Path.open(...).read() instead of Path.read_text(newline=""):
            # found live via CI mypy on Python 3.11 (2026-07-19) -- read_text()
            # only gained a `newline` parameter in Python 3.13; this repo's CI
            # matrix runs 3.11/3.12, where passing it raises TypeError at
            # runtime, not just a mypy complaint. write_text(newline=...) has
            # been valid since Python 3.10, so only the read side needed this
            # workaround. Path.open() forwards newline to the builtin open(),
            # which has supported it on every Python version this repo targets.
            with (REPO / rel_path).open(encoding="utf-8", newline="") as f:
                by_file[rel_path] = f.read()
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
        (REPO / rel_path).write_text(text, encoding="utf-8", newline="")
    print("[sync-doc-counts] updated files to match the filesystem.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
