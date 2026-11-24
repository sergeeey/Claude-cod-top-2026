"""State files, locking, audit/rotation for Claude Code hooks.

WHY this file exists (split from hooks/utils.py, HS-01 in
artifacts/architecture-coupling/hotspots.json): utils.py's fan-in was 74
(68 hooks + 13 tests import it directly), making every bug here ripple
across 60+ hooks. Splitting by responsibility localizes blast radius.
See hooks/utils.py for the facade that keeps `from utils import X` working.
"""

import contextlib
import json
import os
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

from .security import redact_secrets, sanitize_text

# --- Circuit Breaker shared constants ----------------------------------------
# WHY: both mcp_circuit_breaker.py and mcp_circuit_breaker_post.py need
# identical values. Single source of truth prevents threshold drift.
CB_FAILURE_THRESHOLD = 3
CB_RECOVERY_TIMEOUT = 60  # seconds
CB_STATE_FILE = Path.home() / ".claude" / "cache" / "mcp_circuit_state.json"


def load_json_state(path: Path) -> dict:
    """Load JSON state file, returning empty dict on any error.

    WHY: Duplicated in mcp_circuit_breaker and mcp_circuit_breaker_post
    (identical load_state functions).
    """
    if not path.exists():
        return {}
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


# WHY (audit 2026-10-17, F3): on Windows os.replace() fails while another handle holds the
# destination open (a reader in another process or thread). Under continuous readers that
# window outlasts a few hundred milliseconds: a 0.6 s attempt budget lost 53 of 100 saves
# (artifacts/concurrency-stress-baseline.json, S6). The budget is measured in time, not in
# attempts, and stays far below the 30 s hook timeout.
_REPLACE_BUDGET_S = 4.0


def replace_with_retry(src: str | Path, dst: Path) -> None:
    """os.replace() that rides out a transient PermissionError (audit 2026-10-17, F3).

    The repo's vector_store and expert_registry already retry this case for their own
    writes. A failure that outlasts the budget is raised to the caller, which decides
    how to react.
    """
    deadline = time.monotonic() + _REPLACE_BUDGET_S
    delay = 0.01
    while True:
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.1)


def _temp_path_for(path: Path) -> Path:
    """Unique sibling temp name for an atomic write.

    WHY (audit 2026-10-17, F5): the name used to carry the PID only, so threads of one
    process shared it. One thread's rename then removed the file another thread was still
    writing: 319 of 320 writes raised with 8 threads (artifacts/concurrency-stress-baseline.json,
    S4). Thread id and a random suffix make the name unique per call. The ".tmp." infix is
    kept, because leftover checks look for it.
    """
    return path.with_name(
        f"{path.name}.tmp.{os.getpid()}.{threading.get_ident()}.{os.urandom(4).hex()}"
    )


def atomic_write_json(path: Path, data: object, *, indent: int | None = None) -> None:
    """Atomically persist data as JSON at path.

    WHY: plain open("w") + json.dump truncates the file on write start;
    a kill-9 or OOM between truncation and final flush produces an empty
    or partial file — data loss on every state file (circuit breaker state,
    wiki entries, memory snapshots). tmp + fsync + os.replace is atomic on
    POSIX and best-effort on Windows (os.replace is atomic within the same
    volume). A unique temp name per call keeps concurrent writers apart, in
    other processes and in threads of one process (audit 2026-10-17, F5).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _temp_path_for(path)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=indent, ensure_ascii=False))
            f.flush()
            os.fsync(f.fileno())
        replace_with_retry(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically write a text file. Same guarantees as atomic_write_json."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _temp_path_for(path)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        replace_with_retry(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def save_json_state(path: Path, state: dict) -> None:
    """Save dict as JSON state file, creating parent dirs.

    WHY: Duplicated in mcp_circuit_breaker and mcp_circuit_breaker_post.
    Delegates to atomic_write_json for crash-safe writes.
    """
    atomic_write_json(path, state, indent=2)


@contextlib.contextmanager
def file_lock(
    lock_path: Path,
    timeout: float = 2.0,
    poll_interval: float = 0.05,
    stale_after: float = 30.0,
):
    """Cross-platform exclusive lock via an atomic O_CREAT|O_EXCL sentinel file.

    WHY not fcntl/msvcrt: those are platform-specific (POSIX-only / Windows-only
    respectively) and hooks in this repo run on both. os.open(path, O_CREAT |
    O_EXCL) raises FileExistsError atomically on both platforms when the file
    already exists, giving true mutual exclusion using only the stdlib.

    WHY this exists: atomic_write_json/save_json_state already make a single
    WRITE crash-safe, but do nothing for a read-modify-write sequence spanning
    multiple calls (load_json_state(...) -> mutate the dict -> save_json_state(...)).
    Two concurrent hook invocations can both read the same "before" state and
    then race to write, silently losing one side's update (concretely: the MCP
    circuit breaker's failure counter under-counting failures, or two HALF_OPEN
    probes both slipping through instead of one).

    WHY stale_after (cross-model review, 2026-07-06): if a process is killed
    (SIGKILL, hard crash) while holding the lock, `finally` never runs and the
    lock file is never cleaned up. Without staleness detection, every future
    call would hit FileExistsError, wait out the full `timeout`, and yield
    False forever -- silently and permanently disabling the exact race
    protection this exists to provide, with no visible symptom. A lock file
    older than `stale_after` (default far longer than any real read-modify-
    write critical section in this repo, which is a small JSON read+write) is
    treated as abandoned: removed so a waiting process can retake it.

    Yields True if the lock was acquired, False if it timed out.

    Caller contract on timeout (revised 2026-07-07 -- see note below): the
    ORIGINAL intent was best-effort, proceed-without-exclusivity semantics, on
    the theory that a hook must never hang or crash the tool call it's
    guarding. In practice every current caller (doc_registry.py,
    expert_registry.py's `_locked()`, vector_store.py, moc_autolink.py,
    observation_capture.py) instead does
        `with file_lock(path, timeout=15.0) as acquired:
             if not acquired: raise TimeoutError(...)`
    because silently proceeding without the lock defeats the entire purpose
    of taking it -- a "best-effort" caller that ignores `False` reintroduces
    the exact lost-update race this function exists to prevent (confirmed via
    a forced `timeout=0.001` reproduction, 2026-07-07). Each of those 5
    callers wraps its own call site in a broader `try/except Exception` (or
    relies on `hook_main()`'s generic handler) so the raise is always caught
    before it can crash a hook -- `file_lock()` itself never swallows the
    timeout, the CALLER decides how to react to it. New callers should raise
    on `False` too, not silently proceed, unless they have a specific reason
    the old best-effort behavior is actually safe for their case.
    """
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except (FileExistsError, PermissionError):
            # WHY PermissionError too (found by a real concurrency-test
            # failure while adding stale-lock reaping, 2026-07-06): on
            # Windows, a file mid-deletion by another thread can make a
            # concurrent O_CREAT|O_EXCL open() raise PermissionError instead
            # of FileExistsError -- NTFS can leave a file "pending delete"
            # for a brief window rather than removing it atomically. Treat
            # it identically to "someone else currently holds this lock."
            try:
                age = time.time() - lock_path.stat().st_mtime
            except FileNotFoundError:
                age = 0.0  # released between our failed open() and this stat()
            if age >= stale_after:
                # WHY unlink-then-retry-after-a-sleep, not "assume ours now":
                # another waiter may win the recreate race first -- that's
                # fine, O_EXCL still enforces exclusivity. This only clears
                # an abandoned lock so *someone* can proceed, instead of every
                # waiter timing out against a lock nobody will ever release.
                # WHY suppress PermissionError (audit 2026-10-17, F4a): on Windows a
                # stalled holder that still has the file open makes unlink() fail.
                # That means "still held", not a reason to crash the waiting hook.
                with contextlib.suppress(PermissionError):
                    lock_path.unlink(missing_ok=True)
            if time.time() >= deadline:
                yield False
                return
            # WHY always sleep here, never retry with a zero-delay continue:
            # a tight busy-loop under real contention (many threads racing on
            # the same lock file) is exactly what triggered the Windows
            # PermissionError above in the first place -- removing the sleep
            # on any retry path increases contention instead of easing it.
            time.sleep(poll_interval)
    # WHY a token (audit 2026-10-17, F4b): after a reap the lock file can belong to another
    # holder. Release deletes the file only while it still carries this holder's token.
    token = os.urandom(16).hex().encode("ascii")
    try:
        os.write(fd, token)
    except OSError:
        os.close(fd)
        with contextlib.suppress(OSError):
            lock_path.unlink(missing_ok=True)
        raise
    try:
        yield True
    finally:
        os.close(fd)
        _release_lock_file(lock_path, token)


def _release_lock_file(lock_path: Path, token: bytes) -> None:
    """Delete the lock file only while it still carries this holder's token.

    WHY (audit 2026-10-17, F4b): a stalled holder can be reaped, and then the file belongs
    to another holder. An unconditional unlink here would remove that holder's lock. A failed
    unlink is not an error: on Windows another handle may still be open, and the next waiter
    reaps the file once it is stale.

    Residual race, accepted and recorded rather than closed: between the read and the unlink,
    a waiter can reap the file and create its own. That window is microseconds and opens only
    after the holder has stalled past stale_after.
    """
    try:
        if lock_path.read_bytes() != token:
            return
        lock_path.unlink(missing_ok=True)
    except OSError:
        pass


def _append_line(path: Path, line: str) -> None:
    """Append one telemetry line under the file's own lock (audit 2026-10-17, F7).

    WHY: an append seeks to the end and then writes. On Windows that pair is not atomic across
    processes, so two writers can seek to the same end and one line overwrites the other:
    116 of 900 lines were lost with 6 processes (artifacts/concurrency-stress-baseline.json, S3).
    The earlier comment relied on PIPE_BUF, which governs pipes, not regular files.

    On lock timeout the line is skipped, the same policy as verdict_logger.py: telemetry must
    never block a hook, and a holder stuck for the whole timeout is an exceptional case.
    """
    with file_lock(path.with_name(path.name + ".lock"), timeout=5.0) as acquired:
        if not acquired:
            return
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)


def update_text_locked(
    path: Path,
    transform: Callable[[str | None], str],
    *,
    timeout: float = 15.0,
    writer: Callable[[Path, str], None] | None = None,
) -> None:
    """Read, change and rewrite a text file under the file's own lock (audit 2026-10-17, F6).

    WHY: atomic_write_text() stops a torn file, but not a lost update. Two callers that each
    read, change and write can both start from the same text, and the second write drops the
    first caller's change. post_commit_memory.py did exactly that for decisions.md, the daily
    commit archive and activeContext.md. The read and the write belong inside one lock.

    transform receives the current text, or None when the file does not exist yet, and returns
    the new text. A file that exists but cannot be read raises, so it is never overwritten from
    a partial view. On lock timeout the write still happens, without the lock: the old race, never
    a silently dropped change.

    writer defaults to atomic_write_text. A caller that passes its own module-level name lets
    that name stay the single point of control for its writes (tests patch it there).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write = writer if writer is not None else atomic_write_text
    with file_lock(path.with_name(path.name + ".lock"), timeout=timeout) as acquired:
        if not acquired:
            print(f"[state] {path.name}: lock timeout, writing without the lock", file=sys.stderr)
        try:
            current: str | None = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            current = None
        write(path, transform(current))


def rotate_log_if_large(path: Path, max_bytes: int = 5 * 1024 * 1024, backups: int = 3) -> None:
    """Rotate `path` to `path.1` (shifting older backups up) before it grows past max_bytes.

    WHY: hook_triggers.jsonl, model_usage.jsonl, hook_events.jsonl, audit.log,
    and sessions.log are append-only and were never rotated — on a long-lived
    machine they grow without bound (model_usage.jsonl appends once per tool
    call). This is a plain size-based logrotate equivalent, checked before each
    append so no background process or cron job is needed.

    Behavior
    --------
    * Checked BEFORE the write that would grow the file, so a single append
      never pushes the file past max_bytes by more than one line's worth.
    * Rotates by shifting existing backups: path.(backups-1) -> path.backups,
      ..., path -> path.1. The oldest backup (path.<backups>) is discarded.
    * A file under max_bytes (including one that doesn't exist yet) is left
      untouched — this only ever acts on a file that has already grown past
      the threshold, never on today's normal-sized logs.
    * Silent on failure (OSError) — log rotation must never break a hook.

    Known limitations (accepted, not bugs):
    * TOCTOU race under concurrent hook invocations (two Claude Code sessions
      on the same machine): both can pass the size check before either
      rotates. On POSIX the second `rename` silently clobbers the first's
      `.1` backup (one generation lost, no crash). On Windows it raises
      `FileExistsError`, caught by the `except OSError` below — a missed
      rotation, not data loss or a crash. Acceptable for a fail-open,
      best-effort log; not worth a lock file for this use case.
    * Rotation is rename-based, so a process doing `tail -f` on one of these
      logs will stop seeing new lines after a rotation (the fd it holds now
      points at the renamed `.1` file). Inherent to size-based log rotation,
      not specific to this implementation.
    """
    try:
        if not path.exists() or path.stat().st_size < max_bytes:
            return
        oldest = path.with_name(f"{path.name}.{backups}")
        if oldest.exists():
            oldest.unlink()
        for i in range(backups - 1, 0, -1):
            src = path.with_name(f"{path.name}.{i}")
            if src.exists():
                src.rename(path.with_name(f"{path.name}.{i + 1}"))
        path.rename(path.with_name(f"{path.name}.1"))
    except OSError:
        pass


def log_audit_event(event_type: str, details: str) -> None:
    """Append an audit event to ~/.claude/logs/audit.log.

    WHY: config_audit.py and other hooks need consistent audit logging.
    Centralized here to ensure uniform format and directory creation.
    """
    from datetime import UTC, datetime

    log_dir = Path.home() / ".claude" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "audit.log"
    rotate_log_if_large(log_file)
    timestamp = datetime.now(UTC).isoformat()
    entry = {"timestamp": timestamp, "event": event_type, "details": details}
    try:
        _append_line(log_file, json.dumps(entry) + "\n")
    except OSError:
        pass


# --- Hook Trigger Telemetry --------------------------------------------------
# WHY: without per-trigger telemetry, hooks like validation_theater_guard and
# evidence_guard cannot prove precision/recall on real sessions. Audit log
# captures timing only — this function records WHAT pattern fired and on
# WHICH sample, so we can compute metrics later (true positives, false
# positives, distribution per session, drift over time).
#
# Cascading-hallucination context (2026-05-03): two consecutive Claude
# sessions made unverified claims about hook events count without grepping
# settings.json. Telemetry would have anchored those claims to actual
# trigger logs instead of guesses.

HOOK_TRIGGERS_LOG = Path.home() / ".claude" / "logs" / "hook_triggers.jsonl"


def log_hook_trigger(
    hook_name: str,
    trigger_type: str,
    action: str,
    sample: str = "",
    session_id: str | None = None,
) -> None:
    """Record one hook trigger to ~/.claude/logs/hook_triggers.jsonl.

    Parameters
    ----------
    hook_name : str
        Stable hook identifier, e.g. ``"validation_theater_guard"``.
    trigger_type : str
        Pattern category that fired, e.g. ``"perfect_score"``,
        ``"synthetic_data"``, ``"missing_evidence_marker"``.
    action : str
        What the hook did. One of: ``"warning"``, ``"block"``, ``"sanitize"``,
        ``"info"``. Free-form so callers can report richer state, but stick
        to these four for dashboard aggregation.
    sample : str
        Up to 200 chars of the matched text. Truncated automatically — never
        log full tool output (privacy + log size).
    session_id : str | None
        Claude Code session id when available. Pulled from hook stdin payload.

    Behavior
    --------
    * Silent on failure (OSError/etc). Hooks must never break tool calls
      because telemetry directory is unwritable.
    * Recursion-guarded via ``CLAUDE_INVOKED_BY`` env var so subagent runs
      don't double-count the parent's triggers.
    * Append under the log's own lock (``_append_line``), so concurrent hooks
      don't overwrite each other's lines (audit 2026-10-17, F7).
    """
    from datetime import UTC, datetime

    if os.environ.get("CLAUDE_INVOKED_BY"):
        return

    try:
        HOOK_TRIGGERS_LOG.parent.mkdir(parents=True, exist_ok=True)
        rotate_log_if_large(HOOK_TRIGGERS_LOG)
        # WHY: redact BEFORE truncate. Truncating first could split a secret
        # in half and leave a partial token visible (e.g. "sk-ab" without the
        # tail) — still a fingerprint and still useful for an attacker who
        # can guess the rest. Order is: redact_secrets → sanitize_text.
        safe_sample = sanitize_text(redact_secrets(sample), max_len=200)
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "hook": hook_name,
            "trigger": trigger_type,
            "action": action,
            "sample": safe_sample,
            "session_id": session_id or "",
        }
        # WHY the lock (audit 2026-10-17, F7): PIPE_BUF atomicity governs pipes, not regular
        # files, and an append is not atomic across processes on Windows.
        _append_line(HOOK_TRIGGERS_LOG, json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        # WHY: telemetry must never break the hook. If logs/ is read-only or
        # disk is full, hooks should keep guarding (warnings still emit).
        pass
