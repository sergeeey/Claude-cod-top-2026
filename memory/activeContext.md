# Active Context — Claude Code Config v3.2.0

## Last Updated
2026-04-04

## Scope Fence
- **Goal:** Maintain and improve Claude Code Config — production-grade hook/agent/skill system
- **Boundary:** hooks/, agents/, skills/, tests/, memory/, docs/, rules/, .github/workflows/
- **Done when:** CI green, coverage ≥ 45%, 5 zero-coverage hooks tested, eval in CI
- **NOT NOW:** new hook features, MCP server changes, agent team restructuring, RAG layer

## Current State [VERIFIED 2026-04-04]
- Tests: 563 passing (was 395)
- Coverage: 45% (was 38%) — goal in ci.yml now updated
- Hooks: 39 files across 25 events, 31 handlers in settings.json
- Agents: 13 active + 3 teams
- Skills: 17 total (8 core + 9 extensions)
- Eval: 6 TCs in tests/eval/, now integrated in CI (weekly + workflow_dispatch)

## Recent Decisions
- `webhook_notify.py`: fixed regex replacement `\1=[REDACTED]` → `[REDACTED]`
  (all groups were non-capturing `(?:...)`, Python 3.13 raised PatternError)
- Coverage gate raised: `--fail-under=38` → `--fail-under=45`
- Eval job: runs on `workflow_dispatch` + `schedule` only, `continue-on-error: true`

## Active Gaps (prioritized)
1. **P1** — scripts/ still 0% coverage (doctor.py 251 lines, weekly_review.py 76 lines)
2. **P1** — mypy scope: only hooks/ + scripts/redact.py, not full scripts/
3. **P2** — memory/decisions.md needs more ADR entries from git history
4. **P2** — pytest on Windows (only install.ps1 smoke tested)

## Quick Access
- Hook entry points: `hooks/*.py`
- CI: `.github/workflows/ci.yml`
- Eval corpus: `tests/eval/TC-*.md` (run: `bash tests/eval/run_eval.sh`)
- Observability: `scripts/weekly_review.py`, `scripts/metrics_collector.py`
- Config audit: `scripts/doctor.py`, `scripts/config_audit_scan.py`

## Agent Memory Notes
- `reviewer` (memory:project) — focus: hook test coverage, regex bugs
- `sec-auditor` (memory:project) — focus: SSRF in webhook_notify, PII redaction
- `navigator` (memory:user) — user prefers direct answers, no filler
- `explorer` (memory:local) — hooks/ and tests/ are the hot paths
