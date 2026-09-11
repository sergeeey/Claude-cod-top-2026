#!/usr/bin/env python3
"""SessionStart hook: warn when the LIVE ~/.claude install has drifted
away from what this repo actually ships -- hooks/ (content + event
wiring), rules/ (content + files that exist only in the personal
install), and agents/ + commands/ + skills/ (content of what is shipped).

WHY (2026-09-01, Tracy strategic pass -> Critical Path item #1): this repo's
own CLAUDE.md documents the gap in prose ("a hook fixed here isn't live
until reinstalled/redeployed... several bugs this project has hit were
exactly this") but nothing ever mechanically checked for it. Confirmed the
same day, concretely: mcp_circuit_breaker.py/mcp_circuit_breaker_post.py
were fixed and merged (PR #296), yet the live ~/.claude/hooks copy on this
machine still ran the buggy version until someone happened to notice by
hand. This hook is the mechanization of that check -- it would have caught
that exact drift at the next session start.

The rules/ half was added 2026-09-09 after a FOURTH rule file in a single
day turned out to exist only in the maintainer's personal ~/.claude/rules/
and never in this repo's rules/ -- i.e. absent from the distribution
entirely (autonomy-budget.md #396, meta-loop.md #398, a
research-methodology.md section #402, then pearl_registry/INDEX.md). Three
had already been caught and shipped one at a time, by hand, by noticing.
Four of one class is the point at which noticing stops being the mechanism.

That estimate was already low by the time this shipped. A FIFTH file of the
same class (rationalizations.md, #401) was found by hand the same day, and
on this check's first real run against the maintainer's own machine it
immediately reported a SIXTH -- artifact-provenance-gates.md, 9.4 KB, live
and load-bearing, never in this repo at all -- plus two content
divergences, one in each direction (estimand-ops.md: repo ahead of the
personal install, i.e. an un-run redeploy; memory-protocol.md: personal
ahead by ~190 lines, i.e. another distribution gap). Those three are
deliberately NOT fixed in the same change that adds the check: one fix per
PR, and a gate whose first output is a real finding is better evidence than
its own unit tests, which were written by the same author as the gate.

The agents/ + commands/ + skills/ half was added 2026-09-11 as the cheap
falsifiable test recorded in docs/artifact-distribution-topology.md (#424)
against building a declarative artifact inventory: if extending the guard
per-kind closes the observed drift class, the inventory is unnecessary. The
prediction said "using its existing rules-tree logic" and that part did not
survive contact -- see find_shipped_artifact_drift's own docstring for the
two measured reasons (the live install is not roughly the shipped tree for
these kinds, and skills are nested in the repo but flat when installed).
Its first run reported 111 divergences on the maintainer's machine, which
is a real un-run redeploy rather than a gate misfiring: 58 of them differ
by three lines or fewer, and commands/ came back clean, as it should have
after #425.

A same-day triage of those divergences (still 2026-09-11) found that 97 of
105 skill-level findings reduced to exactly two mechanically-explainable
causes -- see _strip_generated_fields's own WHY. find_shipped_artifact_drift
now separates those into a third, quieter `enriched` bucket instead of
counting them as real drift; on this machine, after redeploying the 21
skills the triage identified as genuinely stale or repo-ahead, the split is
14 missing / 6 drifted (all six are agents/, a separate, not-yet-triaged
class) / 100 enriched. Before this split, every one of those 100 would have
printed as an undifferentiated "content differs" alongside the 6 that
actually matter -- exactly the "warning nobody reads" failure this repo's
own skeptic-triggers.md names for a check that fires on every session.

It lives here rather than in a second, near-identical hook because it
answers the same question against the same two trees, needs the same
"personal install may simply not exist" no-op, and this repo has already
been burned once by building a near-duplicate gate beside an existing one
(see falsification-ladder.md Step 2b's own correction note).

Scope: only meaningful when the CURRENT working directory IS this repo
(hooks/registry.yaml + skills/registry.yaml both present) -- comparing
hashes only makes sense against the repo that produced the live install.
Silent no-op everywhere else, including a machine where CLAUDE_HOME was
never installed from this repo at all, or where it exists but has no
rules/ directory (a hooks-only or minimal install). A clean CI runner has
no personal install at all: that is the ordinary case, not a failure.

Deliberately NOT a promotion gate: read-only, warns via stdout (the
SessionStart additionalContext channel, matching estimand_guard.py's own
pattern), never blocks, never writes inside the repo. Autonomy Budget:
Green tier (read-only, 0 project files changed) per
.claude/rules/autonomy-budget.md.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

# WHY 8s ceiling, not "as long as it takes": autonomy-budget.md caps every
# SessionStart hook's wall-clock at 8s. Hashing ~100 small .py files is a
# few ms in practice; this is a hard stop against a slow/networked
# CLAUDE_HOME (e.g. a synced drive) turning a cheap check into a stall.
_MAX_FILES = 500


def is_this_repo(root: Path) -> bool:
    return (root / "hooks" / "registry.yaml").is_file() and (
        root / "skills" / "registry.yaml"
    ).is_file()


def resolve_claude_home() -> Path | None:
    env = os.environ.get("CLAUDE_HOME") or os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        candidate = Path(env)
        return candidate if candidate.is_dir() else None
    candidate = Path.home() / ".claude"
    return candidate if candidate.is_dir() else None


def sha256_of(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def find_drift(repo_hooks: Path, live_hooks: Path) -> list[str]:
    """Return relative paths present in BOTH trees whose content differs.

    WHY "present in both" only: a file that exists in the repo but was never
    installed (e.g. a brand-new hook not yet deployed) is an outstanding
    deploy step, not drift -- and a file only in the live tree may be a
    personal, non-repo hook (this repo's own CLAUDE.md documents exactly
    this case for personal-only consumers). Neither is this hook's concern.
    """
    drifted = []
    count = 0
    for repo_file in repo_hooks.rglob("*.py"):
        if "__pycache__" in repo_file.parts:
            continue
        count += 1
        if count > _MAX_FILES:
            break
        rel = repo_file.relative_to(repo_hooks)
        live_file = live_hooks / rel
        if not live_file.is_file():
            continue
        repo_hash = sha256_of(repo_file)
        live_hash = sha256_of(live_file)
        if repo_hash is not None and live_hash is not None and repo_hash != live_hash:
            drifted.append(str(rel))
    return drifted


# WHY `search` (first match), not `findall` (P2 note, reviewer 2026-09-02):
# every command in both settings.json files today is `<interpreter> <one
# hook>.py`, so first-match is exact. If a wrapper-style command that names
# TWO .py files is ever introduced, only the first would be tracked here and
# the second silently dropped from both event-sets -- a blind spot, not a
# false positive. Switch to `findall` at that point; not needed yet.
_HOOK_BASENAME_RE = re.compile(r"([A-Za-z0-9_]+\.py)(?:\s|$)")


def _load_settings(path: Path) -> dict | None:
    try:
        data: dict = json.loads(path.read_text(encoding="utf-8-sig"))
        return data
    except (OSError, json.JSONDecodeError):
        return None


def _event_registrations(settings: dict) -> dict[str, set[str]]:
    """Map each hook script's basename to the set of top-level event names
    (PreToolUse, PostToolUse, PermissionRequest, Stop, ...) it is registered
    under in this settings.json.

    WHY basename, not the full command string: the repo template uses
    `__PYTHON_CMD__ __CLAUDE_HOME__/hooks/<name>.py` placeholders while a
    live install has real, machine-specific interpreter/path strings --
    comparing full commands would report drift on every single hook, every
    time, which is useless. The basename survives both forms.
    """
    result: dict[str, set[str]] = {}
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return result
    for event_name, blocks in hooks.items():
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            for entry in block.get("hooks", []):
                command = entry.get("command", "")
                m = _HOOK_BASENAME_RE.search(command)
                if not m:
                    continue
                basename = m.group(1)
                result.setdefault(basename, set()).add(event_name)
    return result


def find_event_registration_drift(
    repo_settings: Path, live_settings: Path, live_hooks: Path | None = None
) -> list[str]:
    """Return human-readable findings for hooks whose registered EVENT set
    differs between repo and live -- e.g. registered under `PreToolUse` in
    the repo but `PermissionRequest` in live.

    WHY this exists as a check distinct from `find_drift` (content hashing):
    2026-09-02, an independent security audit found `permission_policy.py`
    byte-identical between repo and a stale live copy would have shown zero
    drift by content hash alone -- the actual bug was WIRING, not code: live
    registered it under `PermissionRequest` (which this repo's own SEC-03
    decision, 2026-07-18, established never fires when `Bash(*)` sits in
    `permissions.allow`), while the repo had long since moved it to
    `PreToolUse`/`Bash`. The hook's logic was correct and unchanged; its
    registration silently made that logic dead code for over a month, and
    `find_drift`'s content-hash comparison structurally cannot see this
    class of bug, because the .py file itself never differed. This function
    covers the wiring layer that content hashing does not.
    """
    repo_data = _load_settings(repo_settings)
    live_data = _load_settings(live_settings)
    if repo_data is None or live_data is None:
        return []

    repo_events = _event_registrations(repo_data)
    live_events = _event_registrations(live_data)

    findings = []
    for basename, repo_evset in repo_events.items():
        live_evset = live_events.get(basename)
        if live_evset is None:
            # WHY this branch now splits on whether the FILE exists (2026-09-10):
            # the original `continue` assumed "no live registration" implies "not
            # deployed live", i.e. find_drift's territory. That assumption is
            # false in the one case this whole function exists to catch. A hook
            # can be copied into ~/.claude/hooks/ and simply never added to
            # settings.json -- the file is present and byte-identical, so
            # find_drift correctly reports nothing, and this check skipped it, so
            # NOBODY reported an installed hook that can never fire.
            #
            # Hit live the same day: model_switch_tracker.py was deployed and
            # left unregistered; both checks stayed silent and the hook was dead.
            # Same consequence as the permission_policy incident in this
            # function's own docstring -- correct code, wrong wiring, silently
            # inert -- differing only in "wired to no event" instead of "wired to
            # the wrong one".
            #
            # When the file genuinely is absent live, the original reasoning
            # still holds: that is an un-run redeploy, and find_drift owns it.
            if live_hooks is not None and (live_hooks / basename).is_file():
                findings.append(
                    f"{basename}: deployed live but registered under NO event "
                    f"(repo wires it to {sorted(repo_evset)}) -- installed and dead"
                )
            continue
        if repo_evset != live_evset:
            findings.append(f"{basename}: repo={sorted(repo_evset)} live={sorted(live_evset)}")
    return findings


def _live_rule_files(live_rules: Path) -> list[Path]:
    """Every *.md under the live rules/ tree, dot-directories excluded.

    WHY rglob and not glob: rules/ has one nested directory
    (rules/pearl_registry/), and its INDEX.md is precisely the kind of file
    this check exists to notice -- a flat glob would structurally never see
    the nested case.

    WHY dot-directories are skipped: a live install accumulates runtime junk
    the repo never ships. This machine's own rules/pearl_registry/ had grown
    a .claude/state/ directory from a hook that happened to run with that
    cwd; nothing in there is a rule.

    Backup files need no filter: the personal install's convention is
    `<name>.md.backup.<stamp>` / `<name>.md.bak-<stamp>`, which do not end
    in `.md` and so never match the glob in the first place. Verified
    against the live tree (2026-09-09) rather than assumed.
    """
    out = []
    for path in sorted(live_rules.rglob("*.md")):
        if any(part.startswith(".") for part in path.relative_to(live_rules).parts):
            continue
        out.append(path)
        if len(out) >= _MAX_FILES:
            break
    return out


def _normalized(path: Path) -> str | None:
    """File text with line endings normalized to LF, or None if unreadable.

    WHY read as TEXT and not as bytes, unlike find_drift() above:
    .gitattributes pins `*.md text eol=lf`, so a repo checkout is always LF,
    while a personal rules file edited or copied on Windows can be CRLF or
    -- as pearl_registry/INDEX.md actually was, 21 CR against 23 LF --
    MIXED. Comparing bytes would then report permanent, unfixable drift on
    files whose content is identical, and a check that cries wolf every
    session is a check nobody reads. The normalization is `read_text`'s own
    universal-newline translation, which collapses both `\r\n` and a lone
    `\r` to `\n` before this function returns -- so no explicit `.replace()`
    is needed, and an earlier draft that added one was writing dead code
    (probed, not assumed). tests/test_live_drift_guard.py's
    `test_line_ending_difference_alone_is_not_drift` fails if this is ever
    switched to a byte comparison.

    The .py half deliberately keeps byte comparison: those files are written
    by install.sh from this same repo, so a stray CR there IS real drift.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


_TRIGGERS_FIELD_RE = re.compile(r"^triggers:\s*\[.*\]\s*$\n?", re.MULTILINE)
_BSV_BLOCK_RE = re.compile(r"^<!-- BSV.*?-->\n\n?", re.DOTALL | re.MULTILINE)


def _strip_generated_fields(text: str) -> str:
    """Remove the two known, mechanically-explainable causes of shipped-
    artifact drift before comparing bodies.

    WHY this exists (2026-09-11, same day as find_shipped_artifact_drift
    itself, once its first real run was triaged rather than just read):
    of 105 skills that function reported as "differ in content," 97 turned
    out to have one of exactly two causes, neither a real divergence in the
    skill's actual instructions:

    1. `triggers: [...]` frontmatter -- scripts/add_triggers.py +
       scripts/build_skill_trigger_index.py's own WHY documents this is
       intentionally LIVE-ONLY, feeding hooks/keyword_router.py's index,
       and deliberately never committed (committing it would leak the
       trigger phrases of ~50 personal-only skills into a public repo).
       82 of the 105 had no other difference at all.
    2. A leading `<!-- BSV -- Brief Skill View ... -->` HTML comment --
       present on live copies whose repo version has since dropped the
       BSV-card convention. An ordinary un-run redeploy, not a content
       divergence.

    Without stripping these, find_shipped_artifact_drift's `drifted` bucket
    could not distinguish "this skill's real instructions changed" from
    "this skill has the exact enrichment it is supposed to have" -- every
    session using a well-functioning local install would see the same ~80+
    false alarms, which is precisely the condition under which a warning
    stops being read (this repo's own skeptic-triggers.md names the pattern
    under a different heading: a check that fires constantly gets ignored).

    Kept as a free function, not inlined into compare() below, because
    tests/test_live_drift_guard.py exercises it directly against both known
    causes independently before trusting the combined classification.
    """
    without_triggers = _TRIGGERS_FIELD_RE.sub("", text, count=1)
    return _BSV_BLOCK_RE.sub("", without_triggers, count=1)


def find_rules_drift(repo_rules: Path, live_rules: Path) -> tuple[list[str], list[str]]:
    """Return (missing_from_repo, content_drift) for the two rules/ trees.

    `missing_from_repo` -- a rule that exists in the personal install and has
    no counterpart in this repo. This is the exact failure the function was
    written for: the rule is live and load-bearing for its author, and is
    simply not in the product anyone else installs.

    `content_drift` -- present in both, but the text differs.

    Deliberately does NOT report the third direction (shipped by the repo,
    absent from the live install): that is an un-run redeploy, not a
    distribution gap, and find_drift() above already declines to report the
    same direction for hooks for the same reason. Keeping the two halves
    consistent matters more here than exhaustiveness.
    """
    missing: list[str] = []
    drifted: list[str] = []
    for live_file in _live_rule_files(live_rules):
        rel = live_file.relative_to(live_rules)
        repo_file = repo_rules / rel
        if not repo_file.is_file():
            missing.append(rel.as_posix())
            continue
        live_text = _normalized(live_file)
        repo_text = _normalized(repo_file)
        if live_text is not None and repo_text is not None and live_text != repo_text:
            drifted.append(rel.as_posix())
    return missing, drifted


def find_shipped_artifact_drift(
    repo_root: Path, claude_home: Path
) -> tuple[list[str], list[str], list[str]]:
    """Content drift for the three artifact kinds the repo SHIPS but never checked.

    WHY this is a separate function and not a third call to find_rules_drift
    (measured 2026-09-11 BEFORE any of it was written, because the prediction
    in docs/artifact-distribution-topology.md said "using its existing
    rules-tree logic" and that turned out to be wrong):

    find_rules_drift reports BOTH directions, and its missing-from-repo half
    is the loud one -- correct for rules/, because the live rules tree is
    roughly the shipped tree (21 live against 22 shipped). That premise does
    not hold for these three kinds. The live install accumulates artifacts
    from many sources, not just this repo:

        skills     583 live .md   vs  135 shipped SKILL.md
        agents      66 live .md   vs   16 shipped
        commands    14 live .md   vs    3 shipped

    Reporting "live but not in repo" here would emit roughly 450 findings for
    skills alone, every one of them correct-by-construction and useless. So
    that half is deliberately dropped for these kinds and only content drift
    on artifacts the repo actually ships is reported.

    WHY skills need their own path mapping: the repo nests them as
    skills/{core,extensions}/<name>/SKILL.md while install.sh syncs them FLAT
    to ~/.claude/skills/<name>/SKILL.md. A same-relative-path comparison finds
    no counterpart for any skill and reports a clean tree -- the worst
    possible failure for a drift check, silence that looks like health.

    What it reports on the maintainer's own machine the day it was written:
    agents 6 of 16 drifted, commands 0 of 3 (clean since #425), skills 105 of
    135 -- of which 58 differ by three lines or fewer. Real un-run redeploy,
    mostly small, not noise: the magnitudes were measured rather than assumed
    before deciding to include skills at all.

    Returns (missing_live, drifted, enriched) -- a three-tuple where the
    original two-tuple shape (present through #427/#428/#429) used to stop.
    `enriched` was added 2026-09-11, the same day #427's first real run was
    triaged rather than just read: of 105 "content differs" findings, 97
    turned out to be one of two known, mechanically-explainable causes (see
    _strip_generated_fields's own WHY), not a real change to a skill's
    instructions.

    missing_live -- a file this repo ships that has no counterpart anywhere
    in the live install. This is NOT the same finding as find_rules_drift's
    "un-run redeploy" skip, even though it looks identical from inside a
    single compare(): for hooks/ and rules/, the maintainer edits and
    redeploys the SAME tree on the SAME machine, so "shipped, not yet live"
    overwhelmingly means "haven't re-run install.sh." That reasoning does
    NOT transfer here, because #425 (release-scout.md) was exactly this
    shape and was NOT a redeploy lag: install.sh's own source mapping was
    wrong, so no number of re-runs would have delivered the file. Silently
    treating this as "un-run redeploy" is the same complacent assumption
    that let release-scout stay invisible until it was noticed by hand --
    the failure this whole guard exists to replace with a mechanical check.
    A second, unrelated reason this direction is cheap to report for these
    three kinds and was expensive for rules/: the repo-shipped set here is
    small and fully enumerable (the SAME set this function already walks to
    find content drift), not a second tree that needs its own traversal.

    drifted -- present in both, and the text still differs after stripping
    the two known generated-field causes. This is the bucket worth reading.

    enriched -- present in both, raw text differs, but the difference is
    fully explained by a known, intentional, or ordinary-redeploy-lag cause
    (see _strip_generated_fields). Reported separately, in a deliberately
    quieter tone, so it stays visible without training the reader to skip
    past this hook's output the way a constant false alarm would.

    Still does NOT report the fourth direction (live but not shipped by this
    repo) -- that's the ~450-skill noise this function's own docstring
    measured, and it stays off for the same reason it always was.
    """
    missing_live: list[str] = []
    drifted: list[str] = []
    enriched: list[str] = []

    def compare(kind: str, repo_file: Path, live_file: Path, label: str) -> None:
        if not live_file.is_file():
            missing_live.append(f"{kind}: {label}")
            return
        repo_text = _normalized(repo_file)
        live_text = _normalized(live_file)
        if repo_text is None or live_text is None or repo_text == live_text:
            return
        if _strip_generated_fields(repo_text) == _strip_generated_fields(live_text):
            enriched.append(f"{kind}: {label}")
        else:
            drifted.append(f"{kind}: {label}")

    for kind, subdir in (("agent", "agents"), ("command", "commands")):
        repo_dir = repo_root / subdir
        live_dir = claude_home / subdir
        if not repo_dir.is_dir() or not live_dir.is_dir():
            continue
        try:
            if repo_dir.resolve() == live_dir.resolve():
                continue  # --link install: comparing a tree to itself
        except OSError:
            pass
        for repo_file in sorted(repo_dir.glob("*.md")):
            # agents/CLAUDE.md is repo-local authoring guidance, never
            # installed -- the same file sync_doc_counts.py excludes from
            # the agent count.
            if repo_file.name == "CLAUDE.md":
                continue
            compare(kind, repo_file, live_dir / repo_file.name, repo_file.name)

    repo_skills = repo_root / "skills"
    live_skills = claude_home / "skills"
    if repo_skills.is_dir() and live_skills.is_dir():
        same = False
        try:
            same = repo_skills.resolve() == live_skills.resolve()
        except OSError:
            pass
        if not same:
            # rglob, not a fixed-depth glob("*/*/SKILL.md") -- the earlier
            # draft hardcoded exactly two nesting levels (core|extensions/
            # <name>/SKILL.md), which is everywhere true on this machine
            # today (verified: every shipped SKILL.md sits at that same
            # depth) but is an assumption about tomorrow's layout, not a
            # fact this function should encode. A third level added later
            # would not error under the fixed glob -- it would silently
            # match nothing and report a clean tree, exactly the
            # checked-known-set-not-the-universe failure this session's own
            # research-methodology work names. rglob has no depth to get
            # wrong: it finds a SKILL.md wherever one is nested.
            for repo_file in sorted(repo_skills.rglob("SKILL.md")):
                name = repo_file.parent.name
                compare("skill", repo_file, live_skills / name / "SKILL.md", name)

    return missing_live, drifted, enriched


def _format_findings(header: str, findings: list[str]) -> str:
    shown = findings[:10]
    more = len(findings) - len(shown)
    suffix = f"\n  ... and {more} more" if more > 0 else ""
    return header + "\n  " + "\n  ".join(shown) + suffix


def main() -> None:
    try:
        root = Path.cwd()
        if not is_this_repo(root):
            return
        claude_home = resolve_claude_home()
        if claude_home is None:
            return
        live_hooks = claude_home / "hooks"
        if not live_hooks.is_dir():
            return
        repo_hooks = root / "hooks"
        # WHY same-path check: a --link install (symlinks) or --target
        # pointing straight at this repo's own hooks/ makes drift
        # structurally impossible -- comparing a directory to itself would
        # only ever report zero drift, so skip the walk entirely.
        try:
            if live_hooks.resolve() == repo_hooks.resolve():
                return
        except OSError:
            pass

        drifted = find_drift(repo_hooks, live_hooks)
        if drifted:
            shown = drifted[:10]
            more = len(drifted) - len(shown)
            lines = "\n  ".join(shown)
            suffix = f"\n  ... and {more} more" if more > 0 else ""
            print(
                "[live-drift-guard] Live ~/.claude/hooks differs from this repo's "
                f"HEAD for {len(drifted)} file(s) -- a fix merged here isn't live "
                "until redeployed:\n  " + lines + suffix
            )

        # WHY a second, separate check (not folded into find_drift above):
        # content hashing answers "is the CODE the same"; this answers "is
        # it WIRED to the same event" -- two independent questions, and
        # 2026-09-02 showed a hook can be byte-identical while being
        # registered under an event that never fires (see this function's
        # own docstring). settings.json legitimately differs in every
        # command string (real paths vs __CLAUDE_HOME__ placeholders), so a
        # naive hash comparison of the whole file would always "drift" --
        # this checks only the structural piece that actually matters.
        repo_settings = repo_hooks / "settings.json"
        # WHY claude_home and NOT live_hooks (bug fixed 2026-09-10): install.sh
        # copies hooks/settings.json to $CLAUDE_DIR/settings.json -- the root of
        # the install, not the hooks/ subdirectory. This line read
        # `live_hooks / "settings.json"`, a path that does not exist on any
        # correctly-installed machine, so the `is_file()` guard below was always
        # False and this entire event-wiring check has been dead code since it
        # was written. The function added specifically to catch hooks that are
        # installed but never run was itself installed and never run. Confirmed
        # by inspection: ~/.claude/hooks/settings.json absent,
        # ~/.claude/settings.json present at 31825 bytes.
        live_settings = claude_home / "settings.json"
        if repo_settings.is_file() and live_settings.is_file():
            event_drift = find_event_registration_drift(repo_settings, live_settings, live_hooks)
            if event_drift:
                shown_e = event_drift[:10]
                more_e = len(event_drift) - len(shown_e)
                lines_e = "\n  ".join(shown_e)
                suffix_e = f"\n  ... and {more_e} more" if more_e > 0 else ""
                print(
                    "[live-drift-guard] Live settings.json registers "
                    f"{len(event_drift)} hook(s) under a DIFFERENT event than "
                    "this repo's HEAD -- code can be identical while the "
                    "wiring makes it dead (see permission_policy.py, "
                    "2026-09-02):\n  " + lines_e + suffix_e
                )
        # WHY a third check, on a different directory: the first two ask
        # whether a hook's CODE and its WIRING made it out of the repo. This
        # asks whether a RULE made it out at all. Same failure family --
        # something real exists on only one side -- different tree, and the
        # one this repo had no mechanical check for until 2026-09-09.
        live_rules = claude_home / "rules"
        repo_rules = root / "rules"
        if live_rules.is_dir() and repo_rules.is_dir():
            try:
                same_tree = live_rules.resolve() == repo_rules.resolve()
            except OSError:
                same_tree = False
            if not same_tree:
                missing, rules_drifted = find_rules_drift(repo_rules, live_rules)
                if missing:
                    print(
                        _format_findings(
                            "[live-drift-guard] "
                            f"{len(missing)} rule file(s) exist in ~/.claude/rules but "
                            "are NOT shipped by this repo -- missing from the "
                            "distribution, not merely stale:",
                            missing,
                        )
                    )
                if rules_drifted:
                    print(
                        _format_findings(
                            "[live-drift-guard] "
                            f"{len(rules_drifted)} rule file(s) differ in content "
                            "between ~/.claude/rules and this repo:",
                            rules_drifted,
                        )
                    )

        # WHY a fourth check, and why it stands apart from the rules block
        # above rather than extending it: rules/ was the only *.md tree whose
        # live copy is roughly the shipped copy, so it can afford to ask the
        # loud question ("what is live and missing from the distribution?").
        # agents/, commands/ and skills/ cannot -- the live install holds
        # 583 skill files against 135 shipped -- so this asks only the
        # narrower one: of what this repo DOES ship, what no longer matches?
        # Added 2026-09-11 to test the prediction recorded in
        # docs/artifact-distribution-topology.md that per-kind coverage
        # closes the class without a new registry layer.
        artifact_missing, artifact_drift, artifact_enriched = find_shipped_artifact_drift(
            root, claude_home
        )
        if artifact_missing:
            print(
                _format_findings(
                    "[live-drift-guard] "
                    f"{len(artifact_missing)} shipped artifact(s) are NOT installed "
                    "live -- shipped by this repo but never delivered (see #425, "
                    "release-scout.md, for a real incident of exactly this):",
                    artifact_missing,
                )
            )
        if artifact_drift:
            print(
                _format_findings(
                    "[live-drift-guard] "
                    f"{len(artifact_drift)} shipped artifact(s) differ in content "
                    "between this repo and the live install -- agents/, commands/ "
                    "and skills/ are covered by NO check above:",
                    artifact_drift,
                )
            )
        # WHY a separate, quieter line rather than folding this into
        # artifact_drift above: these ARE real byte-level differences, but
        # every one is fully explained by _strip_generated_fields's two
        # known causes -- a live-only triggers: field feeding
        # keyword_router.py's index, or a stale BSV header the repo has
        # since dropped. Printed distinctly, in a "for information" tone,
        # so it stays legible without teaching the reader to skip past this
        # hook's output the way a constant false alarm would (measured
        # 2026-09-11: this line replaces what would otherwise be roughly 80
        # additional entries inside artifact_drift above, every session).
        if artifact_enriched:
            print(
                _format_findings(
                    "[live-drift-guard] "
                    f"{len(artifact_enriched)} shipped artifact(s) differ from this repo "
                    "for a known reason (live-only triggers: field or a repo-dropped BSV "
                    "header) -- not a real change, nothing to act on:",
                    artifact_enriched,
                )
            )
    except Exception as e:  # never block session start
        print(f"[live-drift-guard] skipped ({type(e).__name__})", file=sys.stderr)


if __name__ == "__main__":
    main()
