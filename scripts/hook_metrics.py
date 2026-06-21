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
    python scripts/hook_metrics.py --alert          # exit 1 if block-rate spike detected
    python scripts/hook_metrics.py --alert --alert-threshold 0.20  # 20% spike threshold

Output sections:
    1. Total triggers, unique sessions, time range
    2. Per-hook table: count, action breakdown, top trigger types
    3. Top-10 trigger types across all hooks
    4. Daily volume (sparkline-style)
    5. Recent samples — 5 most recent entries per hook for spot-checking

NOT included on purpose:
    - precision/recall — requires ground-truth labels we don't have yet

    Drift alert (--alert):
    Compares the block rate of the LAST day in the window against the mean
    block rate of the PREVIOUS days. If the spike exceeds --alert-threshold
    (default 0.15), exits with code 1 and prints the offending hooks.
    WHY: the known issue "input_guard blocks mcp__context7 27x/2d" is
    invisible without a threshold — the alert surfaces it automatically.
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


def compute_drift(entries: list[dict], threshold: float) -> list[dict]:
    """Detect block-rate spikes per hook by comparing last day vs prior days.

    WHY: a sudden jump in block rate (e.g. input_guard blocking mcp__context7)
    signals either a regex regression or a threshold that's too tight — both
    require human review. We use block rate as a proxy for false-positive rate
    because we don't have ground-truth labels yet.

    Returns a list of alert dicts (empty = no drift detected):
        [{"hook": str, "last_day_rate": float, "prior_rate": float, "delta": float}]
    """
    if not entries:
        return []

    # Group entries by (hook, day)
    from collections import defaultdict

    by_hook_day: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for e in entries:
        hook = e.get("hook", "<unknown>")
        ts = e.get("ts", "")
        day = ts[:10] if ts else "unknown"
        by_hook_day[hook][day].append(e)

    alerts: list[dict] = []
    for hook, days in by_hook_day.items():
        sorted_days = sorted(days.keys())
        if len(sorted_days) < 2:
            # Need at least 2 days to compare
            continue

        last_day = sorted_days[-1]
        prior_days = sorted_days[:-1]

        def _block_rate(day_entries: list[dict]) -> float:
            if not day_entries:
                return 0.0
            blocks = sum(1 for e in day_entries if e.get("action") == "block")
            return blocks / len(day_entries)

        last_rate = _block_rate(days[last_day])
        prior_rates = [_block_rate(days[d]) for d in prior_days]
        prior_mean = sum(prior_rates) / len(prior_rates) if prior_rates else 0.0

        delta = last_rate - prior_mean
        if delta > threshold:
            alerts.append(
                {
                    "hook": hook,
                    "last_day": last_day,
                    "last_day_rate": round(last_rate, 3),
                    "prior_mean_rate": round(prior_mean, 3),
                    "delta": round(delta, 3),
                    "last_day_count": len(days[last_day]),
                }
            )

    return sorted(alerts, key=lambda a: -a["delta"])


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
    parser.add_argument(
        "--alert",
        action="store_true",
        help="Exit 1 if block-rate spike detected (use in CI / cron)",
    )
    parser.add_argument(
        "--alert-threshold",
        type=float,
        default=0.15,
        metavar="DELTA",
        help="Block-rate spike threshold 0.0–1.0 (default 0.15 = 15%%)",
    )
    args = parser.parse_args()

    since = parse_since(args)
    entries = load_entries(args.log)
    entries_in_window = filter_by_window(entries, since)
    metrics = compute_metrics(entries_in_window)

    # WHY: run drift check before rendering so alert message appears first
    # in CI output, not buried after the full report.
    drift_exit_code = 0
    if args.alert:
        drift_alerts = compute_drift(entries_in_window, threshold=args.alert_threshold)
        if drift_alerts:
            drift_exit_code = 1
            print(
                f"[hook-metrics] DRIFT ALERT — block-rate spike detected "
                f"(threshold={args.alert_threshold:.0%}):",
                file=sys.stderr,
            )
            for a in drift_alerts:
                print(
                    f"  hook={a['hook']} last_day={a['last_day']} "
                    f"block_rate={a['last_day_rate']:.1%} "
                    f"(prior_mean={a['prior_mean_rate']:.1%}, "
                    f"delta=+{a['delta']:.1%}, "
                    f"n={a['last_day_count']})",
                    file=sys.stderr,
                )
            print(
                "[hook-metrics] Action: check recent regex changes or narrow MCP matchers.",
                file=sys.stderr,
            )
        else:
            print(
                f"[hook-metrics] OK — no block-rate spike > {args.alert_threshold:.0%}",
                file=sys.stderr,
            )

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
    return drift_exit_code


if __name__ == "__main__":
    sys.exit(main())
