#!/usr/bin/env python3
"""Export Claude Code hook telemetry from model_usage.jsonl to OpenTelemetry.

Reads ~/.claude/logs/model_usage.jsonl (written by hooks/model_usage_tracker.py)
and either:
  • prints a console summary table  (no OTel SDK required)
  • exports spans to an OTLP endpoint (requires opentelemetry-sdk)

JSONL entry format (one per tool call):
    {"ts": 1234567890.123, "sid": "ab123456", "tool": "Bash",
     "resp_bytes": 1234, "inp_bytes": 456,
     "est_out_tok": 308, "est_in_tok": 114}

Usage:
    python scripts/otel_exporter.py                  # console summary
    python scripts/otel_exporter.py --top 10         # top-10 tools by tokens
    python scripts/otel_exporter.py --since 3600     # last 1 hour only
    python scripts/otel_exporter.py --tail           # follow mode (like tail -f)
    python scripts/otel_exporter.py --otlp           # export to localhost:4317
    python scripts/otel_exporter.py --otlp http://collector:4318/v1/traces

Requires for --otlp:
    pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

LOG_FILE = Path.home() / ".claude" / "logs" / "model_usage.jsonl"
DEFAULT_OTLP_ENDPOINT = "http://localhost:4317"
SERVICE_NAME = "claude-code-harness"

# ── OTel SDK — optional import ────────────────────────────────────────────────

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter,  # type: ignore
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    HAS_OTEL = True
except ImportError:
    HAS_OTEL = False


# ── Data model ────────────────────────────────────────────────────────────────


def _load_entries(path: Path, since: float | None = None) -> list[dict]:
    """Read JSONL entries, optionally filtering by timestamp."""
    if not path.exists():
        return []
    entries: list[dict] = []
    cutoff = time.time() - since if since else 0.0
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since and entry.get("ts", 0) < cutoff:
                continue
            entries.append(entry)
    except OSError:
        pass
    return entries


# ── Console summary ───────────────────────────────────────────────────────────


def _console_summary(entries: list[dict], top: int | None = None) -> None:
    """Print per-tool usage summary to stdout."""
    if not entries:
        print("No entries found in", LOG_FILE)
        return

    by_tool: dict[str, dict] = defaultdict(lambda: {"calls": 0, "out_tok": 0, "in_tok": 0})
    total_out = total_in = 0
    sessions: set[str] = set()

    for e in entries:
        t = e.get("tool", "unknown")
        by_tool[t]["calls"] += 1
        by_tool[t]["out_tok"] += e.get("est_out_tok", 0)
        by_tool[t]["in_tok"] += e.get("est_in_tok", 0)
        total_out += e.get("est_out_tok", 0)
        total_in += e.get("est_in_tok", 0)
        if s := e.get("sid"):
            sessions.add(s)

    rows = sorted(by_tool.items(), key=lambda kv: kv[1]["out_tok"] + kv[1]["in_tok"], reverse=True)
    if top:
        rows = rows[:top]

    print(f"\nClaude Code Tool Usage — {len(entries)} calls across {len(sessions)} session(s)\n")
    print(f"{'Tool':<30} {'Calls':>7} {'Out tok':>10} {'In tok':>10} {'Total tok':>10}")
    print("-" * 72)
    for tool, stats in rows:
        total = stats["out_tok"] + stats["in_tok"]
        print(
            f"{tool:<30} {stats['calls']:>7} {stats['out_tok']:>10,} "
            f"{stats['in_tok']:>10,} {total:>10,}"
        )
    print("-" * 72)
    grand = total_out + total_in
    print(f"{'TOTAL':<30} {len(entries):>7} {total_out:>10,} {total_in:>10,} {grand:>10,}")
    print()


# ── OTel export ───────────────────────────────────────────────────────────────


def _export_otel(entries: list[dict], endpoint: str) -> None:
    """Export entries as OTel spans to an OTLP endpoint."""
    if not HAS_OTEL:
        print(
            "ERROR: opentelemetry-sdk not installed. Install with:\n"
            "  pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-exporter-otlp-proto-grpc",
            file=sys.stderr,
        )
        sys.exit(1)

    resource = Resource(attributes={"service.name": SERVICE_NAME})
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(SERVICE_NAME)

    print(f"Exporting {len(entries)} spans to {endpoint}…")
    for entry in entries:
        ts_ns = int(entry.get("ts", 0) * 1e9)
        with tracer.start_as_current_span(
            name=f"claude.tool.{entry.get('tool', 'unknown')}",
            start_time=ts_ns,
        ) as span:
            span.set_attribute("claude.tool", entry.get("tool", "unknown"))
            span.set_attribute("claude.session_id", entry.get("sid", ""))
            span.set_attribute("claude.est_out_tokens", entry.get("est_out_tok", 0))
            span.set_attribute("claude.est_in_tokens", entry.get("est_in_tok", 0))
            span.set_attribute("claude.resp_bytes", entry.get("resp_bytes", 0))
            span.set_attribute("claude.inp_bytes", entry.get("inp_bytes", 0))

    provider.force_flush()
    provider.shutdown()
    print(f"✓ Exported {len(entries)} spans to {endpoint}")


# ── Tail mode ─────────────────────────────────────────────────────────────────


def _tail(path: Path) -> None:
    """Follow model_usage.jsonl and print new entries as they arrive."""
    print(f"Following {path} (Ctrl+C to stop)…")
    seen = 0
    try:
        while True:
            entries = _load_entries(path)
            for entry in entries[seen:]:
                ts = entry.get("ts", 0)
                tool = entry.get("tool", "?")
                out = entry.get("est_out_tok", 0)
                inp = entry.get("est_in_tok", 0)
                print(f"{ts:.3f}  {tool:<30}  out={out:>6}  in={inp:>6}")
            seen = len(entries)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopped.")


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Claude Code telemetry to OTel or console")
    parser.add_argument(
        "--since",
        type=float,
        metavar="SECONDS",
        help="Only include entries from the last N seconds",
    )
    parser.add_argument(
        "--top",
        type=int,
        metavar="N",
        help="Show only top N tools by token usage",
    )
    parser.add_argument(
        "--tail",
        action="store_true",
        help="Follow the log file and print new entries (like tail -f)",
    )
    parser.add_argument(
        "--otlp",
        nargs="?",
        const=DEFAULT_OTLP_ENDPOINT,
        metavar="ENDPOINT",
        help=f"Export spans to OTLP endpoint (default: {DEFAULT_OTLP_ENDPOINT})",
    )
    parser.add_argument(
        "--log",
        default=str(LOG_FILE),
        metavar="PATH",
        help=f"Path to model_usage.jsonl (default: {LOG_FILE})",
    )
    args = parser.parse_args()

    log_path = Path(args.log)

    if args.tail:
        _tail(log_path)
        return 0

    entries = _load_entries(log_path, since=args.since)

    if args.otlp:
        _export_otel(entries, args.otlp)
    else:
        _console_summary(entries, top=args.top)

    return 0


if __name__ == "__main__":
    sys.exit(main())
