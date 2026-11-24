# Trend Watch — 2026-10-15

#trends #claude-code

Период: 2026-10-08 00:00 — 2026-10-15 00:00, Asia/Qyzylorda (семь завершённых суток).
Расписание из задания: понедельник, 09:00 Asia/Qyzylorda. Этот запуск выполняет обзор; настройка/активность расписания не проверена и не изменена.
Классификация изменений: TRIVIAL — только отчёт и черновик issue. Оценки impact ниже относятся к находкам, а не к внесённым изменениям.

## [Claude Code / Anthropic] — Исправление fail-open защитных hooks на Windows

**What changed:** [VERIFIED] 14 октября в v2.1.299 исправлен пропуск PreToolUse/PermissionRequest при отсутствии Git for Windows и явного shell.
**Impact on this repo:** HIGH. [VERIFIED] Локально установлен Claude Code 2.1.296. [CODE] В hooks/settings.json — 19 PreToolUse и 1 PermissionRequest, все без shell. [INFERRED] Это приоритет проверки требований к runtime при установке на Windows; наличие всех условий обхода на этой машине не установлено. Проверить успешный запуск, deny, timeout и отказ запуска guard в изолированном окружении.
**File to update:** rules/security.md — требования к runtime/оболочке; hooks/permission_policy.py и hooks/security_verify.py — только если проверка совместимости покажет необходимость.
**Source:** [Anthropic v2.1.299, 2026-10-14](https://github.com/anthropics/claude-code/releases/tag/v2.1.299)

## [Claude Code / Anthropic] — UserPromptSubmit выполняется до раскрытия skills

**What changed:** [VERIFIED] v2.1.299 перенёс UserPromptSubmit перед раскрытием skill/slash command. Собственный frontmatter-hook skill впервые срабатывает на следующем prompt.
**Impact on this repo:** MED. [CODE] Зарегистрировано 11 UserPromptSubmit hooks, включая keyword_router.py и null_results_pre_check.py. [INFERRED] Проверить маршрутизацию и предупреждения на обычном prompt и вызове /skill: нельзя предполагать наличие раскрытого текста skill во входе. Регрессия локально не воспроизводилась.
**File to update:** hooks/keyword_router.py и hooks/null_results_pre_check.py — кандидаты для проверки; изменение кода пока не обосновано.
**Source:** [Anthropic v2.1.299, 2026-10-14](https://github.com/anthropics/claude-code/releases/tag/v2.1.299)

## [Python async patterns] — Python 3.15 добавил TaskGroup.cancel()

**What changed:** [VERIFIED] Python 3.15.0 вышел 9 октября. TaskGroup.cancel() позволяет досрочно завершать группу задач без вспомогательной задачи, бросающей специальное исключение. Депрекации asyncio policy system и asyncio.iscoroutinefunction() — ранее объявленные изменения с удалением в 3.16, не новые депрекации этой недели.
**Impact on this repo:** LOW. [CODE] Поиск asyncio/anyio в Python-файлах hooks/, scripts/ и tests/ не дал совпадений. hooks/async_wrapper.py использует subprocess.Popen, а pyproject.toml сохраняет Python >=3.11. Не вводить API 3.15 в общий путь без отдельного решения о совместимости; срочная миграция не нужна.
**File to update:** rules/coding-style.md — только при добавлении рекомендаций для нового async-кода; hooks/async_wrapper.py менять по этой находке не требуется.
**Source:** [Python 3.15.0 release](https://www.python.org/downloads/release/python-3150/), [What's new — asyncio](https://docs.python.org/3.15/whatsnew/3.15.html#asyncio)

## [Security] — CVE-2026-108583: SSRF через zotero-mcp

**What changed:** [VERIFIED] CVE опубликована 10 октября, раскрытие датировано 9 октября. В zotero-mcp 0.10.0–0.14.1 инструмент zotero_add_by_url может обращаться к внутренним адресам, в том числе через redirects; prompt injection может направить агента к такому вызову.
**Impact on this repo:** LOW. [CODE] zotero-mcp не найден в requirements.txt, pyproject.toml и mcp-profiles/. Это применимый класс угроз для MCP-окружения, а не доказанная уязвимость репозитория. hooks/webhook_notify.py уже содержит проверку private/loopback/link-local адресов; её корректность в этом обзоре не тестировалась. Произвольные внешние и глобальные MCP-установки не инвентаризировались.
**File to update:** rules/security.md — правило проверки сетевых назначений у подключаемых MCP-серверов; обязательного исправления hooks/webhook_notify.py не выявлено.
**Source:** [CVE Program: CNA record CVE-2026-108583](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/108xxx/CVE-2026-108583.json)

## [AI agent tooling] — Изоляция состояния при вызове agent-as-tool

**What changed:** [VERIFIED] Microsoft Agent Framework Python 1.21.0 от 8 октября изолирует принадлежащее провайдеру состояние сессии при вызове агентов как tools; добавлен пример фильтрации ответов group chat.
**Impact on this repo:** LOW. [CODE] agent-framework не найден в проверенных зависимостях; rules/delegation-contract.md уже задаёт scope, критерии приёмки и stop conditions. [INFERRED] Полезное дополнение при следующем изменении координации — явно задавать владельца session state и проверять отсутствие смешения контекста соседних агентов. Сам релиз не доказывает дефект текущего механизма.
**File to update:** rules/delegation-contract.md — кандидат на уточнение владения состоянием.
**Source:** [Microsoft Agent Framework python-1.21.0](https://github.com/microsoft/agent-framework/releases/tag/python-1.21.0)

## Implemented

- Подготовлены эта raw note и отдельный черновик GitHub issue.
- Целевой путь из задания: C:/Users/serge/.claude/memory/raw/trend-watch-2026-10-15.md.
- Фактический путь: D:/Claude-cod-top-2026/.claude/memory/raw/trend-watch-2026-10-15.md. Перенос в глобальную память НЕ выполнен: sandbox разрешает запись только в workspace/временные каталоги, escalation недоступен.
- HIGH issue: НЕ создан. Поиск существующих trend issues вернул пустой список. Вызов GitHub create_issue вернул: "MCP tool call requires approval, but approval policy is never".
- Готовый черновик: trend-watch-2026-10-15-issue-draft.md рядом с этой заметкой.
- Runtime, settings.json, hooks, правила и зависимости не изменялись; commit/push не выполнялись.

## Verified

- Даты релизов и CVE проверены по первичным страницам Anthropic, Python, Microsoft и записи CNA в CVE Program.
- claude --version: 2.1.296 (Claude Code).
- Разбор hooks/settings.json: PreToolUse=19, PermissionRequest=1, UserPromptSubmit=11; explicitShell=0 во всех трёх категориях.
- rg по asyncio/anyio в hooks/, scripts/, tests/ (*.py): 0 совпадений, exit=1.
- Поиск agno/zotero/langflow/mcp-remote/agent-framework в requirements.txt, pyproject.toml, mcp-profiles/: 0 совпадений, exit=1.
- Прочитаны конкретные файлы hooks и rules, указанные в находках. GitNexus MCP в сессии недоступен; модификаций символов не было.
- Существующие изменения рабочего дерева сохранены. Тесты кода, проверка exploitability и проверка поведения обновлённого Claude Code не запускались: задача ограничена мониторингом и документацией.
- Ограничения покрытия: веб-поиск не является полным аудитом всех CVE или глобально установленных пакетов; отсутствие находки не доказывает отсутствие уязвимостей.

