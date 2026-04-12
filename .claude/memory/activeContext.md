# activeContext.md — Claude-cod-top-2026

## Scope Fence
- **Goal:** production-ready Claude Code config для переиспользования в любых проектах
- **Boundary:** только hooks/ agents/ skills/ rules/ — не трогать внешние проекты
- **Done when:** install.sh работает на trёх машинах, CI зелёный, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, публикация в marketplace




## Current Focus
PR #55 готов к merge (807 тестов, 0 failed). Содержит: scientific-research skill + plan-mode-guard milestone fix + wiki index.md (Karpathy map) + prompt_wiki_inject + wiki_reminder + recursion guard. Следующее: merge #55 → install.sh на 2-й машине (Scope Fence Done When).




## Project State
- **Version:** 3.5.0
- **Branch:** feat/scientific-research-and-fixes → PR #55 open
- **Tests:** 807 passing
- **Coverage:** 86% (hooks/)
- **Smoke tests:** 82/82 passed
- **Open PRs:** 1 (#55)




## Architecture
- `hooks/` — 49 хуков (.py) + utils.py + learning_tips.py, 27 событий в settings.json
- `agents/` — 14 агентов + 3 команды (build/review/research squad)
- `skills/` — 26 skills (8 core + 18 extensions)
- `tests/` — 37 тест-файлов, pytest + bash smoke
- `rules/` — 9 markdown-правил
- `mcp-profiles/` — 3 профиля (core / deploy / science)
- `assets/` — banner.svg (animated) + pipeline.svg + preview_design.html




## Recent Merges
- #54 feat: 5 obsidian skills + daily vault refresh cron
- #53 feat: CogniML integration + auto-detect new projects at session start
- #52 feat: Second Brain 3.0 — ACE Reflector, Syntax Guard, Knowledge Librarian, Wikilinks
- #51 feat: Raw→Wiki pipeline (session_save.py + raw-to-wiki skill)




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
- **Wiki Index (Karpathy map):** `session_save.py` Step 5 — генерирует index.md из wiki/ (O(1) vs O(N) grep)
- **Scientific Research skill:** KILL_CRITERIA + baseline + red team + falsification gates
- **plan_mode_guard milestones:** алерт только на {3, 5, 10, 20, 30, 50} файлах — конец alert fatigue
- **prompt_wiki_inject:** UserPromptSubmit — инжекция wiki перед каждым промтом (не только SessionStart)
- **wiki_reminder:** Stop hook — детектор решений (2+ keywords EN+RU) + debounce 5 мин
- **Recursion guard:** `CLAUDE_INVOKED_BY` в session_save + auto_capture — защита от Agent SDK loops




## Install Command (for other projects)
```bash
bash install.sh --profile=standard --non-interactive
```




## Test Status
2026-04-12: 807 passed, 0 failed, coverage 86%




## Retrospective [2026-04-09]
- Worked: markdown-only → direct Edit без worktree; ruff --fix одной командой [REPEAT]
- Avoid: squash merge с 2+ коммитами — второй теряется; worktree для markdown — overhead [AVOID]
- Next: merge PR #55 → install.sh на 2-й машине




## Auto-commit log
- [2026-04-12 17:xx] `772fb58`: feat: UserPromptSubmit wiki inject + Stop wiki reminder + recursion guard
- [2026-04-12 17:xx] `3a4b0c1`: fix: 807 tests green — WIKI_INDEX mock + milestone assertion
- [2026-04-12 15:25] `a9b45ba`: feat: wiki index.md — Karpathy navigation map for knowledge base
- [2026-04-12 15:16] `3fbbb6e`: feat: scientific-research skill + plan-mode-guard milestone alerts
- [2026-04-12 14:50] `6287505`: feat: add 5 obsidian skills + daily vault refresh cron
- [2026-04-12 14:41] `3179a60`: feat: auto-detect new projects at session start (#53)
- [2026-04-12 13:56] `74475cb`: feat: auto_capture.py — automatic git commit + test failure → raw/ notes
- [2026-04-12 12:10] `f6125fc`: feat: populate_vault.py — seed Obsidian from git/CogniML/patterns/retro
- [2026-04-12 11:36] `a4d24c3`: feat: CogniML integration — semantic search fallback + wiki push (#53)
- [2026-04-12 11:30] `eea259d`: feat: Second Brain 3.0 — ACE Reflector, Syntax Guard, Knowledge Librarian, Wikilinks (#52)
- [2026-04-09] `9a7a99a`: feat: Raw→Wiki pipeline (#51) — 755 tests, 20 skills
- [2026-04-09] Sprint 3: PRs #44 #45 #46 merged — 746 tests, 9 rules, 18 skills
- [2026-04-06] `c348dd0`: feat: Speed Mode + Causal Debugging (PR #42)
- [2026-04-05] `840a8f3`: feat: coverage 45%→86% + cyberpunk visual identity (PR #40)
