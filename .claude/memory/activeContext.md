# activeContext.md — Claude-cod-top-2026

## Current Focus
PR #38 открыт: `feat/test-coverage-boost-45pct` → main
CI статус: все 4 чека зелёные после fix plugin.json (коммит 3b5cdfa)

## Project State
- **Version:** 3.2.0
- **Branch:** feat/test-coverage-boost-45pct
- **Tests:** 563 passing
- **Coverage:** 45% (gate: --fail-under=45)
- **Smoke tests:** 82/82 passed

## Architecture
- `hooks/` — 40 .py файлов, 25 событий в settings.json
- `agents/` — 13 агентов + 3 команды (build/review/research squad)
- `skills/` — 14 skills (7 core + 7 extensions)
- `tests/` — 23 тест-файла, pytest + bash smoke
- `rules/` — 8 markdown-правил
- `mcp-profiles/` — 3 профиля (core / deploy / science)

## Open PRs
- #38 test: coverage 38→45% + eval в CI (текущая ветка) — OPEN, CI green
- #28 feat: Speed Mode + Causal Debugging — OPEN, CI failing
- #18 docs: README visual polish — OPEN

## Recent Decisions
- Coverage gate: 38% → 45% (ADR зафиксирован в decisions.md)
- webhook_notify.py: regex backreference bug исправлен (Python 3.13 совместимость)
- Eval job добавлен в CI как non-blocking (continue-on-error: true)

## Next Steps
1. Merge PR #38 в main
2. Coverage 45% → 70% (следующий спринт)
3. Eval suite расширить до 5+ сценариев
4. PR #28 — починить CI (Speed Mode)

## Test Status
2026-04-05: 563 passed, 0 failed, coverage 45%
