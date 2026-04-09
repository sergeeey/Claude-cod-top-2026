# activeContext.md — Claude-cod-top-2026

## Current Focus
Репо приведён в порядок. Готов к использованию в других проектах.


## Project State
- **Version:** 3.2.0
- **Branch:** main
- **Tests:** 712 passing
- **Coverage:** 86% (hooks/)
- **Smoke tests:** 82/82 passed
- **Open PRs:** 0


## Architecture
- `hooks/` — 40 хуков (.py) + utils.py + learning_tips.py, 25 событий в settings.json
- `agents/` — 13 агентов + 3 команды (build/review/research squad)
- `skills/` — 17 skills (8 core + 9 extensions)
- `tests/` — 24 тест-файла, pytest + bash smoke
- `rules/` — 8 markdown-правил
- `mcp-profiles/` — 3 профиля (core / deploy / science)
- `assets/` — banner.svg (animated) + pipeline.svg


## Recent Merges
- #42 feat: Speed Mode (`fast:`) + Causal Debugging
- #41 feat: Learning loop — yellow tips after every commit + session start
- #40 feat: Coverage 45%→86% + cyberpunk visual identity (banner.svg, pipeline.svg)
- #39 chore: requirements.txt


## Key Features Added This Sprint
- **Learning Loop:** learning_tracker.py + learning_tips.py (24 tips L1→L5)
  При каждом git commit → жёлтый бокс в терминал → запись в learning_log.md
- **Animated SVG banner:** assets/banner.svg (1200×400, CLAUDE/CODE/HOOKS neon)
- **Pipeline diagram:** assets/pipeline.svg (6 нод с анимированными стрелками)
- **Speed Mode:** `fast:` или `just do:` префикс → без объяснений
- **mentor-protocol v3:** каждые 2-3 ответа (был 5-7)


## Install Command (for other projects)
```bash
bash install.sh --profile=standard --non-interactive
```


## Test Status
2026-04-06: 712 passed, 0 failed, coverage 86%


## Auto-commit log
- [2026-04-06] `c348dd0`: feat: Speed Mode + Causal Debugging (PR #42)
- [2026-04-05] `4e4aa57`: feat: learning loop — yellow tips (PR #41)
- [2026-04-05] `840a8f3`: feat: coverage 45%→86% + cyberpunk visual identity (PR #40)
- [2026-04-05] `a164d87`: chore: add requirements.txt (PR #39)
