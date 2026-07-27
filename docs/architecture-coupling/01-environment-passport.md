# 01 — Environment Passport

Субъект анализа: `repo-fresh/` — канонический git-клон `sergeeey/Claude-cod-top-2026`,
HEAD `3f2807b`, working tree clean. Рабочая копия `Claude-cod-top-2026-main/` — более старый
снапшот того же проекта (расхождения зафиксированы `diff -rq`); анализ ведётся по канону.
Workspace-корень `C:\Claude-cod-top-2026-main` сам по себе git-репозиторием не является.

| Параметр | Результат | Evidence | Confidence |
|---|---|---|---|
| Languages | Python 3.11+ (hooks/scripts/tests: 215 files), Markdown (база знаний: skills/rules/agents/docs), JSON (конфигурация), Bash/PowerShell (install) | `pyproject.toml` requires-python ">=3.11"; подсчёт файлов | [VERIFIED] HIGH |
| Frameworks | Нет web-фреймворка. Платформа — Claude Code plugin API (hooks events, skills, agents); stdlib-only рантайм хуков | `hooks/settings.json`, `.claude-plugin/plugin.json`; `requirements.txt` | [VERIFIED] HIGH |
| Build system | Нет сборки как таковой; ruff + mypy + pytest (2212 tests заявлено в README), install.sh/install.ps1 | `pyproject.toml` [tool.ruff/mypy/pytest] | [VERIFIED] HIGH |
| Runtime topology | Event-driven: Claude Code вызывает хуки как независимые короткоживущие процессы (stdin JSON → stdout JSON); 88 регистраций на 25 типов событий (SessionStart, PreToolUse, PostToolUse…) | `hooks/settings.json` разбор | [VERIFIED] HIGH |
| Module structure | Плоский `hooks/` (91 .py), `scripts/` (29), `tests/` (88), знания: `skills/` (123 skills), `rules/`, `agents/`, `claude-md/`, `commands/`; пакетов внутри hooks нет | листинг, AST-скан | [VERIFIED] HIGH |
| Deployment units | 1: плагин целиком (marketplace install); профили standard/minimal | `.claude-plugin/plugin.json`, README install | [VERIFIED] HIGH |
| Data stores | Файловые: `.claude/memory/*.md` (activeContext, patterns, decisions), `~/.claude/state/`, `~/.claude/logs/*.jsonl`, `experiments/`, `null_results/`, `pearl_registry/` | скан path-литералов в 215 .py | [VERIFIED] HIGH |
| Communication styles | Файловые контракты (shared markdown/JSONL), stdin/stdout JSON hook-protocol, subprocess git; сети между компонентами нет | AST/regex скан | [VERIFIED] HIGH |
| Team ownership | Single developer («Single-developer dogfood» — самоописание); CODEOWNERS нет | `.claude-plugin/plugin.json` description; поиск CODEOWNERS | [VERIFIED] HIGH |
| Existing tests | tests/: 88 файлов; coverage-политика в pyproject с явным omit-списком env-зависимых хуков | `pyproject.toml`, листинг | [VERIFIED] HIGH |
| Existing observability | `~/.claude/logs/hook_triggers.jsonl` (писатель — utils.log_hook_trigger), `hook_observability.py`, `scripts/hook_metrics.py`, `scripts/otel_exporter.py` (требует живой OTel endpoint) | grep, pyproject omit-note | [VERIFIED] MEDIUM (полнота покрытия не измерена) |
| Existing architecture rules | `tests/test_structure.py` — count-consistency gate (прецедент fitness function, рождён из дефекта 87-vs-88); ruff import-sort; правил направления импортов (import-linter и т.п.) нет | чтение test_structure.py | [VERIFIED] HIGH |

## Ограничения паспорта

- <unknown>Team boundaries: один разработчик — socio-technical graph (раздел 9.5) вырожден, выводы о координации команд неприменимы; вместо них используется deployment_coordination_count (файлов на изменение).</unknown>
- <unknown>Runtime coupling: production traces/metrics отсутствуют (хуки — локальные процессы; `hook_triggers.jsonl` на анализируемой машине не является репрезентативной телеметрией репозитория). Runtime-слой помечен unavailable, static analysis его НЕ подменяет.</unknown>
- Business domain (inferred): «Evidence-aware Goal Operating Layer» — надстройка над Claude Code для анти-галлюцинационного контроля (evidence gates, validation-theater detection, память, research-методология). [VERIFIED из самоописания plugin.json]
