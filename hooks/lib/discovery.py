"""Project/git discovery for Claude Code hooks.

WHY this file exists (split from hooks/utils.py, HS-01 in
artifacts/architecture-coupling/hotspots.json): utils.py's fan-in was 74
(68 hooks + 13 tests import it directly), making every bug here ripple
across 60+ hooks. Splitting by responsibility localizes blast radius.
See hooks/utils.py for the facade that keeps `from utils import X` working.
"""

import re
import subprocess
from pathlib import Path


def run_git(args: list[str], timeout: int = 10, cwd: str | None = None) -> str:
    """Run git command and return stdout.

    WHY: Duplicated identically in pre_commit_guard, post_commit_memory,
    pattern_extractor (3 copies, 36 lines total).

    WHY cwd: without it, git resolves against the HOOK PROCESS's cwd, which is
    fixed per session (the harness's project root) — NOT the directory the
    intercepted command actually targets. In a multi-repo session (e.g. a `cd
    /other/repo && git commit ...` from inside a different project), every check
    here silently reports the WRONG repo's state (branch, staged files, etc.).
    Callers that can determine the command's real target dir (see
    `extract_command_cwd` in pre_commit_guard.py) should pass it through.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def find_project_memory() -> Path | None:
    """Find activeContext.md walking up from CWD.

    WHY: Duplicated in memory_guard, checkpoint_guard, post_commit_memory,
    session_save, pre_compact (5 copies with slight variations).
    """
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        # WHY: global vault uses _auto/ subfolder, but project-level vaults
        # keep activeContext.md directly in memory/. Check both paths.
        for subpath in [
            ".claude" / Path("memory") / "_auto" / "activeContext.md",
            ".claude" / Path("memory") / "activeContext.md",
        ]:
            candidate = parent / subpath
            if candidate.exists():
                return candidate
    return None


def find_project_claude_dir() -> Path | None:
    """Find .claude/memory/ directory walking up from CWD.

    WHY: session_start.py variant — returns directory, not file.
    Also checks for CLAUDE.md as project root marker.
    """
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        # WHY: check _auto/ (global vault v2) then direct (project-level vaults)
        for subpath in [
            ".claude" / Path("memory") / "_auto" / "activeContext.md",
            ".claude" / Path("memory") / "activeContext.md",
        ]:
            if (parent / subpath).exists():
                return parent / ".claude" / "memory"
        if (parent / "CLAUDE.md").exists():
            claude_mem = parent / ".claude" / "memory"
            if claude_mem.exists():
                return claude_mem
    return None


def find_scope_fence() -> Path | None:
    """Find Scope Fence file, searching multiple tool-agnostic locations.

    Search order (first found wins):
    1. .scope-fence.md at project root (universal)
    2. .claude/memory/activeContext.md (Claude Code)
    3. .cursor/memory_bank/activeContext.md (Cursor)

    WHY: Duplicated in drift_guard.py and session_start.py (identical logic).
    """
    cwd = Path.cwd()
    candidates = [
        ".scope-fence.md",
        str(Path(".claude") / "memory" / "_auto" / "activeContext.md"),
        str(Path(".claude") / "memory" / "activeContext.md"),
        str(Path(".cursor") / "memory_bank" / "activeContext.md"),
    ]
    for parent in [cwd, *cwd.parents]:
        for rel in candidates:
            full = parent / rel
            if full.exists():
                return full
    return None


def parse_scope_fence(content: str) -> dict[str, str]:
    """Extract Scope Fence fields from file content.

    Returns dict with keys: goal, boundary, done_when, not_now.
    WHY: Used by both drift_guard and session_start.
    """
    fence: dict[str, str] = {}
    in_fence = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "## Scope Fence":
            in_fence = True
            continue
        if in_fence and stripped.startswith("## "):
            break
        if not in_fence:
            continue

        if stripped.startswith("Goal:"):
            fence["goal"] = stripped[5:].strip()
        elif stripped.startswith("Boundary:"):
            fence["boundary"] = stripped[9:].strip()
        elif stripped.startswith("Done when:"):
            fence["done_when"] = stripped[10:].strip()
        elif stripped.startswith("NOT NOW:"):
            fence["not_now"] = stripped[8:].strip()

    return fence


# WHY moved here from pre_commit_guard.py (2026-07-21): a second hook
# (gitnexus_reindex.py) needs the same cwd-extraction to avoid reindexing the
# WRONG repo in a multi-repo session -- importing pre_commit_guard.py directly
# is unsafe (it calls hook_main(main, fail_closed=True) at MODULE level, not
# gated by `if __name__ == "__main__"`, so importing it would re-run its own
# PreToolUse logic). utils.py has zero import-time side effects, the one safe
# place for logic shared across hook files.
#
# WHY split-then-scan-for-LAST-cd, not a single anchored regex (reviewer
# finding, 2026-07-21, reproduced live): the original version only matched a
# `cd` at the very START of the whole string, so a SECOND `cd` later in a
# chain -- `cd /a && cd /b && git commit ...` -- was invisible and resolved to
# `/a`, silently reindexing the WRONG repo. This shares the same chain-operator
# split intent as pre_commit_guard.py's `_CHAIN_SPLIT_RE` (duplicated here, not
# imported, for the same module-level-side-effect safety reason as the move
# above) but is intentionally NOT heredoc/newline-aware like pre_commit_guard's
# full tokenizer -- that scope wasn't part of the reported bug (a same-line
# `&&`-chain), and porting the whole tokenizer for this one fix would be
# disproportionate.
_CD_STATEMENT_RE = re.compile(r'^cd\s+(?:"([^"]+)"|\'([^\']+)\'|(\S+))$')


def _split_on_chain_operators(command: str) -> list[str]:
    """Split on &&, ||, ;, &, | -- but NEVER inside a quoted span.

    WHY not a plain regex split (reviewer finding, 2026-07-21, reproduced
    live): `_CHAIN_SPLIT_RE.split()` operated on the raw string with no idea
    it was inside a quote, so a quoted path containing a literal chain-
    operator character -- a plausible real directory name like "R&D" -- got
    truncated mid-quote: `cd "C:\\Projects\\R&D" && git commit` resolved to
    `"C:\\Projects\\R` instead of `C:\\Projects\\R&D`. That silently fed a
    malformed cwd into pre_commit_guard.py's branch-protection Check 1,
    which then fails OPEN (run_git raises, caught, branch resolves to ""
    rather than raising a visible error) for any repo path containing
    &/;/| -- the opposite of what a security check should do on bad input.
    A quote-aware scan is the minimal fix that doesn't require a full shlex
    dependency for this narrow use.
    """
    statements: list[str] = []
    current: list[str] = []
    quote: str | None = None
    i = 0
    n = len(command)
    while i < n:
        ch = command[i]
        if quote:
            current.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            current.append(ch)
            i += 1
            continue
        if command[i : i + 2] in ("&&", "||"):
            statements.append("".join(current))
            current = []
            i += 2
            continue
        if ch in (";", "&", "|"):
            statements.append("".join(current))
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    statements.append("".join(current))
    return statements


def extract_command_cwd(command: str) -> str | None:
    """Extract the target directory of the LAST `cd <dir>` in a chained
    command that is followed by at least one more statement (e.g. `cd /a &&
    cd /b && git commit ...` -> `/b`) -- the chain's trailing command runs in
    whatever directory the last `cd` left it in, not the first hop.

    A bare `cd <dir>` with nothing chained after it returns None: matches the
    original semantics (a `cd` with no follow-up command isn't "the directory
    something else runs in" -- there is no something else).
    """
    statements = _split_on_chain_operators(command)
    target: str | None = None
    for statement in statements[:-1]:  # the last statement can't have anything "after" it
        match = _CD_STATEMENT_RE.match(statement.strip())
        if match:
            target = next((g for g in match.groups() if g is not None), None)
    return target


def find_file_upward(relative_path: str) -> Path | None:
    """Find a file by walking up the directory tree from CWD.

    WHY: Generic version of find_project_memory/find_checkpoints_dir.
    Reduces the need for one-off search functions.
    """
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        full = parent / relative_path
        if full.exists():
            return full
    return None
