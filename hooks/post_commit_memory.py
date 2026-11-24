#!/usr/bin/env python3
"""PostToolUse hook for Bash: auto-log commits to activeContext.md.

WHY: memory_guard only REMINDS to update context. This hook ACTS —
it automatically appends the commit log to activeContext.md. Double safety net:
1. Auto-log (commit fact recorded)
2. Reminder for Claude to supplement context manually (auto-log is the minimum)

Difference from memory_guard: memory_guard checks file freshness.
post_commit_memory maintains a structured commit log.
"""

import contextlib
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from lib.discovery import (
    _CD_STATEMENT_RE,
    _normalize_gitbash_drive_path,
    _split_on_chain_operators,
    find_file_upward,
    find_project_memory,
    run_git,
)
from lib.runtime import (
    emit_hook_result,
    extract_tool_response,
    get_tool_input,
    is_failed_commit,
    parse_stdin,
)
from lib.state import atomic_write_json, atomic_write_text, file_lock, load_json_state

# WHY (docs/memory-architecture.md target, implemented 2026-08-22): the
# Auto-commit log in activeContext.md grew unbounded -- this file's own
# section header comment already calls that section "history, not source
# of truth", but nothing capped it, so it kept growing until PreCompact's
# progressive-summary pass collapsed old entries into "[summarized]"
# markers, permanently losing the per-commit detail. Every commit now ALSO
# gets appended to a permanent, per-day archive (history/commits-<date>.md)
# before the active section is capped -- trimming the recent view is then
# safe: nothing is lost, it just isn't duplicated in both places forever.
_ACTIVE_LOG_CAP = 15

# WHY (GitHub issue #354, found via 4 separate Codex-review catches in the
# repo this hook was designed against, 2026-09-04): that repo's own workflow
# always squash- or rebase-merges PRs, which mints a brand-new commit hash
# on `main` and makes the hash logged here at commit time permanently
# unreachable from any remote branch the moment its PR merges -- verified
# repeatedly there with `git branch -r --contains <hash>` returning empty
# for every such commit checked. The hook cannot know at commit time
# whether -- or how -- a branch will eventually be merged (a hard timing
# constraint, not fixable by changing what gets computed here), so the log
# entry itself says plainly when a hash might not stay resolvable, WITHOUT
# presuming any specific merge policy.
#
# WHY this is deliberately NOT worded as "will be squashed" (Codex review,
# PR #355, corrected before merge): this hook is a distributable Claude
# Code config artifact, installed into other people's ~/.claude/hooks/ by
# hooks/CLAUDE.md's own description -- an installation using ordinary merge
# commits (history preserved, hash never rewritten) or a local branch that
# never becomes a PR at all would make a flat "will be squashed" claim
# simply false there. The wording below only says a hash MAY be replaced,
# without asserting which merge strategy (if any) will be used.
#
# WHY detached HEAD gets its OWN category, not lumped in with "stable like
# main" (Codex review, PR #355, second finding, corrected before merge):
# `git branch --show-current` returns "" for detached HEAD exactly like it
# does for "we couldn't determine the branch" -- but a detached-HEAD commit
# has no branch ref retaining it at all and can become unreachable via
# ordinary garbage collection, which is the same class of risk this fix
# exists to flag, not the "this is fine, like main" case an empty string
# was originally treated as.
_MAIN_BRANCH_NAMES = frozenset({"main", "master"})

# WHY (2026-09-05, user report: "тот же бесконечный хвост" -- a burst of
# commits in one session, e.g. a PR-per-fix workflow, made this hook's
# "please update context manually" line fire identically after every single
# commit): the archive + Auto-commit log writes below are the valuable,
# lossless part and must never be throttled -- only the repeated NUDGE TEXT
# is noise once a session already saw it. First commit of a session gets the
# full reminder; commits 2..(N-1) after that get silence (archive still
# happens); every Nth commit repeats it once, so a long session isn't
# reminded exactly once and then never again. Session-scoped (not global)
# so a fresh session always gets the first-commit reminder.
_NUDGE_EVERY_N = 5
_NUDGE_STATE_FILENAME = "post_commit_nudge.json"  # under active_ctx.parent/"state"


def _nudge_commit_count(active_ctx: Path, session_id: str) -> int:
    """Increment and return this session's commit count, for nudge throttling.

    Plain counter, no signing (unlike iteration_guard.py's HMAC-signed
    session state): this gates cosmetic reminder text, not a security
    control, so tampering has zero blast radius -- proportionate effort.

    WHY keyed off `active_ctx.parent` (sibling of the existing `history/`
    dir from `_history_dir()`, same depth, same convention), not
    `Path.cwd()` and not two parents up: cwd during a hook invocation isn't
    guaranteed to be the project root the memory file was actually found
    under (find_project_memory() walks upward), and in tests it's the test
    runner's cwd, not the fixture's tmp_path -- using cwd directly would
    write real state into this repo's own `.claude/state/` during `pytest`.
    Climbing two parents (assuming activeContext.md always sits under a
    `.claude/memory/` pair) is equally fragile: this file's own tests place
    activeContext.md directly in `tmp_path` with no `.claude/memory/`
    nesting, so `.parent.parent` escaped tmp_path into pytest's shared temp
    root and let unrelated tests collide on one counter (caught by
    test_creates_new_section_in_active_context still failing after the
    Path.cwd() fix, for a different reason than the first failure). One
    parent up -- exactly where `_history_dir()` already writes -- makes no
    assumption about directory depth at all.
    """
    state_dir = active_ctx.parent / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / _NUDGE_STATE_FILENAME
    state = load_json_state(state_path)
    count = int(state.get(session_id, 0)) + 1
    state[session_id] = count
    # WHY cap the dict itself, not just rely on session churn: a very
    # long-lived install could otherwise accumulate one entry per session_id
    # forever. Keep only the most recent 200 sessions' counters.
    if len(state) > 200:
        for stale_key in list(state.keys())[: len(state) - 200]:
            del state[stale_key]
    atomic_write_json(state_path, state)
    return count


def _current_branch(cwd: str | None = None) -> str:
    """Best-effort current branch name; empty string if unknown/detached.

    `cwd` is the repository the commit was made in (None = the hook process's cwd).
    """
    if cwd is None:
        return run_git(["branch", "--show-current"])
    return run_git(["branch", "--show-current"], cwd=cwd)


_SELF_LOG_COMMIT_PREFIX = "chore: auto-log commit history entry"


def _is_self_log_commit(commit_msg: str) -> bool:
    """True if commit_msg is this hook's own auto-log commit (any suffix).

    WHY (2026-09-07, Y-17-100-gipotez incident): this hook only WRITES to
    activeContext.md/history/, it never commits itself -- but the write
    leaves the file dirty, and committing that dirty file as "chore:
    auto-log commit history entry" is itself a `git commit`, which
    re-triggers this hook, which writes again, forever. 6+ chained commits
    happened live before being manually cut off. Checked right after
    commit_msg is read in main(), before any writes, to break the loop.

    WHY prefix match, not substring: a real commit that DESCRIBES this fix
    (e.g. "fix: guard against chore: auto-log commit history entry loop")
    must not be swallowed by its own guard.
    """
    return commit_msg.strip().lower().startswith(_SELF_LOG_COMMIT_PREFIX)


def _format_log_entry(commit_hash: str, commit_msg: str, branch: str, now_dt: datetime) -> str:
    """Build one Auto-commit log line, honest about hash instability.

    See the module-level WHY comment above _MAIN_BRANCH_NAMES for the full
    rationale -- this is the one place those decisions are applied.
    """
    timestamp = now_dt.strftime("%Y-%m-%d %H:%M")
    if branch in _MAIN_BRANCH_NAMES:
        return f"- [{timestamp}] `{commit_hash}`: {commit_msg}\n"
    if branch:
        return (
            f"- [{timestamp}] `{commit_hash}` (local, branch `{branch}` -- "
            f"may be replaced if this branch is later merged via squash or "
            f"rebase; check that branch's PR/merge for the surviving hash "
            f"if this one becomes unresolvable): {commit_msg}\n"
        )
    return (
        f"- [{timestamp}] `{commit_hash}` (detached HEAD or unknown branch "
        f"-- not retained by any branch ref; may become unreachable unless "
        f"tagged or merged): {commit_msg}\n"
    )


@contextlib.contextmanager
def _locked(path: Path):
    """Serialise a read-modify-write of a shared memory file across hook processes.

    WHY: atomic_write_text only prevents a TORN file, not a lost update. Measured 2026-11-08
    on log_decision(): 8 parallel appenders kept 1 entry in 10 of 10 trials (serial control
    8 of 8). Uses the repo's existing lib.state.file_lock; on timeout raises (same convention
    as doc_registry / expert_registry), caught by hook_main -- never proceeds unlocked.
    """
    with file_lock(Path(f"{path}.lock"), timeout=4.0) as acquired:
        if not acquired:
            raise TimeoutError(f"could not lock {path.name} within 4s")
        yield


def _history_dir(active_ctx: Path) -> Path:
    """The history/ directory sibling to activeContext.md."""
    history_dir = active_ctx.parent / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir


def _archive_commit(active_ctx: Path, log_entry: str, now: datetime) -> None:
    """Append this commit's log line to today's permanent daily archive.

    WHY a new file per day, not per commit: a file per commit (mirroring
    DeepSeek Harness's `.agents/notes/<date>-<slug>.md`) would multiply tiny
    files for routine commits (this repo's own "docs(memory): auto-log entry
    for <sha>" churn is a good example) -- the daily archive gives a
    permanent, ungrowing-per-file record without that multiplication. A
    richer, hand-written `<date>-<slug>.md` narrative note (what/why/outcome)
    is still the right artifact for a genuinely noteworthy chunk of work --
    that's authored by the agent doing the work, not generated per commit.
    """
    archive_path = _history_dir(active_ctx) / f"commits-{now.strftime('%Y%m%d')}.md"
    with _locked(archive_path):
        if archive_path.exists():
            existing = archive_path.read_text(encoding="utf-8")
            atomic_write_text(archive_path, existing.rstrip("\n") + "\n" + log_entry)
        else:
            header = f"# Commit log — {now.strftime('%Y-%m-%d')}\n\n"
            atomic_write_text(archive_path, header + log_entry)


def _trim_active_log(lines: list[str], header_idx: int, cap: int) -> list[str]:
    """Keep only the first `cap` log-entry lines directly under the Auto-commit
    log header (newest-first ordering, since new entries are inserted right
    after the header) -- drop the rest from the ACTIVE view. Safe to drop:
    the full record already landed in history/commits-<date>.md above.
    """
    entry_start = header_idx + 1
    entry_end = entry_start
    while entry_end < len(lines) and (
        lines[entry_end].startswith("- [") or lines[entry_end].startswith("[summarized]")
    ):
        entry_end += 1
    # WHY min(): the slice must never reach past entry_end even when cap is
    # larger than the actual entry count -- otherwise it grabs the blank
    # line/next section too, and appending `lines[entry_end:]` right after
    # duplicates them (found by test_under_cap_keeps_everything).
    kept = lines[entry_start : min(entry_end, entry_start + cap)]
    return lines[:entry_start] + kept + lines[entry_end:]


def _find_in_repo(start: str, top: str | None, rels: list[str]) -> Path | None:
    """Walk up from `start` to the repository top level (inclusive) looking for `rels`.

    WHY bounded by the top level (O43, 2026-11-09): the home directory is itself a git
    repository here, so an unbounded walk from any project without its own memory ends at
    ~/.claude/memory and writes that project's commit into the HOME project's log. A
    project memory must live inside the repository the commit was made in; if it does not,
    nothing is written. `top` None/empty = unbounded (callers that could not resolve it).
    """
    top_key = os.path.normcase(os.path.realpath(top)) if top else None
    here = Path(start)
    for parent in [here, *here.parents]:
        for rel in rels:
            candidate = parent / rel
            if candidate.exists():
                return candidate
        if top_key and os.path.normcase(os.path.realpath(parent)) == top_key:
            break
    return None


def find_decisions_file(search_from: str | None = None, bound: str | None = None) -> Path | None:
    """Find decisions.md walking up from CWD (or from `search_from`, stopping at `bound`).

    WHY: global vault uses _auto/ subfolder, project vaults keep decisions.md
    directly in memory/. Check both paths with _auto/ first (preferred).
    """
    if search_from is not None:
        auto = str(Path(".claude") / "memory" / "_auto" / "decisions.md")
        direct = str(Path(".claude") / "memory" / "decisions.md")
        return _find_in_repo(search_from, bound, [auto]) or _find_in_repo(
            search_from, bound, [direct]
        )
    return find_file_upward(
        str(Path(".claude") / "memory" / "_auto" / "decisions.md")
    ) or find_file_upward(str(Path(".claude") / "memory" / "decisions.md"))


# WHY: Nexus-lite — automatic accumulation of architectural decisions from commit messages.
# Commits with arch:/decision:/security:/pattern: prefixes automatically go to decisions.md.
# This turns the manual memory system into a semi-automatic one.
DECISION_PREFIXES = ("arch:", "decision:", "security:", "pattern:")


def extract_decision(commit_msg: str) -> tuple[str, str] | None:
    """Extract decision type and description from commit message.

    Returns (type, description) if commit message starts with a decision prefix.
    """
    msg_lower = commit_msg.lower()
    for prefix in DECISION_PREFIXES:
        if msg_lower.startswith(prefix):
            description = commit_msg[len(prefix) :].strip()
            # Strip conventional commit prefix if present (e.g., "feat: arch: ...")
            decision_type = prefix.rstrip(":")
            return decision_type, description

        # Also check after conventional commit prefix: "feat: arch: ..."
        for conv in ("feat:", "fix:", "refactor:", "chore:", "docs:"):
            combined = f"{conv} {prefix}"
            if msg_lower.startswith(combined):
                description = commit_msg[len(combined) :].strip()
                decision_type = prefix.rstrip(":")
                return decision_type, description

    return None


def log_decision(
    commit_hash: str,
    commit_msg: str,
    search_from: str | None = None,
    bound: str | None = None,
) -> str | None:
    """Auto-record decision to decisions.md if commit message has decision prefix."""
    result = extract_decision(commit_msg)
    if result is None:
        return None

    decision_type, description = result
    decisions_file = (
        find_decisions_file(search_from, bound)
        if search_from is not None
        else find_decisions_file()
    )
    if decisions_file is None:
        return f"Decision detected but no decisions.md found: [{decision_type}] {description}"

    now = datetime.now(UTC).strftime("%Y-%m-%d")
    # Format: ### [date] Description. Type: X. Commit: hash
    entry = f"\n### [{now}] {description}\n- Type: {decision_type}\n- Commit: `{commit_hash}`\n"

    # WHY file_lock: atomic_write_text alone only prevents a torn file. Two invocations that
    # both read the old text still lose one entry (8 parallel appenders kept 1, measured
    # 2026-11-08); the lock serialises the read-modify-write window.
    with _locked(decisions_file):
        content = decisions_file.read_text(encoding="utf-8")
        # Append at the end
        content = content.rstrip() + "\n" + entry
        atomic_write_text(decisions_file, content)

    return f"Auto-recorded [{decision_type}] decision to decisions.md"


# --- Which repository did the commit happen in? (O43, 2026-11-09) ---------------------------
#
# Incident (measured on real events, 2026-11-05..09): every commit made as `cd <repo> && git
# commit ...` from a session whose cwd was another repository (here: the home repository) was
# logged with the LAST commit of the SESSION's repository. Seven log lines in a row named one
# hash from 2026-11-02, including the commit that had just been made in a different worktree.
# Cause: git ran in the hook process's cwd, not where the command ran. The lines below find
# the directory the commit statement actually ran in (cd chain / `git -C`), read the commit
# from THAT repository, and write only into a memory directory inside it. If the directory or
# the commit cannot be established reliably, nothing is logged -- never another project's data.
_GIT_OPTS = (
    r"(?:\s+(?:-C\s+(?:\"[^\"]+\"|'[^']+'|\S+)"
    r"|-c\s+(?:[^\s\"']|\"[^\"]*\"|'[^']*')+"
    r"|--(?:git-dir|work-tree)(?:=|\s+)\S+"
    r"|--no-pager|--no-optional-locks|-p))*"
)
# a statement that IS a commit: optional env assignments / `command`, then git [options] commit
_GIT_COMMIT_RE = re.compile(
    r"^(?:\w+=\S*\s+)*(?:command\s+)?git(" + _GIT_OPTS + r")\s+commit(?![\w-])"
)
# the same anywhere in the command: the cheap gate in main()
_GIT_COMMIT_ANY_RE = re.compile(r"\bgit(" + _GIT_OPTS + r")\s+commit(?![\w-])")
_GIT_DIR_OPT_RE = re.compile(r"--(?:git-dir|work-tree)|\bGIT_(?:DIR|WORK_TREE)=")
# interpreters / wrappers that can run a quoted command line somewhere else
_INTERPRETER_RE = re.compile(r"\b(?:bash|sh|zsh|dash|eval|exec|xargs|source|env|sudo)\b")
_QUOTED_RE = re.compile(r"\"[^\"]*\"|'[^']*'")
# anything in the command that can point git at another directory
_REDIRECT_HINT_RE = re.compile(
    r"(?:^|[\s(;&|{\"'`])(?:cd|pushd|popd)(?:\s|$)|\s-C\s|--git-dir|--work-tree|GIT_DIR=|GIT_WORK_TREE="
)
_HEREDOC_RE = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_]\w*)\1")
_GIT_C_OPT_RE = re.compile(r"-C\s+(?:\"([^\"]+)\"|'([^']+)'|(\S+))")
# a statement that STARTS with cd/pushd/popd (optionally inside a subshell)
_CD_LIKE_RE = re.compile(r"^[({\s]*(?:cd|pushd|popd)(?:\s|$)")
# `[branch abc1234] subject`, `[branch (root-commit) abc1234] subject`, `[detached HEAD abc1234]`
_COMMIT_LINE_RE = re.compile(r"^\[[^\]\n]*?\s([0-9a-f]{7,40})\]", re.MULTILINE)
# A HEAD commit older than this cannot be "the commit that just ran" when the tool output did
# not name it (e.g. `git commit -q`): treated as unconfirmed and skipped.
_FRESH_COMMIT_SECONDS = 600


def _resolve_dir(raw: str, base: str | None) -> str | None:
    """Existing absolute directory for a `cd`/`-C` operand, or None if it is not certain."""
    raw = raw.strip()
    if not raw or raw.startswith("~") or raw == "-" or any(ch in raw for ch in "$%`*?"):
        return None
    path = Path(_normalize_gitbash_drive_path(raw))
    if not path.is_absolute():
        if base is None:
            return None
        path = Path(base) / path
    resolved = os.path.normpath(str(path))
    return resolved if os.path.isdir(resolved) else None


def _strip_heredocs(command: str) -> str:
    """Drop heredoc bodies (message text), keeping the command text before each `<<WORD`."""
    out: list[str] = []
    terminator: str | None = None
    for line in command.split("\n"):
        if terminator is not None:
            if line.strip() == terminator:
                terminator = None
            continue
        match = _HEREDOC_RE.search(line)
        if match:
            out.append(line[: match.start()])
            terminator = match.group(2)
        else:
            out.append(line)
    return "\n".join(out)


def _split_lines_unquoted(chunk: str) -> list[str]:
    """Split on newlines outside quotes (a multi-line `-m "..."` message stays whole)."""
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for ch in chunk:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            current.append(ch)
        elif ch == "\n":
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def _commit_target_dir(command: str, base: str) -> str | None:
    """Directory in which the (last) `git commit` statement of `command` ran.

    None whenever the directory is not certain: an unresolvable `cd`, `--git-dir`/`--work-tree`/
    GIT_DIR, ANY statement in the command that can move git elsewhere and that this parser does
    not follow (`then cd B`, `bash -c "cd B && ..."`, `export GIT_DIR=...`), or a command with no
    recognisable `git commit` statement. `base` only for a command that cannot have left the
    session directory. Unknown means "log nothing", never "fall back to the session repo".
    """
    head = _strip_heredocs(command)  # heredoc bodies are message text, never commands
    cwd: str | None = base
    saw_commit = False
    tainted = False  # a statement we do not follow may have moved git elsewhere
    result: str | None = base
    statements = [
        part for chunk in _split_on_chain_operators(head) for part in _split_lines_unquoted(chunk)
    ]
    for statement in statements:
        stripped = statement.strip()
        commit = _GIT_COMMIT_RE.match(stripped)
        if commit:
            saw_commit = True
            c_opt = _GIT_C_OPT_RE.search(commit.group(1) or "")
            if cwd is None or _GIT_DIR_OPT_RE.search(stripped[: commit.end()]):
                result = None
            elif c_opt:
                result = _resolve_dir(next(g for g in c_opt.groups() if g is not None), cwd)
            else:
                result = cwd
            continue
        cd_match = _CD_STATEMENT_RE.match(stripped)
        if cd_match:
            cwd = _resolve_dir(next(g for g in cd_match.groups() if g is not None), cwd)
        elif _CD_LIKE_RE.search(stripped):
            cwd = None  # (cd x), pushd, cd with options: directory unknown from here on
            tainted = True
        else:
            unquoted = _QUOTED_RE.sub('""', stripped)
            if _REDIRECT_HINT_RE.search(unquoted) or (
                _INTERPRETER_RE.search(unquoted) and _REDIRECT_HINT_RE.search(stripped)
            ):
                tainted = True  # e.g. `then cd B`, `bash -c "cd B && ..."`, `export GIT_DIR=...`
    if tainted:
        return None
    if saw_commit:
        return result
    if cwd is None or _REDIRECT_HINT_RE.search(head):
        return None
    if not _GIT_COMMIT_ANY_RE.search(_QUOTED_RE.sub('""', head)):
        return None  # the commit only appears inside quotes / a heredoc: where it ran is unknown
    return base


def _is_fresh_commit(target: str) -> bool:
    """True unless HEAD's committer time is parseable AND older than _FRESH_COMMIT_SECONDS."""
    stamp = run_git(["log", "-1", "--format=%ct"], cwd=target)
    try:
        return time.time() - int(stamp) <= _FRESH_COMMIT_SECONDS
    except ValueError:
        return True  # cannot tell: the directory evidence stands on its own


def _confirmed_commit(response_text: str, target: str) -> str | None:
    """Abbreviated hash of the commit named in git's own output, verified in `target`.

    "" = git named no commit (e.g. `-q`); None = git named a commit that does NOT exist in
    `target`, i.e. the resolved directory is wrong -- the caller must log nothing.
    """
    named = _COMMIT_LINE_RE.findall(response_text)
    if not named:
        return ""
    full = run_git(["rev-parse", "--verify", "--quiet", f"{named[-1]}^{{commit}}"], cwd=target)
    if not full:
        return None
    return run_git(["log", "-1", "--format=%h", full], cwd=target)


def main() -> None:
    # WHY: prevent recursion when this hook fires inside a subagent's
    # SessionStart/etc — see hooks/CLAUDE.md "Recursion guard" section.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    data = parse_stdin()
    if not data:
        return

    tool_input = get_tool_input(data)
    command = tool_input.get("command", "")

    # options may sit between `git` and `commit` (-C <dir>, -c k=v, --no-pager)
    if not _GIT_COMMIT_ANY_RE.search(command):
        return

    response_text = extract_tool_response(data)
    if is_failed_commit(response_text):
        return

    session_cwd = data.get("cwd")
    if not (isinstance(session_cwd, str) and os.path.isdir(session_cwd)):
        session_cwd = os.getcwd()
    target = _commit_target_dir(command, session_cwd)
    if target is None:
        emit_hook_result(
            "PostToolUse",
            "[post-commit-memory] Commit not auto-logged: could not determine reliably "
            "which repository it was made in (unresolvable cd / -C target).",
        )
        return

    # Get the commit data from the repository the commit ran in
    commit_hash = _confirmed_commit(response_text, target)
    if commit_hash is None:
        emit_hook_result(
            "PostToolUse",
            "[post-commit-memory] Commit not auto-logged: git named a commit that is not in the "
            "repository resolved for this command, so the target directory is not reliable.",
        )
        return
    if not commit_hash:
        commit_hash = run_git(["log", "-1", "--format=%h"], cwd=target)
        if commit_hash and not _is_fresh_commit(target):
            return  # HEAD is old and git's output did not name a new commit: not ours
    commit_msg = (
        run_git(["log", "-1", "--format=%s", commit_hash], cwd=target) if commit_hash else ""
    )

    if not commit_hash:
        return

    # WHY here, before any writes: break the self-referencing commit loop --
    # see _is_self_log_commit's docstring for the incident this guards.
    if _is_self_log_commit(commit_msg):
        return

    # Find activeContext.md INSIDE the repository of the commit (never the home project's)
    top = run_git(["rev-parse", "--show-toplevel"], cwd=target)
    if top:
        active_ctx = _find_in_repo(
            target,
            top,
            [str(Path(".claude") / "memory" / "_auto" / "activeContext.md")],
        ) or _find_in_repo(
            target,
            top,
            [str(Path(".claude") / "memory" / "activeContext.md")],
        )
    else:
        active_ctx = find_project_memory()
    if active_ctx is None:
        emit_hook_result(
            "PostToolUse",
            "[post-commit-memory] Commit logged but no activeContext.md found. "
            "Consider creating .claude/memory/activeContext.md for project state tracking.",
        )
        return

    # WHY: we append to the file, not overwrite.
    # The "Auto-commit log" section is a structured log, easy to parse.
    now_dt = datetime.now()
    branch = _current_branch(target)
    log_entry = _format_log_entry(commit_hash, commit_msg, branch, now_dt)

    # WHY first, before touching activeContext.md: the permanent record must
    # land before the active view is capped, so a crash between the two
    # writes below never loses a commit -- worst case is a duplicate in both
    # places, never a gap in the archive.
    _archive_commit(active_ctx, log_entry, now_dt)

    # WHY file_lock around the whole read-modify-write: see log_decision.
    with _locked(active_ctx):
        content = active_ctx.read_text(encoding="utf-8")

        # Find existing section or create a new one
        section_header = "## Auto-commit log"
        if section_header in content:
            # Append after the section header (before next section or at end)
            lines = content.split("\n")
            insert_idx = None
            for i, line in enumerate(lines):
                if line.strip() == section_header:
                    insert_idx = i + 1
                    break
            if insert_idx is not None:
                lines.insert(insert_idx, log_entry.rstrip())
                lines = _trim_active_log(lines, insert_idx - 1, _ACTIVE_LOG_CAP)
                content = "\n".join(lines)
        else:
            # Create section at end of file
            content = content.rstrip() + f"\n\n{section_header}\n{log_entry}"

        atomic_write_text(active_ctx, content)

    # Nexus-lite: auto-record decisions from commit message prefixes
    decision_msg = (
        log_decision(commit_hash, commit_msg, search_from=target, bound=top)
        if top
        else log_decision(commit_hash, commit_msg)
    )

    # Reminder for Claude to supplement context manually -- throttled per
    # session (see _NUDGE_EVERY_N WHY above). The archive + active-log
    # writes above already happened unconditionally; only this text is
    # gated, so no commit is ever silently un-logged.
    # WHY (2026-09-05, found by skeptic dogfooding boyko-scientific-consortium
    # on this exact fix): defaulting a missing session_id to the literal
    # string "default" would collapse every caller that ever omits it onto
    # ONE shared counter -- the opposite failure mode from the one this
    # throttle exists to fix (over-suppression across unrelated callers,
    # instead of under-suppression within one burst). Always nudge when
    # session_id is absent -- a spurious reminder is a safe default, a
    # silently-merged counter across strangers is not.
    session_id = data.get("session_id")
    if session_id is None:
        should_nudge = True
    else:
        nudge_count = _nudge_commit_count(active_ctx, session_id)
        should_nudge = nudge_count == 1 or nudge_count % _NUDGE_EVERY_N == 0

    additional = ""
    if should_nudge:
        additional = (
            f"[post-commit-memory] Commit {commit_hash} auto-logged. "
            "If this was a meaningful change, a short WHAT/WHY note in "
            "activeContext.md helps future sessions — the auto-log alone "
            "only has the commit message."
        )
    if decision_msg:
        additional = (
            f"{additional} | {decision_msg}"
            if additional
            else f"[post-commit-memory] {decision_msg}"
        )

    # WHY: feat/refactor commits often involve architectural decisions that
    # should be recorded in decisions.md. Nudge when not already captured
    # by an explicit decision prefix (arch:/decision:/security:/pattern:).
    # Not throttled like the reminder above -- each feat/refactor commit is
    # its own distinct decision point, not a repeat of the same notice.
    _ADR_PREFIXES = ("feat:", "refactor:")
    _needs_adr_nudge = (
        any(commit_msg.lower().startswith(p) for p in _ADR_PREFIXES)
        and extract_decision(commit_msg) is None
    )
    if _needs_adr_nudge:
        adr_line = (
            "📋 ADR nudge: feat/refactor commit — was an architectural choice made? "
            "If yes, add an entry to decisions.md "
            "(format: ### [date] Decision. Type: arch. Commit: hash)"
        )
        additional = (
            f"{additional} | {adr_line}" if additional else f"[post-commit-memory] {adr_line}"
        )

    if additional:
        emit_hook_result("PostToolUse", additional)


if __name__ == "__main__":
    main()
