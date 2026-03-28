"""
Multi-Agent Research Pipeline for last30days-skill.
Replaces the monolithic last30days.py orchestrator with a parallel
agent-based architecture: discovery → funnel → synthesis + verifier → output.

Usage:
    python pipeline.py "Claude Code skills" [--days=30] [--quick] [--emit=md]
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Local imports
sys.path.insert(0, str(Path(__file__).parent))
from agents.discovery_agent import DiscoveryAgent, Source
from agents.funnel_agent import FunnelAgent
from agents.synthesis_agent import SynthesisAgent
from agents.verifier_agent import VerifierAgent
from lib.shared_state import SharedState

PIPELINE_VERSION = "1.0.0"

# ── Sources available in parallel ────────────────────────────────────────────
ALL_SOURCES = [
    Source.REDDIT,
    Source.TWITTER,
    Source.YOUTUBE,
    Source.HN,
    Source.WEB,
    Source.POLYMARKET,
]


async def run_pipeline(
    topic: str,
    *,
    days: int = 30,
    quick: bool = False,
    emit: str = "md",
    sources: list[Source] | None = None,
    context_dir: Path | None = None,
) -> dict:
    """
    Orchestrate the full multi-agent research pipeline.

    CONTEXT LOADING: reads activeContext.md before launching agents,
    so every agent in the swarm is aware of project state.

    Returns a result dict with keys: briefing, stats, output_path.
    """
    start_ts = time.monotonic()
    state = SharedState(context_dir or Path.home() / ".claude" / "memory")

    # ── CONTEXT LOADING (Phase 0) ─────────────────────────────────────────
    context = state.load_context()
    print(f"[pipeline] CONTEXT LOADING: {len(context)} context keys loaded", flush=True)
    if context.get("current_focus"):
        print(f"[pipeline] current focus: {context['current_focus']}", flush=True)

    active_sources = sources or (ALL_SOURCES[:3] if quick else ALL_SOURCES)

    # ── PHASE 1: Parallel discovery ───────────────────────────────────────
    print(f"\n[pipeline] Phase 1 — parallel discovery ({len(active_sources)} sources)", flush=True)
    discovery_tasks = [
        DiscoveryAgent(source).run(topic, days=days, context=context) for source in active_sources
    ]
    raw_results = await asyncio.gather(*discovery_tasks, return_exceptions=True)

    # Flatten and filter errors
    all_items: list[dict] = []
    source_stats: dict[str, int] = {}
    for source, result in zip(active_sources, raw_results, strict=False):
        if isinstance(result, Exception):
            print(f"[pipeline]   {source.value}: FAILED — {result}", flush=True)
            source_stats[source.value] = 0
        else:
            items = result.get("items", [])
            source_stats[source.value] = len(items)
            all_items.extend(items)
            print(f"[pipeline]   {source.value}: {len(items)} items", flush=True)

    if not all_items:
        raise RuntimeError("All discovery agents failed — no items to process")

    # ── PHASE 2: Scoring & funnel ─────────────────────────────────────────
    print(f"\n[pipeline] Phase 2 — funnel ({len(all_items)} raw items)", flush=True)
    funnel = FunnelAgent(top_k_per_source=5 if quick else 10)
    funnel_result = await funnel.run(all_items, topic=topic)
    ranked_items = funnel_result["ranked"]
    print(f"[pipeline]   → {len(ranked_items)} items after dedup+rank", flush=True)

    # ── PHASE 3: Synthesis + Verifier (parallel) ──────────────────────────
    print("\n[pipeline] Phase 3 — synthesis + verification (parallel)", flush=True)
    synth_task = SynthesisAgent().run(ranked_items, topic=topic, context=context)
    verify_task = VerifierAgent().run(ranked_items, topic=topic)

    (synth_result, verify_result) = await asyncio.gather(synth_task, verify_task)

    print(f"[pipeline]   synthesis: {synth_result['word_count']} words", flush=True)
    print(
        f"[pipeline]   verifier:  {verify_result['confidence']} confidence, "
        f"{verify_result['flags']} flags",
        flush=True,
    )

    # ── PHASE 4: Assemble & persist ───────────────────────────────────────
    elapsed = time.monotonic() - start_ts
    stats = {
        "topic": topic,
        "days": days,
        "sources": source_stats,
        "raw_items": len(all_items),
        "ranked_items": len(ranked_items),
        "elapsed_s": round(elapsed, 1),
        "confidence": verify_result["confidence"],
        "flags": verify_result["flags"],
        "pipeline_version": PIPELINE_VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    briefing = _assemble_briefing(
        topic=topic,
        synth=synth_result,
        verify=verify_result,
        stats=stats,
    )

    output_path = _save_output(briefing, topic=topic, emit=emit)
    state.update_last_run(topic=topic, stats=stats)

    print(f"\n[pipeline] Done in {elapsed:.1f}s → {output_path}", flush=True)
    return {"briefing": briefing, "stats": stats, "output_path": str(output_path)}


def _assemble_briefing(
    topic: str,
    synth: dict,
    verify: dict,
    stats: dict,
) -> str:
    """Merge synthesis + verifier output into final Markdown briefing."""
    lines = [
        f"# {topic}",
        f"> Research briefing · {stats['days']} days · "
        f"{stats['elapsed_s']}s · confidence: **{stats['confidence']}**",
        "",
    ]
    if verify["flags"]:
        lines += [
            "## Verifier flags",
            *[f"- {f}" for f in verify["flags"]],
            "",
        ]
    lines += [synth["markdown"], ""]
    lines += [
        "---",
        "## Stats",
        "| Source | Items |",
        "|--------|-------|",
        *[f"| {s} | {n} |" for s, n in stats["sources"].items()],
        f"| **Total ranked** | **{stats['ranked_items']}** |",
    ]
    return "\n".join(lines)


def _save_output(briefing: str, topic: str, emit: str) -> Path:
    """Write briefing to ~/Documents/Last30Days/<slug>.md"""
    slug = "".join(c if c.isalnum() else "_" for c in topic)[:60].strip("_")
    out_dir = Path.home() / "Documents" / "Last30Days"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.md"
    out_path.write_text(briefing, encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="last30days multi-agent pipeline")
    parser.add_argument("topic", help="Research topic")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--emit", default="md", choices=["md", "json", "compact"])
    parser.add_argument(
        "--sources",
        default="auto",
        help="Comma-separated sources or 'auto'",
    )
    args = parser.parse_args()

    sources = None
    if args.sources != "auto":
        sources = [Source(s.strip()) for s in args.sources.split(",")]

    result = asyncio.run(
        run_pipeline(
            args.topic,
            days=args.days,
            quick=args.quick,
            emit=args.emit,
            sources=sources,
        )
    )

    if args.emit == "json":
        print(json.dumps(result["stats"], indent=2))
    elif args.emit == "compact":
        print(result["briefing"][:2000])
    else:
        print(f"\nSaved → {result['output_path']}")


if __name__ == "__main__":
    main()
