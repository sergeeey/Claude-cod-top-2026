# Checkpoint: PR #106 — Attention Decay Layer Merged
**Date:** 2026-05-06  
**Trigger:** clean exit after 10 PRs merged this session

## State at checkpoint

| Metric | Value |
|--------|-------|
| Tests | 1192 (was 1077 at session start, +115) |
| Coverage | 81% CI/Linux canonical |
| Hooks | 57 active |
| Open PRs | 0 |
| CI | GREEN ✅ (3.11 + 3.12 + windows-install) |
| ruff | ✅ |
| mypy | ✅ |

## PRs merged this session
#97 #98 #99 #100 #101 #102 #103 #104 #105 **#106**

## Architecture additions (this session)
- **PR #106** — HOT/WARM/COLD attention scoring in `knowledge_librarian.py`
  - Top-10 wiki candidates → score = 50% keyword overlap + 50% (recency × frequency)
  - HOT (≥0.65): inline ~300 char snippet injected at SessionStart
  - WARM (<0.65): `[[Title]]` ref only
  - Security fixes before merge (review-squad):
    - `[FIXED-HIGH]` Path traversal: `resolve()+relative_to(WIKI_DIR)` + stem sanity check
    - `[FIXED-HIGH]` Prompt injection: `redact_secrets()` applied to wiki content before inject
    - `[FIXED-LOW]` OOM guard: `stat().st_size > 256_000` before `read_text()`
- **PR #101** — `hook_metrics.py` CLI dashboard aggregating `hook_triggers.jsonl`
- **PRs #97-#100** — distribution sprint Step 1+2 (telemetry + anti-hallucination guide)

## Architectural significance
PR #106 closes the last architectural gap from the external 31-feature audit.
Methodology triple stack: online enforcement (57 hooks) + offline aggregation (`hook_metrics.py`) + **dynamic context decay** (attention scoring).

## Open items
- **SKEPTIC GAP #5:** independent test set (4/5 closed)
- **PENDING:** install.sh on sboi machine (smoke-tested locally only)
- **MONITOR:** input_guard false-positive on `mcp__context7__query-docs` — wait for 7d data before narrowing regex
- **DISTRIBUTION:** Step 3 (Habr post) on user hold; Step 4 (7-day metrics) Day 3 of 7

## Next session entry point
1. `python scripts/hook_metrics.py --window 7` — check Day 4+ telemetry
2. Decide on input_guard regex narrowing (threshold: 7d data)
3. Skeptic gap #5 — design independent test set (real-world data, not synthetic)
4. install.sh smoke test on sboi

## Lesson captured
`[AVOID×1]` — review-squad on security-relevant hooks (FS access, context injection) catches HIGH vulns in 70 sec. Cost: 70s agent + 30min fixes. Alternative: deterministic exploit chain in mainline. Always run review-squad before merging hooks that touch filesystem or inject content into context.
