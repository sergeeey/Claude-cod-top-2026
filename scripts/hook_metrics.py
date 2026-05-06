#!/usr/bin/env python3
"""Hook trigger metrics — aggregate ~/.claude/logs/hook_triggers.jsonl.

WHY: log_hook_trigger() (utils.py:530+) writes append-only JSONL of every
hook firing. Without aggregation those logs are an opaque pile — no one
manually reads 5K JSON lines per week. This script turns them into a
rolling Markdown summary that any human (or LLM) can scan in 30 seconds.

The summary is **the** evidence base for any "anti-hallucination works"
claim in marketing material (Habr article, README, gist). Without it those
claims stay [INFERRED]; with it they become [VERIFIED-REAL].

Usage:
    python scripts/hook_metrics.py                  # rolling 7d window → stdout
    python scripts/hook_metrics.py --window 30      # last 30 days
    python scripts/hook_metrics.py --since 2026-05-01
    python scripts/hook_metrics.py --out ~/.claude/memory/_auto/hook_effectiveness.md
    python scripts/hook_metrics.py --json           # machine-readable JSON

Output sections:
    1. Total triggers, unique sessions, time range
    2. Per-hook table: count, action breakdown, top trigger types
    3. Top-10 trigger types across all hooks
    4. Daily volume (sparkline-style)
    5. Recent samples — 5 most recent entries per hook for spot-checking

NOT included on purpose:
    - precision/recall — requires ground-truth labels we don't have yet
    - false-positive flagging — same reason
    Future work: link triggers to next-message Evidence-marker presence to
    compute "did the warning actually cause Claude to add [VERIFIED-REAL]?".
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

DEFAULT_LOG = Path.home() / ".claude" / "logs" / "hook_triggers.jsonl"


def load_entries(log_path: Path) -> list[dict]:
    """Read JSONL, skip malformed lines silently.

    WHY: telemetry log is append-only and can be truncated mid-write on
    sudden process kill. One bad line should not block the whole report.
    """
    if not log_path.exists():
        return []
    entries: list[dict] = []
    with log_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                # WHY: silently skip — a partial write doesn't corrupt the rest.
                continue
    return entries


def filter_by_window(entries: list[dict], since: datetime) -> list[dict]:
    """Keep only entries with ts >= since (parsed as UTC ISO)."""
    out = []
    for e in entries:
        ts_raw = e.get("ts", "")
        try:
            # WHY: datetime.fromisoformat handles "+00:00" and "Z" since 3.11.
            ts = datetime.fromisoformat(ts_raw)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
        except (ValueError, TypeError):
            continue
        if ts >= since:
            out.append(e)
    return out


def compute_metrics(entries: list[dict]) -> dict:
    """Return aggregate metrics ready for rendering.

    Keys:
        total: int
        sessions: int (unique session_id count, "" excluded)
        time_range: (earliest_ts, latest_ts) as ISO strings or None
        per_hook: dict[hook_name, {count, actions: Counter, triggers: Counter, samples: list}]
        top_triggers: list[(trigger_type, count)] (top 10)
        per_day: dict[YYYY-MM-DD, count]
    """
    if not entries:
        return {
            "total": 0,
            "sessions": 0,
            "time_range": None,
            "per_hook": {},
            "top_triggers": [],
            "per_day": {},
        }

    per_hook: dict[str, dict] = defaultdict(
        lambda: {
            "count": 0,
            "actions": Counter(),
            "triggers": Counter(),
            "samples": [],
        }
    )
    all_triggers: Counter[str] = Counter()
    per_day: Counter[str] = Counter()
    sessions: set[str] = set()
    timestamps: list[str] = []

    for e in entries:
        hook = e.get("hook", "<unknown>")
        action = e.get("action", "<unknown>")
        trigger = e.get("trigger", "<unknown>")
        sample = e.get("sample", "")
        ts = e.get("ts", "")
        sid = e.get("session_id", "")

        per_hook[hook]["count"] += 1
        per_hook[hook]["actions"][action] += 1
        per_hook[hook]["triggers"][trigger] += 1
        # WHY: keep last 5 samples per hook — enough for spot-check, no log explosion
        per_hook[hook]["samples"].append({"ts": ts, "trigger": trigger, "sample": sample})
        per_hook[hook]["samples"] = per_hook[hook]["samples"][-5:]

        all_triggers[trigger] += 1
        if sid:
            sessions.add(sid)
        if ts:
            timestamps.append(ts)
            day = ts[:10]  # YYYY-MM-DD prefix
            per_day[day] += 1

    timestamps.sort()
    time_range = (timestamps[0], timestamps[-1]) if timestamps else None

    return {
        "total": len(entries),
        "sessions": len(sessions),
        "time_range": time_range,
        "per_hook": dict(per_hook),
        "top_triggers": all_triggers.most_common(10),
        "per_day": dict(sorted(per_day.items())),
    }


def render_sparkline(per_day: dict[str, int]) -> str:
    """Render daily counts as Unicode sparkline.

    WHY: ASCII sparkline travels everywhere — Slack, GitHub markdown, plain
    terminal. No matplotlib dep, no PNG, no pixel theatre.
    """
    if not per_day:
        return "(no data)"
    blocks = "▁▂▃▄▅▆▇█"
    counts = list(per_day.values())
    peak = max(counts) or 1
    line = "".join(
        blocks[min(int((c / peak) * (len(blocks) - 1)), len(blocks) - 1)] for c in counts
    )
    return f"{line}  (peak={peak}, days={len(counts)})"


def render_markdown(metrics: dict, since: datetime, log_path: Path) -> str:
    """Format metrics as Markdown report. Stable, paste-into-Habr ready."""
    lines = []
    lines.append("# Hook Trigger Metrics")
    lines.append("")
    lines.append(f"**Source:** `{log_path}`")
    lines.append(f"**Window:** since `{since.isoformat()}`")
    lines.append(f"**Generated:** `{datetime.now(UTC).isoformat()}`")
    lines.append("")

    if metrics["total"] == 0:
        lines.append("> No triggers in window. Either telemetry is freshly enabled, the")
        lines.append("> log file is missing, or hooks are silent — verify with:")
        lines.append("> ```")
        lines.append(f"> ls -la {log_path}")
        lines.append("> wc -l ~/.claude/logs/hook_triggers.jsonl")
        lines.append("> ```")
        return "\n".join(lines) + "\n"

    earliest, latest = metrics["time_range"]
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total triggers:** {metrics['total']}")
    lines.append(f"- **Unique sessions:** {metrics['sessions']}")
    lines.append(f"- **First entry:** `{earliest}`")
    lines.append(f"- **Last entry:** `{latest}`")
    lines.append("")
    lines.append(f"**Daily volume:** `{render_sparkline(metrics['per_day'])}`")
    lines.append("")

    lines.append("## Per-hook breakdown")
    lines.append("")
    lines.append("| Hook | Triggers | Top action | Top trigger type |")
    lines.append("|------|---------:|------------|------------------|")
    for hook, stats in sorted(metrics["per_hook"].items(), key=lambda kv: -kv[1]["count"]):
        top_action = stats["actions"].most_common(1)[0] if stats["actions"] else ("?", 0)
        top_trig = stats["triggers"].most_common(1)[0] if stats["triggers"] else ("?", 0)
        action_str = f"{top_action[0]} ({top_action[1]})"
        trig_str = f"{top_trig[0]} ({top_trig[1]})"
        lines.append(f"| `{hook}` | {stats['count']} | {action_str} | {trig_str} |")
    lines.append("")

    lines.append("## Top-10 trigger types (across all hooks)")
    lines.append("")
    for trig, count in metrics["top_triggers"]:
        lines.append(f"- `{trig}`: {count}")
    lines.append("")

    lines.append("## Recent samples (last 5 per hook)")
    lines.append("")
    for hook, stats in sorted(metrics["per_hook"].items(), key=lambda kv: -kv[1]["count"]):
        lines.append(f"### `{hook}`")
        lines.append("")
        for s in reversed(stats["samples"]):  # newest first
            ts_short = s["ts"][:19] if s["ts"] else "?"
            sample_short = (s["sample"] or "")[:120]
            lines.append(f"- `{ts_short}` [{s['trigger']}] {sample_short}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*Generated by `scripts/hook_metrics.py` from `claude-cod-top-2026`. "
        "[Source](https://github.com/sergeeey/Claude-cod-top-2026/blob/main/scripts/hook_metrics.py).*"
    )
    return "\n".join(lines) + "\n"


def parse_since(args: argparse.Namespace) -> datetime:
    """Resolve --since / --window into a UTC datetime cutoff.

    --since wins if both are given (explicit beats implicit).
    """
    if args.since:
        try:
            dt = datetime.fromisoformat(args.since)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            print(f"error: --since must be ISO-8601, got {args.since!r}", file=sys.stderr)
            sys.exit(2)
    return datetime.now(UTC) - timedelta(days=args.window)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG, help="JSONL log path")
    parser.add_argument("--window", type=int, default=7, help="Days back from now (default 7)")
    parser.add_argument("--since", type=str, help="ISO-8601 cutoff, overrides --window")
    parser.add_argument("--out", type=Path, help="Write Markdown to this path (default stdout)")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown")
    args = parser.parse_args()

    since = parse_since(args)
    entries = load_entries(args.log)
    entries_in_window = filter_by_window(entries, since)
    metrics = compute_metrics(entries_in_window)

    if args.json:
        # WHY: json output strips Counter/dict-of-dict to plain lists for portability.
        out_obj = {
            "total": metrics["total"],
            "sessions": metrics["sessions"],
            "time_range": metrics["time_range"],
            "top_triggers": metrics["top_triggers"],
            "per_day": metrics["per_day"],
            "per_hook": {
                h: {
                    "count": s["count"],
                    "actions": dict(s["actions"]),
                    "triggers": dict(s["triggers"]),
                    "samples": s["samples"],
                }
                for h, s in metrics["per_hook"].items()
            },
        }
        rendered = json.dumps(out_obj, ensure_ascii=False, indent=2)
    else:
        rendered = render_markdown(metrics, since, args.log)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
