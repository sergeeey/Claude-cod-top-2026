#!/usr/bin/env python3
"""Redeploy ONLY the live-install drift that is provably safe to overwrite.

WHY this exists, measured 2026-09-13 before anything was written:
hooks/live_drift_guard.py reports drift between this repo and the live
~/.claude install every session, and every fix so far has been done by hand.
The obvious reading is "a detector without a fixer". That reading is wrong,
and the way it is wrong is the whole design of this script:

  * Two fixers ALREADY exist. scripts/sync_config.py copies hooks/rules/agents
    over the live install unconditionally and rmtree()s every skill directory;
    scripts/deploy_p1_hooks.py copies a hardcoded hook list the same way.
    Neither asks which side of the drift is newer.
  * On the maintainer's machine that day, live hooks/iteration_guard.py carried
    a fix (_stop_agent_type, 2026-09-12) that was applied to the live file and
    never ported to this repo. deploy_p1_hooks.py lists iteration_guard -- one
    run would have silently reverted that fix and reopened the bug it closed.
    sync_config.py would also have wiped the live-only `triggers:` field that
    keyword_router.py reads, from ~100 skills.

So the missing piece was never copying. It is DIRECTION: telling "the live
file is an older version of what main ships" (safe to overwrite) apart from
"the live file cannot be shown to be that" (overwriting may destroy work).

THE REFERENCE IS origin/main, NEVER THE CHECKOUT (independent review,
2026-09-13 -- skeptic and sec-auditor found this separately). The first draft
classified against `git log HEAD` and wrote the HEAD blob, guarded by "HEAD
contains origin/main". That guard passes on every feature branch, so a branch
that reverted a hardened hook would label the correctly-deployed live copy
"older" and write the weaker version live; a branch with unreviewed commits
would deploy them. Now the origin/main commit is resolved ONCE to a SHA, every
comparison and every write uses that SHA, and --apply additionally refuses
unless HEAD *is* that commit (candidates come from live_drift_guard, which
compares against the working tree -- a different checkout lists different
files).

STALE requires ORDER, not just a match. "Live equals some older blob" is not
enough: if main went buggy -> fixed -> buggy (a revert) and the live copy kept
"fixed", that content IS an older blob, and overwriting it destroys a
deliberate choice. So STALE means: the live content's LAST appearance on
main's first-parent history is older than the current content's FIRST
appearance. A revert back to an earlier version fails that test and is
reported UNPROVEN. This is conservative on purpose -- some genuinely stale
files in revert-heavy histories will be UNPROVEN, and a human decides.

UNPROVEN is never written. It does not claim "live is newer" (unprovable
either way); it claims "not provably safe".

Also refused, as UNPROVEN, before any comparison: a live install ROOT that is
itself a link, any path component under it that is a symlink, junction or other
reparse point, and any path that resolves outside the live install.
`install.sh --link` creates exactly such links, and Path.write_bytes follows
them -- the first draft overwrote files in another checkout this way.

Writes are atomic (exclusively-created temp file + os.replace, which replaces a
path rather than following it), preceded by an exclusively-created backup and a
re-check that the live file has not changed since it was classified, and are
verified against the pinned blob id rather than against the bytes just written.
On a failed write, only files that call created are removed; live is untouched.
Residual, accepted: an edit landing in the milliseconds between that re-check and
os.replace is not caught. This is a CLI a person runs by hand, not a daemon.

Detection is NOT re-implemented here: candidates come from
live_drift_guard.py's own find_drift / find_rules_drift /
find_shipped_artifact_drift. That hook stays read-only (SessionStart, Green by
construction); the writing lives here, in a CLI a human runs on purpose.

Scope, deliberately narrow:
  * hooks/, rules/, agents/, commands/ -- single-file artifacts.
  * skills/ is EXCLUDED: live skills carry intentional live-only enrichment
    (see live_drift_guard._strip_generated_fields), and the unit is a directory.
  * settings.json event wiring is EXCLUDED: it mixes shareable registrations
    with personal keys.
  * Files shipped but absent live are EXCLUDED: install.sh owns first install,
    and #425 showed "missing" can mean a wrong install mapping.
  * Renames are not followed. Detection is path-based, so an old path that exists
    only live never becomes a candidate, and history is read per path without
    --follow -- a renamed file's pre-rename versions are invisible, which can only
    turn a would-be STALE into UNPROVEN, never the reverse.

Usage:
    python scripts/redeploy_drift.py           # preview: classify, write nothing
    python scripts/redeploy_drift.py --apply   # overwrite STALE files only, with backups

Run it from a checkout whose HEAD is origin/main (`git fetch` first; this
script never fetches). "origin/main" means the LOCAL remote-tracking ref: anyone
who can already write to the checkout can move it or repoint the remote. That is
accepted -- the threat is the maintainer's own normal workflow, not an attacker
who already owns the checkout -- but it is not a signature check.

Exit codes: 0 ok (including "nothing to do"); 1 --apply refused or a write
failed; 2 not runnable here (not this repo / no live install).
"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "hooks"))

import live_drift_guard as ldg  # noqa: E402  (path set up just above)

MAIN_REF = "refs/remotes/origin/main"

STALE = "STALE"
UNPROVEN = "UNPROVEN"
CURRENT = "CURRENT"


@dataclass
class Item:
    rel: str  # repo-relative path, forward slashes, e.g. "hooks/x.py"
    status: str
    detail: str = ""
    live_sha256: str = ""  # of the live bytes as classified; re-checked before any write


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    # GIT_LITERAL_PATHSPECS: a path like `hooks/[ab].py` must not be read as a
    # glob that also matches hooks/a.py's history (sec-auditor L1, reproduced).
    env = {**os.environ, "GIT_LITERAL_PATHSPECS": "1"}
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            timeout=60,
            env=env,
        )
    except subprocess.TimeoutExpired:
        # Any non-zero result already means "not provable" to every caller.
        return subprocess.CompletedProcess(list(args), 124, b"", b"git timed out")


def _lf(data: bytes) -> bytes:
    # WHY normalize before comparing: blobs are stored LF, while a file copied
    # out of a Windows checkout can be CRLF. Without this, every CRLF live copy
    # matches no historical blob and is misfiled UNPROVEN -- the tool would
    # refuse to fix exactly the files it exists to fix.
    return data.replace(b"\r\n", b"\n")


def _git_blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()  # noqa: S324 (git object id)


def resolve_main(root: Path) -> str | None:
    r = _git(root, "rev-parse", "--verify", "--quiet", f"{MAIN_REF}^{{commit}}")
    sha = r.stdout.decode().strip()
    return sha if r.returncode == 0 and sha else None


def blob_at(root: Path, commit: str, rel: str) -> tuple[str, bytes] | None:
    rid = _git(root, "rev-parse", "--verify", "--quiet", f"{commit}:{rel}")
    blob = rid.stdout.decode().strip()
    if rid.returncode != 0 or not blob:
        return None
    data = _git(root, "cat-file", "blob", blob)
    return (blob, data.stdout) if data.returncode == 0 else None


def main_history(root: Path, commit: str, rel: str) -> list[str]:
    """Blob id of `rel` after each first-parent commit that touched it, NEWEST first."""
    # --diff-merges=first-parent is explicit, not left to --first-parent's implied
    # default (git >= 2.31): a change that reached main THROUGH a merge commit must
    # appear here, while a PR branch's intermediate commits must not -- they were
    # never main's content. On a git too old for the flag, the call fails and every
    # file comes out UNPROVEN: useless, but never unsafe.
    r = _git(
        root,
        "log",
        "--first-parent",
        "--diff-merges=first-parent",
        "--format=",
        "--raw",
        "--no-abbrev",
        commit,
        "--",
        rel,
    )
    seq: list[str] = []
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        if not line.startswith(":"):
            continue
        parts = line.split()
        if len(parts) >= 4:
            seq.append(parts[3])  # post-commit blob; all zeros for a deletion
    return seq


def _is_link(path: Path) -> bool:
    """Symlink, junction, or any other Windows reparse point.

    WHY not just is_symlink() + os.path.isjunction: isjunction only exists from
    Python 3.12, and CI runs 3.11, where a junction is invisible to is_symlink().
    The reparse-point attribute catches both on every version. It would also
    refuse a cloud-placeholder file -- conservative, which is the right direction.
    """
    try:
        if path.is_symlink():
            return True
        isjunction = getattr(os.path, "isjunction", None)
        if isjunction is not None and isjunction(path):
            return True
        attrs = getattr(os.lstat(path), "st_file_attributes", 0)
        return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    except OSError:
        return False


def unsafe_live_path(live_file: Path, claude_home: Path) -> str | None:
    """Why this path must not be written, or None when it is an ordinary file inside home."""
    # The live install ROOT is checked too (sec-auditor round 2, M-2, reproduced
    # with `mklink /J`): resolve() follows a linked home, so a file under it passed
    # the containment check below while every write landed in the link's target.
    if _is_link(claude_home):
        return f"the live install root itself is a link ({claude_home})"
    try:
        home = claude_home.resolve()
        rel_parts = live_file.relative_to(claude_home).parts
    except (OSError, ValueError):
        return "not under the live install"
    probe = claude_home
    for part in rel_parts:
        probe = probe / part
        if _is_link(probe):
            return f"symlink/junction at {probe}"
    try:
        if not live_file.resolve().is_relative_to(home):
            return "resolves outside the live install"
    except OSError as e:
        return f"cannot resolve: {e}"
    if not live_file.is_file():
        return "not a regular file"
    return None


def classify(root: Path, rel: str, live_file: Path, main_sha: str, claude_home: Path) -> Item:
    why = unsafe_live_path(live_file, claude_home)
    if why:
        return Item(rel, UNPROVEN, f"refused: {why}")
    try:
        raw = live_file.read_bytes()
    except OSError as e:
        return Item(rel, UNPROVEN, f"live file unreadable: {e}")
    live, live_sha = _lf(raw), hashlib.sha256(raw).hexdigest()

    current = blob_at(root, main_sha, rel)
    if current is None:
        return Item(rel, UNPROVEN, "not on origin/main", live_sha)
    _current_id, current_bytes = current
    if live == _lf(current_bytes):
        return Item(rel, CURRENT, "already matches origin/main", live_sha)

    seq = main_history(root, main_sha, rel)
    content: dict[str, bytes] = {}

    def text_of(blob: str) -> bytes:
        if blob not in content:
            r = _git(root, "cat-file", "blob", blob)
            content[blob] = _lf(r.stdout) if r.returncode == 0 else b"\0unreadable"
        return content[blob]

    live_last = next((i for i, b in enumerate(seq) if b.strip("0") and text_of(b) == live), None)
    if live_last is None:
        return Item(rel, UNPROVEN, "live matches no version origin/main ever shipped", live_sha)
    # By CONTENT, not blob id (sec-auditor round 2, M-1, reproduced): if main once
    # stored the current text with CRLF, that earlier copy has a different blob id,
    # the revert looks like a first appearance, and a live hardened version passes
    # as "older" -- the exact case the ordering rule exists to refuse.
    current_norm = _lf(current_bytes)
    current_first = max(
        (i for i, b in enumerate(seq) if b.strip("0") and text_of(b) == current_norm),
        default=None,
    )
    if current_first is None or live_last <= current_first:
        return Item(
            rel,
            UNPROVEN,
            "live matches a version main shipped AFTER the current one first appeared "
            "-- main moved back (revert?); not provably stale",
            live_sha,
        )
    return Item(rel, STALE, f"live equals older main blob {seq[live_last][:10]}", live_sha)


def candidates(root: Path, claude_home: Path) -> tuple[list[tuple[str, Path]], int]:
    """(repo_rel, live_path) pairs for drifted single-file artifacts, plus the
    count of drifted skills that are reported but deliberately never handled."""
    out: list[tuple[str, Path]] = []
    live_hooks = claude_home / "hooks"
    if live_hooks.is_dir():
        for rel in ldg.find_drift(root / "hooks", live_hooks):
            rel = Path(rel).as_posix()
            out.append((f"hooks/{rel}", live_hooks / rel))
    live_rules = claude_home / "rules"
    if live_rules.is_dir() and (root / "rules").is_dir():
        _missing, drifted = ldg.find_rules_drift(root / "rules", live_rules)
        for rel in drifted:
            out.append((f"rules/{rel}", live_rules / rel))
    _missing_live, drifted_art, _enriched = ldg.find_shipped_artifact_drift(root, claude_home)
    skipped_skills = 0
    for label in drifted_art:
        kind, _, name = label.partition(": ")
        if kind == "agent":
            out.append((f"agents/{name}", claude_home / "agents" / name))
        elif kind == "command":
            out.append((f"commands/{name}", claude_home / "commands" / name))
        else:
            skipped_skills += 1
    return out, skipped_skills


def head_is_main(root: Path, main_sha: str) -> tuple[bool, str]:
    head = _git(root, "rev-parse", "--verify", "--quiet", "HEAD").stdout.decode().strip()
    if head == main_sha:
        return True, ""
    return False, (
        "HEAD is not origin/main -- the drift candidates come from this checkout's "
        "files, so a feature branch or a stale checkout lists the wrong ones"
    )


def apply_item(
    root: Path, item: Item, live_file: Path, main_sha: str, claude_home: Path, stamp: str
) -> str | None:
    """Atomically overwrite one STALE file from the pinned origin/main blob."""
    why = unsafe_live_path(live_file, claude_home)
    if why:
        return f"refused at write time: {why}"
    blob = blob_at(root, main_sha, item.rel)
    if blob is None:
        return "origin/main blob vanished"
    blob_id, data = blob
    try:
        before = live_file.read_bytes()
    except OSError as e:
        return f"cannot re-read live file: {e}"
    if hashlib.sha256(before).hexdigest() != item.live_sha256:
        return "live file changed since it was classified -- not written"

    backup = live_file.with_name(f"{live_file.name}.bak-redeploy-{stamp}")
    tmp = live_file.with_name(f".{live_file.name}.redeploy-tmp-{stamp}")
    created: list[Path] = []
    try:
        _write_new(backup, before)
        created.append(backup)
        _write_new(tmp, data, sync=True)
        created.append(tmp)
        os.replace(tmp, live_file)
    except OSError as e:
        # Live is untouched on every path through here, so nothing THIS call made
        # has a reason to exist -- a leftover backup is an older copy of a guard in
        # the hooks directory (L-3, reproduced). Only files this call created are
        # removed: the first version of this cleanup unlinked by NAME, so when
        # exclusive create refused a file already sitting at the temp name, the
        # "cleanup" deleted that unrelated file -- caught by its own regression test.
        for leftover in created:
            try:
                leftover.unlink(missing_ok=True)
            except OSError:
                pass
        return f"write failed, live file left as it was: {e}"
    try:
        written = live_file.read_bytes()
    except OSError as e:  # L-1: report it as a failure for THIS file, keep the run going
        return f"replaced, but post-write verification could not read the file: {e}"
    if _git_blob_id(written) != blob_id:
        return "post-write content is not the origin/main blob"
    return None


def _write_new(path: Path, data: bytes, sync: bool = False) -> None:
    """Create `path` exclusively and write `data`.

    O_EXCL (sec-auditor round 2, L-2): write_bytes/open("wb") follow and truncate
    whatever already sits at that name -- including a symlink, whose target would
    receive the bytes and which os.replace would then move onto the live path.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        if sync:
            fh.flush()
            os.fsync(fh.fileno())


def run(root: Path, claude_home: Path, apply: bool) -> int:
    main_sha = resolve_main(root)
    if main_sha is None:
        print(
            "[redeploy] no local origin/main ref -- nothing can be proven stale.", file=sys.stderr
        )
        return 1 if apply else 0
    pairs, skipped_skills = candidates(root, claude_home)
    items = [(classify(root, rel, live, main_sha, claude_home), live) for rel, live in pairs]

    for status in (STALE, UNPROVEN, CURRENT):
        group = [(i, p) for i, p in items if i.status == status]
        if not group:
            continue
        print(f"[redeploy] {status} ({len(group)}):")
        for i, _p in group:
            print(f"  {i.rel}  -- {i.detail}")
    if skipped_skills:
        print(
            f"[redeploy] {skipped_skills} drifted skill(s) not handled -- out of scope "
            "(live skills carry intentional enrichment; see this script's docstring)."
        )
    stale = [(i, p) for i, p in items if i.status == STALE]
    if any(i.status == UNPROVEN for i, _p in items):
        print(
            "[redeploy] UNPROVEN files are never written. Decide by hand: port the live "
            "change into the repo, or discard it -- e.g. `diff <repo file> <live file>`."
        )
    if not stale:
        print("[redeploy] nothing safe to redeploy.")
        return 0
    if not apply:
        print(
            "[redeploy] preview only -- re-run with --apply to overwrite "
            f"{len(stale)} STALE file(s)."
        )
        return 0

    ok, why = head_is_main(root, main_sha)
    if not ok:
        print(f"[redeploy] --apply REFUSED: {why}.", file=sys.stderr)
        return 1

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    failed = 0
    for item, live in stale:
        err = apply_item(root, item, live, main_sha, claude_home, stamp)
        if err:
            failed += 1
            print(f"[redeploy] FAILED {item.rel}: {err}", file=sys.stderr)
        else:
            print(f"[redeploy] redeployed {item.rel} (backup: *.bak-redeploy-{stamp})")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not ldg.is_this_repo(REPO):
        print("[redeploy] not run from this repository", file=sys.stderr)
        return 2
    claude_home = ldg.resolve_claude_home()
    if claude_home is None:
        print("[redeploy] no live install found", file=sys.stderr)
        return 2
    return run(REPO, claude_home, apply="--apply" in argv)


if __name__ == "__main__":
    sys.exit(main())
