# Research Pipeline [EXPERIMENTAL]

Multi-agent asyncio pipeline for parallel research across 6 data sources.
Reference architecture for the `last30days` skill — replaces the monolithic
orchestrator with a staged, composable agent swarm.

## Architecture

```
Phase 0  — CONTEXT LOADING (SharedState reads activeContext.md)
Phase 1  — Discovery agents run in parallel (asyncio.gather)
              reddit · twitter · youtube · hn · web · polymarket
Phase 2  — FunnelAgent: score → dedup → cross-source boost → rank
Phase 3  — SynthesisAgent + VerifierAgent run in PARALLEL
Phase 4  — Assemble briefing, persist stats, update shared state
```

## Key modules

| File | Role |
|------|------|
| `pipeline.py` | Orchestrator — runs all 4 phases, CLI entry point |
| `discovery_agent.py` | Per-source async fetcher with unified Item schema |
| `funnel_agent.py` | Scoring (velocity × relevance × recency × quality), dedup, cross-source boost |
| `synthesis_agent.py` | Builds Markdown briefing: TL;DR, themes, voices, prompt pack |
| `synthesis_agent.py` (VerifierAgent) | Checks recency, source diversity, engagement anomalies |
| `shared_state.py` | CONTEXT LOADING backbone — reads/writes activeContext.md and JSON state |
| `CONTEXT_LOADING.md` | Protocol spec for embedding into agent system prompts |

## Status

**Reference architecture.** The pipeline wiring, scoring, dedup, synthesis, and
verifier logic are fully implemented. Discovery agents (`_fetch_*` functions in
`discovery_agent.py`) are **stubs** — they return empty lists until real API
connections are wired up.

APIs to connect: ScrapeCreators (Reddit), xAI Grok (Twitter/X),
YouTube Data API, HN Algolia (free), Brave Search (web), Polymarket REST.

## How to use when ready

```bash
# Full run — 6 sources, 30-day window
python pipeline.py "Claude Code skills 2026"

# Quick mode — 3 sources only
python pipeline.py "AI agents" --quick

# JSON stats output
python pipeline.py "fraud detection KZ" --days=14 --emit=json

# Select specific sources
python pipeline.py "asyncio patterns" --sources=hn,web,reddit
```

Output is saved to `~/Documents/Last30Days/<slug>.md`.
