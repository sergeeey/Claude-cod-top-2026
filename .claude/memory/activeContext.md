# activeContext.md — Claude-cod-top-2026

## Scope Fence
- **Goal:** production-ready Claude Code config для переиспользования в любых проектах
- **Boundary:** только hooks/ agents/ skills/ rules/ — не трогать внешние проекты
- **Done when:** install.sh работает на trёх машинах, CI зелёный, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, публикация в marketplace

## Current Focus
Спринт завершён. PR #44 смержен в main. Готов к следующему.


## Project State
- **Version:** 3.3.0
- **Branch:** main
- **Tests:** 726 passing
- **Coverage:** 86% (hooks/)
- **Smoke tests:** 82/82 passed
- **Open PRs:** 1 (feat/social-engineering-guard-confirm-mode)


## Architecture
- `hooks/` — 42 хука (.py) + utils.py + learning_tips.py, 25 событий в settings.json
- `agents/` — 13 агентов + 3 команды (build/review/research squad)
- `skills/` — 17 skills (8 core + 9 extensions)
- `tests/` — 24 тест-файла, pytest + bash smoke
- `rules/` — 8 markdown-правил
- `mcp-profiles/` — 3 профиля (core / deploy / science)
- `assets/` — banner.svg (animated) + pipeline.svg + preview_design.html


## Recent Merges
- #43 fix: sync metrics — 712 tests, 86% coverage, 17 skills
- #42 feat: Speed Mode (`fast:`) + Causal Debugging
- #41 feat: Learning loop — yellow tips after every commit + session start
- #40 feat: Coverage 45%→86% + cyberpunk visual identity (banner.svg, pipeline.svg)


## Key Features Added This Sprint
- **Social Engineering Guard:** `input_guard.py` — 8 regex-ветвей против prompt injection
- **Confirm / Acceptor Mode:** `keyword_router.py` — Power Mode с явными DONE WHEN / FAIL IF критериями
- **hook_main() timeout:** `utils.py` — daemon-thread с fail-open (exit 0), блокировок больше нет
- **GitNexus docs:** CLAUDE.md + AGENTS.md добавлены в репо (2586 символов, 47 execution flows)


## Install Command (for other projects)
```bash
bash install.sh --profile=standard --non-interactive
```


## Test Status
2026-04-09: 726 passed, 0 failed, coverage 86%


## Auto-commit log
- [2026-04-09 08:24] `fa04518`: feat: social engineering guard + confirm mode + hook_main timeout (#44)
- [2026-04-09 08:20] `0c2f589`: fix: ruff lint — E501 line length, F401 unused import, I001 import order
- [2026-04-09] `d246e2d`: feat: social engineering guard + confirm mode + hook_main timeout
- [2026-04-06] `c348dd0`: feat: Speed Mode + Causal Debugging (PR #42)
- [2026-04-05] `4e4aa57`: feat: learning loop — yellow tips (PR #41)
- [2026-04-05] `840a8f3`: feat: coverage 45%→86% + cyberpunk visual identity (PR #40)
- [2026-04-05] `a164d87`: chore: add requirements.txt (PR #39)
