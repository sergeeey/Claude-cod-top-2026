# activeContext.md — Claude-cod-top-2026

## Scope Fence
- **Goal:** production-ready Claude Code config для переиспользования в любых проектах
- **Boundary:** только hooks/ agents/ skills/ rules/ — не трогать внешние проекты
- **Done when:** install.sh работает на trёх машинах, CI зелёный, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, публикация в marketplace




## Current Focus
Завершён спринт Second Brain 2.0. Следующее: install.sh на 2-й машине (Scope Fence Done When).





## Project State
- **Version:** 3.4.0
- **Branch:** main
- **Tests:** 778 passing
- **Coverage:** 86% (hooks/)
- **Smoke tests:** 82/82 passed
- **Open PRs:** 0





## Architecture
- `hooks/` — 45 хуков (.py) + utils.py + learning_tips.py, 27 событий в settings.json
- `agents/` — 13 агентов + 3 команды (build/review/research squad)
- `skills/` — 25 skills (8 core + 12 extensions + 5 obsidian)
- `tests/` — 24 тест-файла, pytest + bash smoke
- `rules/` — 9 markdown-правил
- `mcp-profiles/` — 3 профиля (core / deploy / science)
- `assets/` — banner.svg (animated) + pipeline.svg + preview_design.html





## Recent Merges
- #51 feat: Raw→Wiki pipeline (session_save.py + raw-to-wiki skill)
- #50 chore: sync activeContext + branch cleanup
- #49 fix: ruff lint + format
- #48 feat: session-retrospective skill + 4-stage workflow labels





## Key Features Added This Sprint
- **Social Engineering Guard:** `input_guard.py` — 8 regex-ветвей против prompt injection
- **Confirm / Acceptor Mode:** `keyword_router.py` — Power Mode с явными DONE WHEN / FAIL IF критериями
- **hook_main() timeout:** `utils.py` — daemon-thread с fail-open (exit 0), блокировок больше нет
- **Audit Verification Gate:** `subagent_verify.py` Check 4 + `rules/audit-verification-gate.md`
- **Session Retrospective:** новый skill `/retro` + 4-stage workflow labels в routing-policy
- **Raw→Wiki pipeline:** `session_save.py` Step 4 — автоконвертация заметок из `raw/` в `wiki/`
- **ACE Reflector:** `ace_reflector.py` — SubagentStop hook, классифицирует подход, обновляет playbook.md
- **Syntax Guard:** `syntax_guard.py` — PreToolUse(Write/Edit) AST-валидация Python/JS до записи на диск
- **Knowledge Librarian:** `knowledge_librarian.py` — SessionStart, инжектирует wiki + patterns + playbook в контекст
- **Wikilinks в wiki:** `session_save.py` — автоматические [[Related Notes]] по тегам
- **5 Obsidian skills:** obsidian-markdown, obsidian-cli, obsidian-bases, json-canvas, defuddle





## Install Command (for other projects)
```bash
bash install.sh --profile=standard --non-interactive
```





## Test Status
2026-04-09: 755 passed, 0 failed, coverage 86%





## Retrospective [2026-04-09]
- Worked: markdown-only → direct Edit без worktree; ruff --fix одной командой [REPEAT]
- Avoid: squash merge с 2+ коммитами — второй теряется; worktree для markdown — overhead [AVOID]
- Next: Raw→Wiki pipeline / pre-commit print() whitelist / install.sh на 2-й машине



## Auto-commit log
- [2026-04-12 13:56] `74475cb`: feat: auto_capture.py — automatic git commit + test failure → raw/ notes
- [2026-04-12 12:10] `f6125fc`: feat: populate_vault.py — seed Obsidian from git/CogniML/patterns/retro
- [2026-04-12 11:36] `a4d24c3`: feat: CogniML integration — semantic search fallback + wiki push (#53)
- [2026-04-12 11:30] `eea259d`: feat: Second Brain 3.0 — ACE Reflector, Syntax Guard, Knowledge Librarian, Wikilinks (#52)
- [2026-04-09] `9a7a99a`: feat: Raw→Wiki pipeline (#51) — 755 tests, 20 skills
- [2026-04-09 22:08] `a6f6372`: fix: ruff lint + format (squash missed second commit from #48)
- [2026-04-09] Sprint 3: PRs #44 #45 #46 merged — 746 tests, 9 rules, 18 skills
- [2026-04-09 08:24] `fa04518`: feat: social engineering guard + confirm mode + hook_main timeout (#44)
- [2026-04-09 08:20] `0c2f589`: fix: ruff lint — E501 line length, F401 unused import, I001 import order
- [2026-04-09] `d246e2d`: feat: social engineering guard + confirm mode + hook_main timeout
- [2026-04-06] `c348dd0`: feat: Speed Mode + Causal Debugging (PR #42)
- [2026-04-05] `4e4aa57`: feat: learning loop — yellow tips (PR #41)
- [2026-04-05] `840a8f3`: feat: coverage 45%→86% + cyberpunk visual identity (PR #40)
- [2026-04-05] `a164d87`: chore: add requirements.txt (PR #39)
