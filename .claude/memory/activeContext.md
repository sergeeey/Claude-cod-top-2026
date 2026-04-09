# activeContext.md — Claude-cod-top-2026

## Scope Fence
- **Goal:** production-ready Claude Code config для переиспользования в любых проектах
- **Boundary:** только hooks/ agents/ skills/ rules/ — не трогать внешние проекты
- **Done when:** install.sh работает на trёх машинах, CI зелёный, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, публикация в marketplace


## Current Focus
Raw → Wiki pipeline — расширить session_save.py для структурированного вывода из #raw заметок.



## Project State
- **Version:** 3.3.0
- **Branch:** main
- **Tests:** 746 passing
- **Coverage:** 86% (hooks/)
- **Smoke tests:** 82/82 passed
- **Open PRs:** 0



## Architecture
- `hooks/` — 42 хука (.py) + utils.py + learning_tips.py, 25 событий в settings.json
- `agents/` — 13 агентов + 3 команды (build/review/research squad)
- `skills/` — 18 skills (8 core + 10 extensions)
- `tests/` — 24 тест-файла, pytest + bash smoke
- `rules/` — 9 markdown-правил
- `mcp-profiles/` — 3 профиля (core / deploy / science)
- `assets/` — banner.svg (animated) + pipeline.svg + preview_design.html



## Recent Merges
- #49 fix: ruff lint + format (squash missed from #48)
- #48 feat: session-retrospective skill + 4-stage workflow labels
- #46 feat: Audit Verification Gate (subagent_verify.py + rules/)
- #45 feat: agent_lifecycle 100% coverage + Scope Fence + integration tests



## Key Features Added This Sprint
- **Social Engineering Guard:** `input_guard.py` — 8 regex-ветвей против prompt injection
- **Confirm / Acceptor Mode:** `keyword_router.py` — Power Mode с явными DONE WHEN / FAIL IF критериями
- **hook_main() timeout:** `utils.py` — daemon-thread с fail-open (exit 0), блокировок больше нет
- **Audit Verification Gate:** `subagent_verify.py` Check 4 + `rules/audit-verification-gate.md`
- **Session Retrospective:** новый skill `/retro` + 4-stage workflow labels в routing-policy



## Install Command (for other projects)
```bash
bash install.sh --profile=standard --non-interactive
```



## Test Status
2026-04-09: 746 passed, 0 failed, coverage 86%



## Retrospective [2026-04-09]
- Worked: markdown-only → direct Edit без worktree; ruff --fix одной командой [REPEAT]
- Avoid: squash merge с 2+ коммитами — второй теряется; worktree для markdown — overhead [AVOID]
- Next: Raw→Wiki pipeline / pre-commit print() whitelist / install.sh на 2-й машине

## Auto-commit log
- [2026-04-09 22:08] `a6f6372`: fix: ruff lint + format (squash missed second commit from #48)
- [2026-04-09] Sprint 3: PRs #44 #45 #46 merged — 746 tests, 9 rules, 18 skills
- [2026-04-09 08:24] `fa04518`: feat: social engineering guard + confirm mode + hook_main timeout (#44)
- [2026-04-09 08:20] `0c2f589`: fix: ruff lint — E501 line length, F401 unused import, I001 import order
- [2026-04-09] `d246e2d`: feat: social engineering guard + confirm mode + hook_main timeout
- [2026-04-06] `c348dd0`: feat: Speed Mode + Causal Debugging (PR #42)
- [2026-04-05] `4e4aa57`: feat: learning loop — yellow tips (PR #41)
- [2026-04-05] `840a8f3`: feat: coverage 45%→86% + cyberpunk visual identity (PR #40)
- [2026-04-05] `a164d87`: chore: add requirements.txt (PR #39)
