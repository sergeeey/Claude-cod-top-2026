# Goals — Claude-cod-top-2026 (обновлено 2026-06-20)

## Завершено (2026-04 → 2026-06)
- ✅ Coverage 81% (CI/Linux canonical, threshold 75%)
- ✅ 1387 тестов, ruff clean, CI green (3.11 + 3.12 + windows-install)
- ✅ Obsidian vault 2136+ заметок, 6 MOCs, graph colorGroups configured
- ✅ HOT/WARM/COLD attention decay — knowledge_librarian (PR #106)
- ✅ hook_metrics.py CLI dashboard + telemetry (hook_triggers.jsonl)
- ✅ mcp-bouncer v0.1.0 → PyPI ✅
- ✅ Perelman Audit: claim_entropy + no-collapse tests + perelman-audit.md
- ✅ Counterfactual Frame: Step -0.5 в FL stack, claim.md секция
- ✅ claim_entropy_tracker hook (PostToolUse → experiments/**/claim.md)
- ✅ P1 хуки: null_results_pre_check + promotion_gate_guard (40 тестов)
- ✅ Sync 19 global hooks → git tracking (80 .py в hooks/)
- ✅ OSA-HC: Evaporating Cloud, Escape Point, Kill Analysis, CDT Protocol, Rescue Layer
- ✅ Assumption Dependency Graph: depends_on в claim.md, Principal Assumption rule
- ✅ META_GRAPH_V8 registered (139k nodes / 197k edges / 29 repos)
- ✅ data_bridge.py — семантический мост META_GRAPH_V8 ↔ Obsidian (2026-06-20)

## Текущие / открытые
- ⏳ **install.sh on sboi** — последний пункт Scope Fence ("Done when: install.sh на трёх машинах")
- ⏳ **Distribution Sprint Step 3** — Habr пост (на hold у пользователя)
- ⏳ **Distribution Sprint Step 4** — 7-day metrics (статус требует проверки)

## Scope Fence
- **Done when:** install.sh работает на трёх машинах, CI зелёный, coverage ≥ 81%
- **NOT NOW:** GUI, web dashboard, SaaS, публикация в marketplace

## Cleanup note (2026-07-06)
Removed 44 duplicate "Carried from compaction" blocks (2026-06-21 → 2026-07-06),
all repeating a single stale "merge PR #57" note — PR #57 merged 2026-04-12,
long before the first duplicate appeared. Root cause was two bugs in
`hooks/pre_compact.py`: `save_pending_to_goals()` had no dedup check, and
`_trim_old_entries()` only scanned section *bodies* for dates, missing dates
embedded in headings (e.g. "## Retrospective [2026-04-12]") that would have
let the source line age out naturally. Both fixed with regression tests.
