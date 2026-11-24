"""Controlled stress runs for the hook state layer (audit 2026-10-17).

The scenarios mirror tests/test_concurrency_audit.py at larger scale and report
counts: lost records, exceptions, corrupted lines, lock timeouts and wait times.
Each run points HOME (and USERPROFILE, which Windows reads) at a fresh temp
directory before any hook module is imported, so no real ~/.claude file is read
or written (.claude/rules/testing.md, Observability Test Isolation).

Usage:
    python scripts/stress_concurrency.py --label baseline \
        --out artifacts/concurrency-stress-baseline.json
    python scripts/stress_concurrency.py --label quick --out tmp/stress.json --quick
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import platform
import re
import sys
import tempfile
import threading
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ROOT / "hooks"


def _prepare_import_path() -> None:
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))


# --- worker functions (module level, so the spawn start method can pickle them) ---


def _hook_state_worker(base_dir: str, worker: int, invocations: int) -> None:
    _prepare_import_path()
    from hook_state import HookState

    for i in range(invocations):
        # Each invocation loads fresh, as a hook subprocess does, then saves once.
        state = HookState("stress_lost_update", max_entries=None, base_dir=Path(base_dir))
        state[f"w{worker:02d}-i{i:04d}"] = i
        state.save()


def _counter_worker(lock_path: str, counter_path: str, rounds: int, out: mp.Queue) -> None:
    _prepare_import_path()
    from lib.state import file_lock

    timeouts = 0
    for _ in range(rounds):
        with file_lock(Path(lock_path), timeout=15.0) as acquired:
            if not acquired:
                timeouts += 1
                continue
            value = int(Path(counter_path).read_text(encoding="utf-8"))
            Path(counter_path).write_text(str(value + 1), encoding="utf-8")
    out.put(timeouts)


def _append_worker(log_path: str, worker: int, lines: int) -> None:
    _prepare_import_path()
    import lib.state as lib_state

    lib_state.HOOK_TRIGGERS_LOG = Path(log_path)
    for i in range(lines):
        lib_state.log_hook_trigger(
            f"hook-w{worker:02d}",
            "stress",
            "info",
            sample=f"w{worker:02d}-i{i:05d}-" + "x" * 150,
            session_id=f"s{worker:02d}",
        )


def _reader_worker(path: str) -> None:
    while True:
        try:
            with open(path, "rb") as fh:
                fh.read()
        except OSError:
            pass


def _abandoning_holder(lock_path: str) -> None:
    _prepare_import_path()
    from lib.state import file_lock

    ctx = file_lock(Path(lock_path), timeout=5.0)
    ctx.__enter__()
    os._exit(0)  # die while holding the lock, the way a killed hook does


# --- scenarios ---------------------------------------------------------------


def scenario_hook_state_lost_updates(workers: int, invocations: int) -> dict:
    """S1: several hook invocations, each load-modify-save one key in one state file."""
    base = Path(tempfile.mkdtemp(prefix="s1-"))
    procs = [
        mp.Process(target=_hook_state_worker, args=(str(base), w, invocations))
        for w in range(workers)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    _prepare_import_path()
    from hook_state import HookState

    final = HookState("stress_lost_update", max_entries=None, base_dir=base)
    present = sum(1 for key in final._data if key.startswith("w"))
    expected = workers * invocations
    return {
        "workers": workers,
        "invocations_per_worker": invocations,
        "expected_keys": expected,
        "present_keys": present,
        "lost_records": expected - present,
        "defect_signal": present < expected,
    }


def scenario_lock_contention(workers: int, rounds: int) -> dict:
    """S2 (control): file_lock serialises a read-modify-write under process contention."""
    base = Path(tempfile.mkdtemp(prefix="s2-"))
    lock, counter = base / "c.lock", base / "c.txt"
    counter.write_text("0", encoding="utf-8")
    out: mp.Queue = mp.Queue()
    procs = [
        mp.Process(target=_counter_worker, args=(str(lock), str(counter), rounds, out))
        for _ in range(workers)
    ]
    start = time.monotonic()
    for p in procs:
        p.start()
    timeouts = sum(out.get() for _ in procs)
    for p in procs:
        p.join()
    elapsed = time.monotonic() - start
    expected = workers * rounds
    final = int(counter.read_text(encoding="utf-8"))
    return {
        "workers": workers,
        "rounds_per_worker": rounds,
        "expected": expected,
        "final": final,
        "lost_increments": expected - final,
        "lock_timeouts": timeouts,
        "elapsed_s": round(elapsed, 3),
        "defect_signal": final != expected or timeouts > 0,
    }


def scenario_append_atomicity(workers: int, lines: int) -> dict:
    """S3: several processes append JSON lines to one shared log via log_hook_trigger."""
    base = Path(tempfile.mkdtemp(prefix="s3-"))
    log = base / "hook_triggers.jsonl"
    procs = [mp.Process(target=_append_worker, args=(str(log), w, lines)) for w in range(workers)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    corrupt = 0
    seen: set[tuple[str, str]] = set()
    total = 0
    for raw in log.read_bytes().split(b"\n"):
        if not raw:
            continue
        total += 1
        try:
            sample = json.loads(raw)["sample"]
            worker_tag, index_tag, *_ = sample.split("-")
            seen.add((worker_tag, index_tag))
        except (ValueError, KeyError, TypeError):
            corrupt += 1
    expected = workers * lines
    lost = expected - len(seen)
    return {
        "workers": workers,
        "lines_per_worker": lines,
        "expected": expected,
        "lines_in_file": total,
        "distinct_records": len(seen),
        "lost_records": lost,
        "corrupt_lines": corrupt,
        "defect_signal": lost > 0 or corrupt > 0,
    }


def scenario_atomic_write_threads(threads: int, writes: int) -> dict:
    """S4: threads of one process call atomic_write_json on the same path."""
    _prepare_import_path()
    from lib.state import atomic_write_json

    base = Path(tempfile.mkdtemp(prefix="s4-"))
    path = base / "shared.json"
    errors: list[str] = []
    guard = threading.Lock()

    def writer(n: int) -> None:
        for i in range(writes):
            try:
                atomic_write_json(path, {"writer": n, "i": i})
            except Exception as exc:
                with guard:
                    errors.append(type(exc).__name__)

    workers = [threading.Thread(target=writer, args=(n,)) for n in range(threads)]
    for t in workers:
        t.start()
    for t in workers:
        t.join()
    try:
        json.loads(path.read_text(encoding="utf-8"))
        final_valid = True
    except (OSError, ValueError):
        final_valid = False
    return {
        "threads": threads,
        "writes_per_thread": writes,
        "exceptions": len(errors),
        "exception_types": dict(Counter(errors)),
        "final_file_valid": final_valid,
        "defect_signal": bool(errors) or not final_valid,
    }


def scenario_decision_records(threads: int, records: int, delay_s: float) -> dict:
    """S5: threads append decision records to one decisions.md (post_commit_memory)."""
    _prepare_import_path()
    import lib.state as lib_state
    import post_commit_memory as pcm

    base = Path(tempfile.mkdtemp(prefix="s5-"))
    decisions = base / "decisions.md"
    decisions.write_text("# Decisions\n", encoding="utf-8")
    pcm.find_decisions_file = lambda: decisions
    real_write = lib_state.atomic_write_text

    def delayed_write(path: Path, text: str) -> None:
        if delay_s:
            time.sleep(delay_s)  # widens the read-to-write window; 0 = natural timing
        real_write(path, text)

    pcm.atomic_write_text = delayed_write
    lib_state.atomic_write_text = delayed_write
    errors: list[str] = []
    guard = threading.Lock()

    def recorder(n: int) -> None:
        for i in range(records):
            try:
                pcm.log_decision(f"h{n:02d}{i:04d}", f"arch: decision {n}-{i}")
            except Exception as exc:
                with guard:
                    errors.append(type(exc).__name__)

    workers = [threading.Thread(target=recorder, args=(n,)) for n in range(threads)]
    for t in workers:
        t.start()
    for t in workers:
        t.join()
    text = decisions.read_text(encoding="utf-8")
    found = set(re.findall(r"### \[[^\]]+\] decision (\d+)-(\d+)", text))
    expected = threads * records
    lost = expected - len(found)
    return {
        "threads": threads,
        "records_per_thread": records,
        "injected_delay_s": delay_s,
        "expected": expected,
        "present": len(found),
        "lost_records": lost,
        "exceptions": len(errors),
        "exception_types": dict(Counter(errors)),
        "defect_signal": lost > 0 or bool(errors),
    }


def scenario_replace_under_readers(writes: int, readers: int) -> dict:
    """S6 (Windows): one writer saves while other processes keep the file open."""
    _prepare_import_path()
    from hook_state import HookState

    base = Path(tempfile.mkdtemp(prefix="s6-"))
    state_file = base / ".claude" / "state" / "replace_stress.json"
    seed = HookState("replace_stress", max_entries=None, base_dir=base)
    seed["seed"] = 0
    seed.save()
    procs = [mp.Process(target=_reader_worker, args=(str(state_file),)) for _ in range(readers)]
    for p in procs:
        p.start()
    try:
        for i in range(writes):
            state = HookState("replace_stress", max_entries=None, base_dir=base)
            state[f"k{i:04d}"] = i
            state.save()
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.join()
    final = HookState("replace_stress", max_entries=None, base_dir=base)
    present = sum(1 for key in final._data if key.startswith("k"))
    return {
        "writes": writes,
        "readers": readers,
        "present_keys": present,
        "lost_saves": writes - present,
        "platform": sys.platform,
        "defect_signal": present < writes,
    }


def scenario_abandoned_lock(timeout_s: float, stale_after_s: float) -> dict:
    """S7 (control, deadlock check): a holder dies without releasing the lock."""
    _prepare_import_path()
    from lib.state import file_lock

    base = Path(tempfile.mkdtemp(prefix="s7-"))
    lock = base / "abandoned.lock"
    holder = mp.Process(target=_abandoning_holder, args=(str(lock),))
    holder.start()
    holder.join()
    start = time.monotonic()
    with file_lock(lock, timeout=timeout_s, poll_interval=0.02, stale_after=60.0) as acquired:
        waited_s = time.monotonic() - start
        blocked = acquired is False
    time.sleep(stale_after_s + 0.1)
    with file_lock(lock, timeout=2.0, poll_interval=0.02, stale_after=stale_after_s) as reclaimed:
        reclaimed_ok = reclaimed is True
    return {
        "timeout_s": timeout_s,
        "waited_s": round(waited_s, 3),
        "returned_false_at_timeout": blocked,
        "reclaimed_after_stale": reclaimed_ok,
        "defect_signal": not (blocked and reclaimed_ok and waited_s < timeout_s + 1.0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--label", required=True, help="run label, e.g. baseline or after")
    parser.add_argument("--out", required=True, help="where to write the JSON results")
    parser.add_argument("--quick", action="store_true", help="smaller sizes for a fast check")
    args = parser.parse_args()

    home = Path(tempfile.mkdtemp(prefix="stress-home-"))
    os.environ["HOME"] = str(home)
    os.environ["USERPROFILE"] = str(home)
    os.environ.pop("CLAUDE_INVOKED_BY", None)

    scale = 2 if args.quick else 1
    results: dict[str, object] = {
        "label": args.label,
        "started_utc": datetime.now(UTC).isoformat(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "isolated_home": str(home),
        "scenarios": {},
    }
    scenarios: dict[str, dict] = results["scenarios"]  # type: ignore[assignment]
    scenarios["S1_hook_state_lost_updates"] = scenario_hook_state_lost_updates(8, 50 // scale)
    scenarios["S2_lock_contention_control"] = scenario_lock_contention(8, 50 // scale)
    scenarios["S3_append_atomicity"] = scenario_append_atomicity(6, 150 // scale)
    scenarios["S4_atomic_write_threads"] = scenario_atomic_write_threads(8, 40 // scale)
    scenarios["S5a_decision_records_natural"] = scenario_decision_records(8, 5, 0.0)
    scenarios["S5b_decision_records_widened"] = scenario_decision_records(8, 5, 0.01)
    scenarios["S6_replace_under_readers"] = scenario_replace_under_readers(100 // scale, 3)
    scenarios["S7_abandoned_lock_control"] = scenario_abandoned_lock(0.5, 0.3)

    flagged = [name for name, body in scenarios.items() if body.get("defect_signal")]
    results["defect_signal_scenarios"] = flagged
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {"label": args.label, "flagged": flagged, "out": str(out_path)}, ensure_ascii=False
        )
    )
    return 0


if __name__ == "__main__":
    mp.freeze_support()
    raise SystemExit(main())
