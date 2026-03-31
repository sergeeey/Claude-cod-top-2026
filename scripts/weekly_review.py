#!/usr/bin/env python3
"""Weekly self-improvement — analyze logs and suggest methodology changes.

WHY: Logs accumulate in ~/.claude/logs/ but nobody reads them.
This script finds recurring failures, underused agents, and stale patterns,
then outputs actionable recommendations for improving the config.

Usage:
    python scripts/weekly_review.py           # analyze last 7 days
    python scripts/weekly_review.py --days 30  # analyze last 30 days
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


def analyze(days: int = 7) -> list[str]:
    """Analyze logs and return recommendations."""
    log_dir = Path.home() / ".claude" / "logs"
    since = datetime.now(UTC) - timedelta(days=days)
    recommendations: list[str] = []

    # 1. Agent failure rate
    agent_entries = load_jsonl(log_dir / "subagent_verify.jsonl", since)
    if agent_entries:
        fails = [e for e in agent_entries if e.get("verdict") == "FAIL"]
        if len(fails) > 3:
            fail_types = Counter(e.get("agent_type", "?") for e in fails)
            worst = fail_types.most_common(1)[0]
            recommendations.append(
                f"AGENT QUALITY: {len(fails)} agent failures in {days}d. "
                f"Worst: {worst[0]} ({worst[1]} fails). "
                f"Consider adding more context to its prompt or switching model."
            )

    # 2. Task completion rate
    task_entries = load_jsonl(log_dir / "tasks.jsonl", since)
    if task_entries:
        created = sum(1 for e in task_entries if e.get("event") == "TaskCreated")
        completed = sum(1 for e in task_entries if e.get("event") == "TaskCompleted")
        if created > 0 and completed / created < 0.5:
            recommendations.append(
                f"TASK ABANDONMENT: {created} tasks created but only {completed} completed "
                f"({completed / created * 100:.0f}%). Tasks may be too large — try decomposing."
            )

    # 3. Instructions loading patterns
    instr_entries = load_jsonl(log_dir / "instructions.jsonl", since)
    if instr_entries:
        files_loaded = Counter(e.get("file_path", "?") for e in instr_entries)
        # Find rules never loaded (possible dead config)
        rules_dir = Path.home() / ".claude" / "rules"
        if rules_dir.exists():
            all_rules = {str(p) for p in rules_dir.glob("*.md")}
            loaded_rules = {f for f in files_loaded if "rules" in f}
            # WHY: we can't directly compare paths, but we can flag zero-load rules
            if len(loaded_rules) == 0 and len(all_rules) > 0:
                recommendations.append(
                    "DEAD CONFIG: No rules were loaded this period. "
                    "Check that rules/ files have correct path-matching or are unconditional."
                )

    # 4. Memory file sizes
    memory_dir = Path.home() / ".claude" / "memory"
    if memory_dir.exists():
        for md_file in memory_dir.glob("*.md"):
            try:
                size = md_file.stat().st_size
                if size > 10_000:  # >10KB
                    recommendations.append(
                        f"MEMORY BLOAT: {md_file.name} is {size / 1024:.1f}KB. "
                        f"Consider summarizing old entries (>30 days) to reduce baseline tokens."
                    )
            except OSError:
                continue

    if not recommendations:
        recommendations.append("ALL CLEAR: No issues found in the last " + str(days) + " days.")

    return recommendations


def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly self-improvement analysis")
    parser.add_argument("--days", type=int, default=7, help="Analysis period (default: 7)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    results = analyze(days=args.days)

    if args.json:
        print(json.dumps({"period_days": args.days, "recommendations": results}, indent=2))
    else:
        print(f"=== Weekly Review ({args.days}d) ===\n")
        for i, rec in enumerate(results, 1):
            print(f"{i}. {rec}\n")


if __name__ == "__main__":
    main()
