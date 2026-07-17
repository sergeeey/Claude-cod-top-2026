# Architecture Coupling Audit — verified baseline (snapshot)

Point-in-time architectural coupling audit of this repo. **Research-only** package: it
measured and recommended; it changed no production code. Preserved here so the verified
baseline is versioned rather than living outside git.

- **Baseline subject:** `repo-fresh @ 3f2807b` (2026-07-16) — see [MANIFEST.md](MANIFEST.md).
- **Start here:** [00-executive-summary.md](00-executive-summary.md) — verdict, top hotspots,
  first 5 actions. Machine-readable data in [`artifacts/architecture-coupling/`](../../artifacts/architecture-coupling/).
- **Method/evidence discipline:** most findings carry `[VERIFIED-tool]` markers; runtime
  coupling layer is explicitly marked unavailable (no production telemetry) — not faked.

## Headline

Structural coupling is already near-ideal — **0 import cycles** (215 files, 238 edges), 3
cross-module production edges, dependencies pointed at a stable core. The real cost of change
sits in **non-structural channels**: duplicated doc-count literals (change coupling), the
shared mutable `.claude/memory/` store (data coupling), and one god-utility (`hooks/utils.py`).
Blindly minimizing edges would buy nothing — the audit's own conclusion.

## Hotspot status (updated as work lands — this file is the continuity index)

| # | Hotspot | Prio | Status |
|---|---|---|---|
| HS-01 | `hooks/utils.py` god-utility (fan-in 74, 1074 LOC, 4 roles) | P1 | **pending** — Yellow refactor, own experiment |
| HS-02 | Doc-count literals duplicated across ≥9 sites | P1 | **in progress** — generation-from-disk (detection already gated; drift-3+ trigger met) |
| HS-03 | `.claude/memory/` shared mutable store | P1 | **partial** — lean activeContext + canonical decisions.md done; memory-API not built |
| HS-04 | Flat `hooks/` hides 9 latent domains | P2 | pending — needs DDD-informed package-by-domain |
| HS-05 | Dual `marketplace.json` (root vs `.claude-plugin/`) | P2 | pending — invariant test proposed |
| HS-06 | Unregistered non-library hooks | P2 | **partial** — PR #199 added "registered != working" gates |
| HS-10 | Dual-scope rules (`rules/` vs `.claude/rules/`) | P3 | **done** — canonical + stub/addendum, `TestRulesNotDuplicated` |

Full ranking with evidence, root cause, and falsification tests: [06-hotspots.md](06-hotspots.md).
Roadmap with rollback/stop-conditions: [12-refactoring-roadmap.md](12-refactoring-roadmap.md).
CI-ready fitness rules: [11-fitness-functions.md](11-fitness-functions.md).
