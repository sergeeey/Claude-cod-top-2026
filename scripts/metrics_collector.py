#!/usr/bin/env python3
"""Structured metrics collector — aggregates JSONL logs into session metrics.

WHY: Without aggregated metrics, individual log entries in ~/.claude/logs/
are noise. This script turns them into actionable session/weekly summaries:
hook fire counts, agent pass/fail rates, skill activation frequency.

Usage:
    python scripts/metrics_collector.py                # last 24h
    python scripts/metrics_collector.py --days 7       # last 7 days
    python scripts/metrics_collector.py --json          # machine-readable output
"""

import argparse
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path


def load_jsonl(path: Path, since: datetime) -> list[dict]:
    """Load JSONL entries newer than `since`."""
    entries: list[dict] = []
    if not path.exists():
        return entries
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = entry.get("timestamp", "")
                    if ts and ts >= since.isoformat():
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return entries


def collect_metrics(days: int = 1) -> dict:
    """Aggregate all JSONL logs into a metrics summary."""
    log_dir = Path.home() / ".claude" / "logs"
    since = datetime.now(UTC) - timedelta(days=days)

    metrics: dict = {
        "period_days": days,
        "collected_at": datetime.now(UTC).isoformat(),
        "hooks": {},
        "agents": {},
        "tasks": {},
        "skills": {},
        "instructions": {},
    }

    # Hook activity (config_audit.log)
    config_entries = load_jsonl(log_dir / "config_audit.log", since)
    metrics["hooks"]["config_changes"] = len(config_entries)

    # Agent verify results (subagent_verify.jsonl)
    agent_entries = load_jsonl(log_dir / "subagent_verify.jsonl", since)
    agent_verdicts = Counter(e.get("verdict", "unknown") for e in agent_entries)
    agent_types = Counter(e.get("agent_type", "unknown") for e in agent_entries)
    metrics["agents"] = {
        "total_runs": len(agent_entries),
        "pass": agent_verdicts.get("PASS", 0),
        "fail": agent_verdicts.get("FAIL", 0),
        "by_type": dict(agent_types),
    }

    # Task lifecycle (tasks.jsonl)
    task_entries = load_jsonl(log_dir / "tasks.jsonl", since)
    task_events = Counter(e.get("event", "unknown") for e in task_entries)
    metrics["tasks"] = {
        "created": task_events.get("TaskCreated", 0),
        "completed": task_events.get("TaskCompleted", 0),
    }

    # Instructions loaded (instructions.jsonl)
    instr_entries = load_jsonl(log_dir / "instructions.jsonl", since)
    loaded_files = Counter(e.get("file_path", "unknown") for e in instr_entries)
    metrics["instructions"] = {
        "total_loads": len(instr_entries),
        "by_file": dict(loaded_files.most_common(20)),
    }

    # Elicitation events (elicitation.jsonl)
    elic_entries = load_jsonl(log_dir / "elicitation.jsonl", since)
    metrics["elicitation"] = {"total_events": len(elic_entries)}

    return metrics


def print_human(metrics: dict) -> None:
    """Print metrics in human-readable format."""
    print(f"=== Claude Code Metrics ({metrics['period_days']}d) ===\n")

    agents = metrics["agents"]
    if agents["total_runs"]:
        fail_rate = agents["fail"] / agents["total_runs"] * 100
        print(
            f"Agents: {agents['total_runs']} runs, "
            f"{agents['pass']} pass, {agents['fail']} fail "
            f"({fail_rate:.0f}% fail rate)"
        )
        if agents.get("by_type"):
            for agent, count in sorted(agents["by_type"].items(), key=lambda x: -x[1]):
                print(f"  {agent}: {count}")
    else:
        print("Agents: no data")

    tasks = metrics["tasks"]
    print(f"\nTasks: {tasks['created']} created, {tasks['completed']} completed")

    instr = metrics["instructions"]
    print(f"\nInstructions loaded: {instr['total_loads']} times")
    if instr.get("by_file"):
        for f, count in list(instr["by_file"].items())[:5]:
            print(f"  {f}: {count}")

    print(f"\nConfig changes: {metrics['hooks']['config_changes']}")
    print(f"MCP elicitations: {metrics['elicitation']['total_events']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate Claude Code session metrics")
    parser.add_argument("--days", type=int, default=1, help="Period in days (default: 1)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    metrics = collect_metrics(days=args.days)

    if args.json:
        print(json.dumps(metrics, indent=2))
    else:
        print_human(metrics)


if __name__ == "__main__":
    main()
