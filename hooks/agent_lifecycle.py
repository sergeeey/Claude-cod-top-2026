#!/usr/bin/env python3
"""SubagentStart/SubagentStop hook: agent lifecycle management.

WHY: Agents need project context at start and cleanup at stop.
Manual setup is error-prone; automated lifecycle ensures consistency.
Duration tracking feeds Believability Tracker — real performance data
instead of manually-written "?" placeholders.

Usage: python agent_lifecycle.py --start  (for SubagentStart)
       python agent_lifecycle.py --stop   (for SubagentStop)
"""

import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from utils import emit_hook_result, find_project_memory, parse_stdin

CACHE_DIR = Path.home() / ".claude" / "cache" / "agent_starts"
LOG_DIR = Path.home() / ".claude" / "logs"
PERF_FILE = Path.home() / ".claude" / "memory" / "_auto" / "agent_performance.md"

# WHY: rebuild performance summary every N stops to avoid expensive rebuild on every call
_REBUILD_EVERY = 10


def on_start(data: dict) -> None:
    """Inject project context when agent starts. Cache start_ts for duration tracking."""
    agent_type = data.get("agent_type", "unknown")
    agent_id = data.get("agent_id", "unknown")

    # WHY: persist start_ts so on_stop can compute real duration.
    # Using a per-agent-id cache file avoids concurrency issues with parallel agents.
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{agent_id}.json"
    try:
        cache_file.write_text(
            json.dumps({"start_ts": datetime.now(UTC).isoformat(), "agent_type": agent_type}),
            encoding="utf-8",
        )
    except OSError:
        pass

    # WHY: load activeContext.md so the agent knows current project state
    memory = find_project_memory()
    if memory and memory.exists():
        try:
            content = memory.read_text(encoding="utf-8")[:2000]
            emit_hook_result(
                "SubagentStart",
                f"[agent-lifecycle] Project context for {agent_type}:\n{content}",
            )
        except OSError:
            pass


def on_stop(data: dict) -> None:
    """Cleanup when agent stops. Compute duration from cached start_ts."""
    agent_type = data.get("agent_type", "unknown")
    agent_id = data.get("agent_id", "unknown")

    # WHY: read and delete the start-time cache to compute real duration
    duration_str = "?"
    cache_file = CACHE_DIR / f"{agent_id}.json"
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            start = datetime.fromisoformat(cached["start_ts"])
            duration_s = (datetime.now(UTC) - start).total_seconds()
            duration_str = f"{duration_s:.1f}s"
            cache_file.unlink(missing_ok=True)
        except (OSError, KeyError, ValueError):
            pass

    # WHY: log with duration for believability tracking
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "agent_lifecycle.log"

    try:
        timestamp = datetime.now(UTC).isoformat()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | STOP | {agent_type} | {agent_id} | {duration_str} | success\n")
    except OSError:
        return

    # WHY: rebuild performance summary periodically — not every stop (expensive)
    _maybe_rebuild_performance(log_file)


def _maybe_rebuild_performance(log_file: Path) -> None:
    """Rebuild agent_performance.md every _REBUILD_EVERY new stop entries."""
    if not log_file.exists():
        return
    try:
        lines = log_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    stop_lines = [line for line in lines if "| STOP |" in line]
    if len(stop_lines) % _REBUILD_EVERY != 0:
        return

    # Aggregate counts and durations per agent type
    counts: dict[str, int] = defaultdict(int)
    durations: dict[str, list[float]] = defaultdict(list)

    for line in stop_lines:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue
        agent_type = parts[2]
        counts[agent_type] += 1
        if len(parts) >= 5:
            dur_str = parts[4]
            if dur_str.endswith("s") and dur_str != "?":
                try:
                    durations[agent_type].append(float(dur_str[:-1]))
                except ValueError:
                    pass

    rows = []
    for agent_type, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        durs = durations[agent_type]
        avg = f"{sum(durs) / len(durs):.1f}s" if durs else "?"
        rows.append(f"| {agent_type} | {count} | {avg} |")

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    table = "\n".join(rows)

    # WHY: preserve the manually-curated Believability Score section across rebuilds
    existing_manual = ""
    if PERF_FILE.exists():
        try:
            existing = PERF_FILE.read_text(encoding="utf-8")
            marker = "## Believability Score (manual)"
            if marker in existing:
                existing_manual = "\n\n" + existing[existing.index(marker) :]
        except OSError:
            pass

    content = f"""# Agent Performance Summary
_Auto-generated: {now}_
_Source: agent_lifecycle.log ({len(stop_lines)} entries)_

## By Agent Type

| Agent Type | Calls | Avg Duration |
|------------|------:|-------------:|
{table}{existing_manual}
"""
    try:
        PERF_FILE.parent.mkdir(parents=True, exist_ok=True)
        PERF_FILE.write_text(content, encoding="utf-8")
    except OSError:
        pass


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    # WHY: use explicit --start/--stop flag from settings.json command
    # instead of fragile payload heuristic. This is robust against
    # Claude Code protocol changes that add new fields.
    if "--stop" in sys.argv:
        on_stop(data)
    else:
        # WHY: default to on_start for backward compatibility
        on_start(data)


if __name__ == "__main__":
    main()
