# Trend Watch — 2026-11-15

#trends #claude-code

Период: 2026-11-08 00:00 — 2026-11-15 00:00, Asia/Qyzylorda; семь завершённых суток.
Расписание из задания: понедельник 09:00 Asia/Qyzylorda. Этот отчёт — выполненный обзор; наличие активного расписания не подтверждено, расписание не создавалось и не изменялось. Инструмента управления автоматизациями в сессии нет.
Классификация изменений: TRIVIAL — только новая заметка и черновик issue.
Impact — приоритет для этого репозитория, не CVSS и не утверждение о воспроизведённой эксплуатации. File to update — кандидат на последующую работу, а не уже изменённый файл.

## [Claude Code / Anthropic] — Исправления исполнения hooks и проверок разрешений

**What changed:** [VERIFIED] Claude Code v2.1.321 опубликован 9 ноября. Исправлены потеря PreToolUse ask при конкурирующем defer, подмена файла с большим hook output, проверки защищённых назначений cp/mv и отдельные ошибки sandbox/permissions. Также исправлены пересылка OAuth-секретов при редиректе MCP и пропуск ответа mcp_tool hook размером более 16 MiB.
**Impact on this repo:** HIGH. [VERIFIED] claude --version: 2.1.319. [CODE] hooks/settings.json запускает несколько PreToolUse command hooks на Bash и Edit|Write; security_verify.py возвращает ask. [INFERRED] Приоритет — проверка и обновление host runtime до версии с исправлениями, поскольку он исполняет решения hooks. [UNCERTAIN] Конкретный сбой локально не воспроизводился; первая затронутая версия upstream не указана. В shipped registrations не найдены defer и тип mcp_tool; matcher mcp__* у command hook не равен типу mcp_tool. Глобальная live-конфигурация не проверялась.
**File to update:** rules/security.md — зафиксировать проверенный runtime baseline; hooks/security_verify.py и hooks/permission_policy.py — точки интеграционной проверки, изменение кода только по результатам.
**Source:** [Anthropic v2.1.321](https://github.com/anthropics/claude-code/releases/tag/v2.1.321)

## [Python async patterns] — Исправления графа ожидания задач asyncio

**What changed:** [VERIFIED] В main CPython 10 ноября исправлено сохранение лишних awaited_by связей при некорректных аргументах asyncio.gather(); 11 ноября добавлена недостающая связь с создающей задачей во время первого eager step. Даты проверены по commit metadata, поведение — по diff. Это изменения ветки разработки; включение в опубликованный стабильный релиз не установлено. Новых депрекаций или обязательной замены async API за окно по проверенным источникам не подтверждено.
**Impact on this repo:** LOW. [CODE] В hooks/ и scripts/ не найдены импорты asyncio, anyio, trio; hooks/async_wrapper.py использует subprocess.Popen. [VERIFIED] Python из PATH: 3.11.13; pyproject.toml требует >=3.11. Оснований мигрировать wrapper по этим изменениям нет. При будущей диагностике async-задач версия CPython влияет на полноту графа ожидания.
**File to update:** rules/coding-style.md — при появлении asyncio-кода фиксировать версию runtime для диагностики; hooks/async_wrapper.py сейчас изменения не требует.
**Source:** [CPython gather fix, 10 Nov](https://github.com/python/cpython/commit/9d05428b29508873fb26832eea5d17e0e8de60df), [CPython eager-task fix, 11 Nov](https://github.com/python/cpython/commit/0ada998ebbf392238719358432cd723a622fcd5e)

## [Security] — Git MCP: выполнение команд через конфигурацию и неполная изоляция

**What changed:** [VERIFIED] Два advisory опубликованы 11 ноября: GHSA-6hqx-gqrx-c5r2 — недоверенный .git/config позволяет запускать команды через core.fsmonitor и другие настройки даже из read-only tools; GHSA-q74p-4wrc-q7w6 — обход --repository через alternate object stores и путаницу common_dir у worktrees. Исправления выпущены в mcp-server-git 2026.11.11. Во втором advisory отдельно указано: Windows junctions пока остаются ограничением изоляции. В обоих advisories указано No known CVE; номера CVE из связанных исследований не относятся автоматически к этим находкам.
**Impact on this repo:** LOW. [CODE] mcp-server-git не найден в requirements.txt, pyproject.toml и mcp-profiles/. [UNCERTAIN] Глобальные и внешние deployments не инвентаризировались. [INFERRED] Если этот сервер подключается отдельно, необходимы проверка версии и доверия к Git metadata; на Windows одного --repository недостаточно при возможности создания junctions. Уязвимость локальных hooks по аналогии не объявляется.
**File to update:** rules/security.md — требования к Git MCP и границам доверия; изменение профилей требуется только при фактическом подключении сервера.
**Source:** [Git configuration execution advisory](https://github.com/modelcontextprotocol/servers/security/advisories/GHSA-6hqx-gqrx-c5r2), [Git confinement advisory](https://github.com/modelcontextprotocol/servers/security/advisories/GHSA-q74p-4wrc-q7w6)

## [Security] — Filesystem MCP: symlink race после проверки пути

**What changed:** [VERIFIED] GHSA-p9cv-8g75-4xcg опубликован 11 ноября. Между проверкой пути и открытием файла атакующий, способный подменить каталог внутри разрешённого дерева, может перенаправить read_text_file за allowedDirectories. Читаемый файл должен быть доступен пользователю сервера. Исправленная версия @modelcontextprotocol/server-filesystem — 2.3.0. Это advisory; CVE-номер в отчёте не присваивается.
**Impact on this repo:** LOW. [CODE] Этот пакет не найден в проверенных зависимостях и mcp-profiles/. [INFERRED] При подключении файлового MCP нужно учитывать гонки между проверкой и использованием пути, а не только статический traversal. [UNCERTAIN] Локальная эксплуатация и наличие отдельной глобальной установки не проверялись.
**File to update:** rules/security.md — проверка версии filesystem MCP и устойчивости файловой изоляции к подмене каталогов.
**Source:** [Filesystem MCP advisory](https://github.com/modelcontextprotocol/servers/security/advisories/GHSA-p9cv-8g75-4xcg)

## [AI agent tooling] — Надёжность доставки результатов фоновых агентов

**What changed:** [VERIFIED] В Claude Code v2.1.321 от 9 ноября исправлены потеря отчёта фонового subagent при compaction и ошибочная классификация агента как остановленного пользователем после прерывания cloud session. Для headless/Desktop/VS Code добавлена совместная обработка накопившихся отчётов одним model call.
**Impact on this repo:** MED. [CODE] hooks/settings.json регистрирует agent_lifecycle.py, subagent_verify.py, iteration_guard.py и verdict_logger.py на SubagentStop; rules/delegation-contract.md требует acceptance criteria и stop conditions. [INFERRED] Для фоновых задач следует различать завершение выполнения и получение результата оркестратором. [UNCERTAIN] Потеря результатов здесь не воспроизведена; перечисленные upstream fixes не доказывают изменение семантики SubagentStop.
**File to update:** rules/delegation-contract.md — оговорить получение результата после compaction/resume; hooks/agent_lifecycle.py — возможная точка проверки, без текущего изменения кода.
**Source:** [Anthropic v2.1.321](https://github.com/anthropics/claude-code/releases/tag/v2.1.321)

## [AI agent tooling] — Разрешения должны принадлежать конкретному запуску агента

**What changed:** [VERIFIED] Microsoft Agent Framework python-1.26.0 опубликован 13 ноября. Исправлена изоляция run-level tool approval state, когда агент вызывается как tool; добавлен пример task-scoped authority middleware. Также усилена связь approvals с сохранёнными вызовами и состоянием сессии, а при сокращении Redis history группы tool call/result/approval сохраняются целиком.
**Impact on this repo:** MED как применимый паттерн координации, без утверждения о дефекте или необходимости SDK-миграции. [CODE] В проверенных manifests/profiles Agent Framework не найден. Контракт делегирования уже описывает scope и stop conditions. [INFERRED] При расширении оркестрации стоит явно определять срок и область действия разрешения, включая resume, и не переносить approval между запусками.
**File to update:** rules/delegation-contract.md — привязка разрешения к задаче/запуску и правила повторного использования после resume.
**Source:** [Microsoft Agent Framework python-1.26.0](https://github.com/microsoft/agent-framework/releases/tag/python-1.26.0)

## Coverage and limits

- Проверены первичные release notes Anthropic и Microsoft, commits CPython, advisories modelcontextprotocol/servers; выполнены date-targeted web searches по четырём категориям, включая CVE.
- Новые CVE с подтверждённой применимостью к зависимостям этого репозитория за окно не установлены. Это результат ограниченного поиска, не гарантия отсутствия уязвимостей. Свежие security advisories приведены отдельно от CVE.
- В найденных in-window релизах новые hook events не подтверждены. Важные hook changes этой недели — исправления поведения.
- Отдельно найдено обсуждение [PEP 852](https://discuss.python.org/t/pep-852-asynchronous-functions-in-the-c-api/110003), начатое 10 ноября: предложение async/await C API. Оно не означает принятие стандарта, наличие стабильного API или депрекацию текущих Python patterns.
- Последние найденные release pages могут отставать от публикаций; полнота всех изменений до конца окна не гарантирована.
- Текущая ветка [VERIFIED]: y17/pilot-pains, HEAD 4e6328a. Рабочее дерево содержит многочисленные существовавшие изменения. Память о main не использовалась как доказательство текущего checkout.
- GitNexus MCP tools и локальная команда gitnexus недоступны. Сопоставление выполнено чтением файлов и rg. Символы не изменялись; impact/detect_changes не запускались. Перед будущими code edits они обязательны.

## Implemented

- Созданы эта заметка и trend-watch-2026-11-15-issue-draft.md с конкретным HIGH issue.
- Запрошенный путь: C:/Users/serge/.claude/memory/raw/trend-watch-2026-11-15.md.
- Фактический путь: D:/Claude-cod-top-2026/.claude/memory/raw/trend-watch-2026-11-15.md. Глобальный путь вне writable roots; escalation запрещён. Файл в глобальной памяти не создан.
- HIGH issue НЕ создан. github_create_issue вернул: MCP tool call requires approval, but approval policy is never. Это отказ автоматической проверки разрешений; явное поручение пользователя было.
- Поиск дублей в sergeeey/Claude-cod-top-2026 по 2.1.321 и по trend:/hook вернул пустые списки. Подготовленный заголовок: trend: verify hook enforcement and update Claude Code runtime for v2.1.321 fixes.
- Расписание не настроено и не проверено. Запрошено: понедельник 09:00 Asia/Qyzylorda.
- Runtime, зависимости, hooks, rules и settings.json не изменялись; commit/push не выполнялись.

## Verified

- claude --version → 2.1.319; python --version → 3.11.13.
- Проверены регистрации PreToolUse/FileChanged/SubagentStop в hooks/settings.json и ask decisions в hooks/security_verify.py.
- Прочитаны hooks/async_wrapper.py, hooks/model_usage_tracker.py, hooks/smart_model_router.py, rules/security.md, rules/delegation-contract.md, rules/coding-style.md, requirements.txt и pyproject.toml.
- rg не нашёл импортов asyncio/anyio/trio в hooks/ и scripts/, а целевые MCP server packages и Agent Framework не найдены в проверенных manifests/profiles.
- Код не менялся; pytest/lint не запускались. Проверка отчёта ограничена первичными источниками, локальными файлами и финальной проверкой структуры новых Markdown-артефактов.

