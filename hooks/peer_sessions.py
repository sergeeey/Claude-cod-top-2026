#!/usr/bin/env python3
"""Tell this Claude Code session what OTHER sessions are doing in the same repo.

WHY (2026-09-13): the maintainer runs 3-4 sessions on this repo at once, and the
same work gets done twice. On the day this was written two sessions independently
picked the same branch number (`y63/...`), one grabbed the PR number another had
assumed, and the main checkout sat dirty on a branch 78 commits behind main. The
harness can already list peer sessions -- but only when the model thinks to ask.
This hook makes that automatic, the same way live_drift_guard made drift checks
automatic instead of something someone remembers.

What it reads, and why these signals and not others (measured, not assumed):
  * Transcripts under ~/.claude/projects/*/<session>.jsonl modified in the last
    WINDOW_MIN minutes = live peers. Cheap: 88 files, 0.11 s to stat on the
    maintainer's machine.
  * From each peer, the file_path of its Edit/Write/MultiEdit/NotebookEdit tool
    calls. NOT the transcript's `cwd`/`gitBranch` fields: those record where a
    session was LAUNCHED. Two peers that did all their work in D:/cc-wt/* both
    reported cwd D:\\Claude-cod-top-2026 on a stale branch -- a hook trusting
    `cwd` would have announced three sessions colliding in one checkout. False.
  * Only paths inside a worktree of THIS repo (`git worktree list`) count, so a
    peer's scratchpad or another project never shows up here.

What it emits (additionalContext only -- never blocks):
  SessionStart      a summary of peers active in this repo, plus uncommitted files
                    per worktree (git sees edits made by ANY tool, including Bash
                    scripts, which the transcript signal cannot).
  UserPromptSubmit  the same summary, but ONLY for peers this session has not been
                    told about yet -- silent otherwise, so a long session hears about
                    a newcomer once, without a banner on every prompt.
  PostToolUse       after an Edit/Write, a warning when a peer touched the same file
                    within the window: the SAME absolute path (both sessions are
                    writing one file -- clobber risk) or the same repo-relative path
                    in a DIFFERENT worktree (a merge conflict waiting to happen).
                    Each (file, peer) pair is reported once per session.

Known limits, stated so they are not mistaken for coverage:
  * Edits made through Bash (sed, python scripts, redirection) have no file path in the
    transcript. A Bash command whose text names a worktree of this repo is reported as
    PRESENCE in that worktree ("running shell commands in ..."), never as an edit of a
    specific file -- the command may only have read something. The SessionStart
    dirty-file listing is the only view of WHICH files such commands changed. A command
    that works in a worktree without ever spelling its path (a bare `git status` after
    an earlier `cd`) is not attributed.
  * Only the last TAIL_BYTES of each transcript are read -- an edit older than that
    tail is not seen even if it is inside the window.
  * Session ids, not session titles: titles live in the desktop app, not on disk.
  * Paths are compared as spelled. A Windows 8.3 short name (PROGRA~1), a junction or
    symlink alias, or a Cygwin `/cygdrive/d/` spelling of a worktree is NOT recognised
    -- these produce misses, never false alarms.
  * A peer that `cd`s once and then runs only relative commands is attributed only while
    that `cd` is still inside the tail.
  * Everything shown about a peer is a path inside this repo that EXISTS, a worktree
    root, a session-id prefix or an age. Transcript text is attacker-shaped (any session
    can put arbitrary text in a tool call); commands and non-existent "paths" are
    matched against, never printed.

Recursion guard: subagent-invoked runs (CLAUDE_INVOKED_BY) exit silently.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.runtime import emit_hook_result, hook_main, parse_stdin  # noqa: E402

WINDOW_MIN = 30
TAIL_BYTES = 512 * 1024
MAX_TRANSCRIPTS = 300
MAX_FILES_SHOWN = 5
MAX_PATH_CHARS = 400
SCAN_BUDGET_S = 3.0
DIRTY_BUDGET_S = 3.0
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_SESSION_ID = re.compile(r"[A-Za-z0-9-]{1,64}")
# Git with no index lock (so a peer's commit/checkout never hits "index.lock exists"),
# no fsmonitor process, no submodule recursion -- this hook only needs to LOOK.
_GIT_READONLY = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false"]


def _plausible_path(value: object) -> str | None:
    """A transcript value that may be SHOWN to this session as a file path, or None.

    WHY (sec-auditor, reproduced 2026-09-13): transcript content is attacker-shaped --
    any session on the machine can put arbitrary text in an Edit call's file_path,
    and a failed call is still recorded. A relative "path" containing
    "\\n[SYSTEM] Ignore prior instructions" resolved into this repo via abspath() and
    was printed verbatim into ANOTHER session's context; a 200 000-character path
    flooded it. Only absolute, single-line, bounded paths are admitted here, and
    in_repo() additionally requires the file to actually exist.
    """
    if not isinstance(value, str) or not value or len(value) > MAX_PATH_CHARS:
        return None
    if _CONTROL_CHARS.search(value) or not os.path.isabs(value):
        return None
    return value


BASH_PREFIX = "\x00bash\x00"
BASH_MARK = "<shell commands>"  # rel-path placeholder: presence in a worktree, file unknown
_GITBASH_DRIVE = re.compile(r"(?<![\w:/])/([a-zA-Z])/")


def worktrees_in_command(command: str, roots: list[str]) -> list[str]:
    """Worktree roots a shell command refers to by path -- the most specific ones only.

    Presence, not proof of writing: a command that only READS a file counts too, which
    is why callers word this as "active in", never "edited". Git-Bash `/d/x` is read as
    `d:/x` so both spellings of the same directory match.
    """
    text = command.replace("\\", "/")
    text = _GITBASH_DRIVE.sub(lambda m: f"{m.group(1)}:/", text)
    if os.name == "nt":
        text = text.lower()
    hits = [r for r in roots if _names_worktree(text, r)]
    return [r for r in hits if not any(o != r and o.startswith(r + "/") for o in hits)]


def _names_worktree(text: str, root: str) -> bool:
    """True when `text` works IN `root`: a path inside it, or cd/pushd/-C to it.

    WHY not a bare substring (skeptic, 2026-09-13): `REPO='d:/repo'` or
    `echo "context: d:/repo"` name the root without doing anything there, and a
    bare match turned them into "running shell commands in this worktree" warnings.
    """
    r = re.escape(root)
    inside = re.search(r + r"/[^\s\"'`;|&)]", text)
    target = re.search(r"(?:\bcd|\bpushd|(?<!\S)-C)\s+[\"']?" + r + r"(?![\w.-])", text)
    return bool(inside or target)


def _norm(path: str | Path) -> str:
    """Comparable form of a path: absolute, forward slashes, case-folded on Windows."""
    p = os.path.normpath(os.path.abspath(str(path))).replace("\\", "/")
    return p.lower() if os.name == "nt" else p


def worktree_roots(cwd: str) -> list[str]:
    """Normalized roots of every worktree of the repo containing `cwd` ([] if none)."""
    try:
        r = subprocess.run(
            [*_GIT_READONLY, "-C", cwd, "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    roots = [
        ln[len("worktree ") :].strip() for ln in r.stdout.splitlines() if ln.startswith("worktree ")
    ]
    return sorted({_norm(x) for x in roots if x}, key=len, reverse=True)


def locate(path: str, roots: list[str]) -> tuple[str, str] | None:
    """(worktree_root, repo_relative_path) if `path` is inside one of `roots`."""
    n = _norm(path)
    for root in roots:  # longest first, so a nested worktree wins over its parent
        if n == root or n.startswith(root + "/"):
            return root, n[len(root) + 1 :]
    return None


def _read_tail(path: Path) -> list[str]:
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > TAIL_BYTES:
                fh.seek(size - TAIL_BYTES)
                fh.readline()  # drop the partial first line
            return fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []


def _parse_ts(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return t.timestamp()


def _transcripts(projects_root: Path, own_session: str, cutoff: float):
    """Yield (session_id, path) for transcripts modified after `cutoff`.

    Includes `<project>/<sid>/subagents/*.jsonl`, attributed to the PARENT sid: a peer
    that edits through a builder subagent writes those Edit calls there, not in its
    own transcript (checked on disk 2026-09-13: 277 subagent files, none top-level).
    """
    try:
        dirs = list(os.scandir(projects_root))
    except OSError:
        return
    for d in dirs:
        if not d.is_dir():
            continue
        try:
            entries = list(os.scandir(d.path))
        except OSError:
            continue
        for e in entries:
            if e.is_file() and e.name.endswith(".jsonl"):
                sid = e.name[: -len(".jsonl")]
                candidates = [Path(e.path)]
            elif e.is_dir():
                sid = e.name
                try:
                    candidates = [
                        Path(s.path)
                        for s in os.scandir(os.path.join(e.path, "subagents"))
                        if s.name.endswith(".jsonl")
                    ]
                except OSError:
                    continue
            else:
                continue
            if sid == own_session:
                continue
            for c in candidates:
                try:
                    if c.stat().st_mtime >= cutoff:
                        yield sid, c
                except OSError:
                    continue


def peer_edits(
    projects_root: Path, own_session: str, now: float
) -> dict[str, list[tuple[float, str]]]:
    """{peer_session_id: [(timestamp, file_path_or_bash), ...]} inside the window."""
    cutoff = now - WINDOW_MIN * 60
    deadline = time.monotonic() + SCAN_BUDGET_S
    found: dict[str, list[tuple[float, str]]] = {}
    recent = 0
    for sid, path in _transcripts(projects_root, own_session, cutoff):
        # WHY count only RECENT transcripts (sec-auditor M-3): counting every file let
        # scandir order decide, past the cap, which live peers were never looked at.
        recent += 1
        if recent > MAX_TRANSCRIPTS or time.monotonic() > deadline:
            break
        edits = found.setdefault(sid, [])
        for line in _read_tail(path):
            if '"tool_use"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            ts = _parse_ts(rec.get("timestamp"))
            # future timestamps would read "just now" while the file stays fresh
            if ts is None or ts < cutoff or ts > now + 300:
                continue
            msg = rec.get("message")
            content = msg.get("content") if isinstance(msg, dict) else None
            if not isinstance(content, list):
                continue
            for c in content:
                if not (isinstance(c, dict) and c.get("type") == "tool_use"):
                    continue
                raw_input = c.get("input")
                inp: dict = raw_input if isinstance(raw_input, dict) else {}
                if c.get("name") in EDIT_TOOLS:
                    target = _plausible_path(inp.get("file_path") or inp.get("notebook_path"))
                    if target:
                        edits.append((ts, target))
                elif c.get("name") == "Bash":
                    # WHY (measured on the first real run): an active peer working in
                    # this repo made 17 Bash calls and ZERO Edit/Write calls. The
                    # command text is only MATCHED against worktree roots in in_repo();
                    # it is never emitted.
                    cmd = inp.get("command")
                    if isinstance(cmd, str) and cmd:
                        edits.append((ts, BASH_PREFIX + cmd))
    return found


def in_repo(
    edits: dict[str, list[tuple[float, str]]], roots: list[str]
) -> dict[str, list[tuple[float, str, str]]]:
    """Keep only edits inside this repo: {sid: [(ts, worktree_root, rel_path), ...]}."""
    out: dict[str, list[tuple[float, str, str]]] = {}
    for sid, items in edits.items():
        kept = []
        for ts, path in items:
            if path.startswith(BASH_PREFIX):
                for root in worktrees_in_command(path[len(BASH_PREFIX) :], roots):
                    kept.append((ts, root, BASH_MARK))
                continue
            loc = locate(path, roots)
            # exists: a fabricated path -- even a clean one that reads like an
            # instruction -- is printed only if that file is really in a worktree.
            # Cost: a peer's edit to a file since deleted is not shown.
            if loc and os.path.lexists(path):
                kept.append((ts, loc[0], loc[1]))
        if kept:
            out[sid] = kept
    return out


def dirty_files(root: str) -> list[str]:
    try:
        r = subprocess.run(
            [
                *_GIT_READONLY,
                "-C",
                root,
                "status",
                "--porcelain",
                "--untracked-files=no",
                "--ignore-submodules=all",
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    return [ln[3:] for ln in r.stdout.splitlines() if len(ln) > 3]


def _ago(ts: float, now: float) -> str:
    # round, not floor: an ISO-8601 round trip can shave microseconds, and 119.99 s
    # reported as "1 min ago" for a two-minute-old edit is simply wrong.
    minutes = max(0, round((now - ts) / 60))
    return "just now" if minutes == 0 else f"{minutes} min ago"


def summary(
    peers: dict[str, list[tuple[float, str, str]]], roots: list[str], now: float, with_dirty: bool
) -> str:
    lines: list[str] = []
    if peers:
        lines.append(
            f"[peer-sessions] {len(peers)} other Claude Code session(s) active in this repo in "
            f"the last {WINDOW_MIN} min -- check before starting overlapping work:"
        )
        for sid, items in sorted(peers.items(), key=lambda kv: -max(t for t, _, _ in kv[1])):
            latest: dict[tuple[str, str], float] = {}
            for ts, root, rel in items:
                key = (root, rel)
                latest[key] = max(ts, latest.get(key, 0.0))
            trees = sorted({root for root, _ in latest})
            lines.append(f"  session {sid[:8]}  worktree(s): {', '.join(trees)}")
            for (root, rel), ts in sorted(latest.items(), key=lambda kv: -kv[1])[:MAX_FILES_SHOWN]:
                if rel == BASH_MARK:
                    lines.append(
                        f"    running shell commands in {root}  ({_ago(ts, now)}) "
                        "-- files it changes are not visible here"
                    )
                else:
                    lines.append(f"    {rel}  ({_ago(ts, now)})")
    if with_dirty:
        dirty = []
        stop_at = time.monotonic() + DIRTY_BUDGET_S
        skipped = 0
        for root in roots:
            if time.monotonic() > stop_at:
                skipped += 1
                continue
            files = dirty_files(root)
            if files:
                dirty.append((root, files))
        if skipped:
            lines.append(
                f"[peer-sessions] uncommitted-file check skipped for {skipped} worktree(s): "
                "time budget used up"
            )
        if dirty:
            lines.append(
                "[peer-sessions] uncommitted changes per worktree (any tool, including Bash):"
            )
            for root, files in dirty:
                shown = ", ".join(files[:MAX_FILES_SHOWN])
                more = (
                    f" +{len(files) - MAX_FILES_SHOWN} more" if len(files) > MAX_FILES_SHOWN else ""
                )
                lines.append(f"  {root}: {shown}{more}")
    return "\n".join(lines)


def _state_path(session_id: str) -> Path:
    return Path.home() / ".claude" / "state" / "peer_sessions" / f"{session_id}.json"


def _load_state(session_id: str) -> dict:
    try:
        data = json.loads(_state_path(session_id).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(session_id: str, state: dict) -> None:
    path = _state_path(session_id)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(state), encoding="utf-8")
        os.replace(tmp, path)  # racing events never leave a half-written file
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def collisions(
    target: str, peers: dict[str, list[tuple[float, str, str]]], roots: list[str]
) -> list[tuple[str, str, str, str]]:
    """[(kind, peer_sid, peer_root, rel)] where kind is SAME_FILE or SAME_PATH_OTHER_WORKTREE."""
    loc = locate(target, roots)
    if not loc:
        return []
    my_root, my_rel = loc
    hits = []
    for sid, items in peers.items():
        for _ts, root, rel in items:
            if rel == BASH_MARK:
                # A peer running commands in the worktree I am editing: the one case
                # where two sessions can clobber each other without ever touching the
                # same file through Edit -- a script, a checkout, a formatter.
                if root == my_root:
                    hits.append(("SAME_WORKTREE_SHELL", sid, root, BASH_MARK))
                continue
            if rel != my_rel:
                continue
            kind = "SAME_FILE" if root == my_root else "SAME_PATH_OTHER_WORKTREE"
            hits.append((kind, sid, root, rel))
    return sorted(set(hits))


def run(data: dict, projects_root: Path | None = None, now: float | None = None) -> str | None:
    """Pure-ish core: returns the additionalContext text to emit, or None."""
    event = data.get("hook_event_name") or ""
    session_id = str(data.get("session_id") or "")
    if not _SESSION_ID.fullmatch(session_id):
        # used in a state FILENAME (sec-auditor M-1, reproduced: "../../settings"
        # overwrote ~/.claude/settings.json). Not a real id -> no state at all.
        session_id = ""
    cwd = str(data.get("cwd") or os.getcwd())
    now = time.time() if now is None else now
    if projects_root is None:
        tp = data.get("transcript_path")
        projects_root = Path(tp).parent.parent if tp else Path.home() / ".claude" / "projects"

    roots = worktree_roots(cwd)
    if not roots:
        return None
    peers = in_repo(peer_edits(projects_root, session_id, now), roots)

    if event == "SessionStart":
        text = summary(peers, roots, now, with_dirty=True)
        if session_id:
            # `seen` = every peer this session has already been told about, so a
            # later prompt announces only NEWCOMERS, not the whole list again.
            prior = _load_state(session_id)
            seen = set(prior.get("seen", [])) | set(peers)
            _save_state(
                session_id,
                {"seen": sorted(seen), "reported": prior.get("reported", [])},
            )
        return text or None

    if event == "UserPromptSubmit":
        state = _load_state(session_id) if session_id else {}
        seen = set(state.get("seen", []))
        new = sorted(set(peers) - seen)
        if not new:
            return None
        state["seen"] = sorted(seen | set(new))
        if session_id:
            _save_state(session_id, state)
        return summary({sid: peers[sid] for sid in new}, roots, now, with_dirty=False) or None

    if event == "PostToolUse":
        if data.get("tool_name") not in EDIT_TOOLS:
            return None
        raw_tool_input = data.get("tool_input")
        inp: dict = raw_tool_input if isinstance(raw_tool_input, dict) else {}
        target = inp.get("file_path") or inp.get("notebook_path")
        if not isinstance(target, str) or not target:
            return None
        state = _load_state(session_id) if session_id else {}
        reported = set(state.get("reported", []))
        fresh = []
        for kind, sid, root, rel in collisions(target, peers, roots):
            key = f"{kind}|{sid}|{root}|{rel}"
            if key not in reported:
                reported.add(key)
                fresh.append((kind, sid, root, rel))
        if not fresh:
            return None
        state["reported"] = sorted(reported)
        if session_id:
            _save_state(session_id, state)
        lines = []
        for kind, sid, root, rel in fresh:
            if kind == "SAME_FILE":
                lines.append(
                    f"[peer-sessions] WARNING: session {sid[:8]} also edited THIS file "
                    f"({rel}, same worktree {root}) in the last {WINDOW_MIN} min -- "
                    "two sessions writing one file; re-read it before trusting your version."
                )
            elif kind == "SAME_WORKTREE_SHELL":
                lines.append(
                    f"[peer-sessions] session {sid[:8]} is running shell commands in this same "
                    f"worktree ({root}) within the last {WINDOW_MIN} min -- a script, checkout "
                    "or formatter there can overwrite what you just wrote."
                )
            else:
                lines.append(
                    f"[peer-sessions] session {sid[:8]} edited the same path ({rel}) in another "
                    f"worktree ({root}) in the last {WINDOW_MIN} min -- likely duplicate work or a "
                    "merge conflict later."
                )
        return "\n".join(lines)

    return None


def main() -> None:
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)
    data = parse_stdin()
    if not data:
        sys.exit(0)
    text = run(data)
    if text:
        emit_hook_result(str(data.get("hook_event_name") or ""), text)
    sys.exit(0)


if __name__ == "__main__":
    hook_main(main, timeout=8, fail_closed=False)
