#!/usr/bin/env python3
"""SessionStart hook: warn when the LIVE ~/.claude install has drifted
away from what this repo actually ships -- hooks/ (content + event
wiring) and rules/ (content + files that exist only in the personal
install).

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


def find_event_registration_drift(repo_settings: Path, live_settings: Path) -> list[str]:
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
            continue  # not deployed live at all -- find_drift's territory, not this check's
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
        live_settings = live_hooks / "settings.json"
        if repo_settings.is_file() and live_settings.is_file():
            event_drift = find_event_registration_drift(repo_settings, live_settings)
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
    except Exception as e:  # never block session start
        print(f"[live-drift-guard] skipped ({type(e).__name__})", file=sys.stderr)


if __name__ == "__main__":
    main()
