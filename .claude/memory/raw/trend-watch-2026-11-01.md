# Trend Watch — 2026-11-01

#trends #claude-code

Период: 2026-10-25 00:00 — 2026-11-01 00:00, Asia/Qyzylorda (семь завершённых суток).
Расписание из задания: понедельник, 09:00 Asia/Qyzylorda. Это выполненный обзор, а не подтверждение настроенного расписания. Инструмента управления автоматизациями Codex в сессии нет; в доступных локальных automation.toml совпадений Trend Watch/trend-watch не найдено. Расписание не создано и не изменено.
Классификация внесённых изменений: TRIVIAL — только отчёт и черновик issue.
Impact — приоритет проверки для репозитория; он не равен CVSS и не доказывает локальную эксплуатацию. «File to update» обозначает кандидата на последующую проверку/изменение.

## [Claude Code / Anthropic] — Исправлены преждевременные SubagentStop

**What changed:** [VERIFIED] v2.1.311 от 26 октября исправляет SubagentStop, который мог запускаться примерно дважды в минуту для работающего агента вместо одного раза при завершении.
**Impact on this repo:** HIGH. [VERIFIED] Установлен Claude Code 2.1.303. [CODE] В hooks/settings.json зарегистрированы шесть SubagentStop handlers. agent_lifecycle.py удаляет стартовый таймер и пишет STOP/success при каждом вызове; iteration_guard.py увеличивает счётчик при VERDICT: NEEDS_WORK/BLOCK без дедупликации agent_id и при count >= 3 запрещает следующий reviewer/builder Agent. [INFERRED] Повторные события могут исказить метрики, а при наличии подходящего verdict — преждевременно исчерпать лимит циклов. [UNCERTAIN] Сбой событий на 2.1.303 и соответствие установленных глобальных hooks репозиторию не воспроизводились; первая затронутая версия в release notes не названа. Первый шаг — изолированная проверка событий и план обновления runtime до версии с исправлением.
**File to update:** hooks/agent_lifecycle.py; hooks/iteration_guard.py — проверить идемпотентность обработки завершения, перед изменением выполнить GitNexus impact.
**Source:** [Anthropic v2.1.311](https://github.com/anthropics/claude-code/releases/tag/v2.1.311)

## [Python async patterns] — Исправлено зависание закрытия SSL после EOF

**What changed:** [VERIFIED] CPython issue #160520 закрыт исправлением 25 октября; поправка включена в changelog Python 3.15.2 от 25 октября. Ранее ssl_shutdown_timeout мог перестать действовать после EOF от peer, который не читает оставшиеся данные; close()/wait_closed() зависали. Это исправление реализации, не новая депрекация API. Новых депрекаций async API за это окно по проверенным источникам не подтверждено.
**Impact on this repo:** LOW. [CODE] Импортов asyncio/anyio/trio в Python-файлах hooks/, scripts/, tests/ не найдено. hooks/async_wrapper.py запускает subprocess.Popen; pyproject.toml требует Python >=3.11. Миграция wrapper на asyncio по этой новости не обоснована.
**File to update:** rules/coding-style.md — только при добавлении async-сетевого кода: явно проверять отмену, timeout и завершение соединений.
**Source:** [CPython #160520](https://github.com/python/cpython/issues/160520), [Python 3.15 changelog](https://docs.python.org/3.15/whatsnew/changelog.html#python-3-15-2-final)

## [Security] — Обновление CVE-2026-115557: недоверенные TLS-сертификаты

**What changed:** [VERIFIED] Запись CVE впервые опубликована 24 октября (до окна), обновлена 27 октября; Python 3.15.2 от 25 октября содержит защиту ssl от скомпрометированных промежуточных ключей eMudhra. Это обновление существующей CVE и выпуск исправления в окне, не новая публикация CVE. CNA указывает исправленные границы 3.11.18, 3.12.16, 3.13.18, 3.14.10 и 3.15.2.
**Impact on this repo:** MED. [VERIFIED] Команда python --version вернула 3.11.13 — ниже исправленной границы ветки 3.11. [CODE] hooks/webhook_notify.py отправляет запросы через urllib opener и полагается на TLS runtime для HTTPS. [INFERRED] Следует проверить используемый hooks интерпретатор, обновления runtime и доверенных сертификатов. [UNCERTAIN] Наличие опасных сертификатов в trust store, реальные webhook destinations и возможность эксплуатации не проверялись; версия из PATH не доказывает, что глобальные hooks используют именно её.
**File to update:** rules/security.md — требования к обновлению TLS runtime/trust store; hooks/webhook_notify.py — точка проверки HTTPS, необходимость изменения кода не установлена.
**Source:** [CVE Program — CVE-2026-115557](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/115xxx/CVE-2026-115557.json), [Python 3.15.2 security changes](https://docs.python.org/3.15/whatsnew/changelog.html#python-3-15-2-final)

## [Security] — mcp-server-git: выход из разрешённого репозитория через gitdir

**What changed:** [VERIFIED] Advisory GHSA-w766-5x43-whvw опубликован 28 октября. Вложенный файл .git с перенаправлением gitdir позволял обойти --repository и читать/менять доступный процессу внешний репозиторий. Требуются возможность вызывать MCP tools и разместить такой файл внутри разрешённого дерева. Исправление: mcp-server-git 2026.10.28. В advisory указано No known CVE — CVE-номер не присваиваю.
**Impact on this repo:** LOW. [CODE] mcp-server-git не найден в requirements.txt, pyproject.toml и mcp-profiles/. Глобальные и внешние MCP deployments не инвентаризировались. [INFERRED] Полезная проверка при подключении Git MCP: confinement должен учитывать разрешённые Git пути после gitdir indirection, а не только исходный файловый путь.
**File to update:** rules/security.md — проверка изоляции Git MCP и версии при подключении сервера.
**Source:** [MCP servers security advisory](https://github.com/modelcontextprotocol/servers/security/advisories/GHSA-w766-5x43-whvw)

## [AI agent tooling] — Отдельный effort для subagents

**What changed:** [VERIFIED] Claude Code v2.1.316 от 31 октября добавил CLAUDE_CODE_SUBAGENT_EFFORT: значение по умолчанию для subagent, когда effort не задан иначе, вместо наследования effort сессии.
**Impact on this repo:** MED. [CODE] rules/delegation-contract.md описывает цель, scope, context, acceptance и stop conditions, но не фиксирует effort. agent_lifecycle.py показывает объявленную модель из frontmatter, не фактический effort. [INFERRED] Для сравнений качества/стоимости делегирования следует явно учитывать настройки effort. Переменная пока недоступна в установленном 2.1.303; изменения окружения не выполнены.
**File to update:** rules/delegation-contract.md — документировать effort для экспериментов, где он влияет на сравнимость результатов.
**Source:** [Anthropic v2.1.316](https://github.com/anthropics/claude-code/releases/tag/v2.1.316)

## [AI agent tooling] — Явное владение async-клиентами

**What changed:** [VERIFIED] Microsoft Agent Framework Python 1.24.0 от 30 октября добавил optional async chat-client contexts и cleanup с учётом владельца: переданные вызывающим кодом ресурсы не закрываются автоматически. Также добавлены async conditions в switch-case workflow edges.
**Impact on this repo:** LOW. [CODE] agent-framework не найден в проверенных зависимостях и MCP profiles; контракт делегирования уже содержит scope и stop conditions. [INFERRED] При будущей координации агентов с общими сетевыми клиентами стоит явно задавать владельца ресурса и кто его закрывает. Это применимый паттерн, не подтверждённый дефект текущей системы.
**File to update:** rules/delegation-contract.md — при появлении shared clients добавить правила ownership и cleanup.
**Source:** [Microsoft Agent Framework python-1.24.0](https://github.com/microsoft/agent-framework/releases/tag/python-1.24.0)

## Implemented

- Созданы эта raw note с тегами и готовый черновик HIGH issue trend-watch-2026-11-01-issue-draft.md.
- Запрошенный путь: C:/Users/serge/.claude/memory/raw/trend-watch-2026-11-01.md.
- Фактический путь: D:/Claude-cod-top-2026/.claude/memory/raw/trend-watch-2026-11-01.md. Запись в глобальную память недоступна по filesystem policy сессии; escalation запрещён. Обход ограничений не выполнялся.
- HIGH issue НЕ создан: github_create_issue вернул "MCP tool call requires approval, but approval policy is never". Это отказ автоматической проверки разрешений, не отсутствие пользовательского поручения.
- Поиск GitHub issues по repo:sergeeey/Claude-cod-top-2026 is:issue SubagentStop вернул пустой список.
- Расписание НЕ настроено: управляющего инструмента нет, запись в глобальные Codex automations также вне разрешённого workspace.
- Исходный код, settings.json, зависимости, runtime и существующие изменения пользователя не менялись. Commit/push не выполнялись.

## Verified

- Даты и поведение проверены по первичным release notes Anthropic/Microsoft, CPython issue/changelog и CVE Program/advisory MCP.
- claude --version: 2.1.303; python --version: 3.11.13.
- Прочитаны hooks/settings.json, hooks/iteration_guard.py, hooks/agent_lifecycle.py, hooks/async_wrapper.py, hooks/webhook_notify.py, rules/security.md, rules/coding-style.md, rules/delegation-contract.md, requirements.txt, pyproject.toml.
- Поиск импортов asyncio/anyio/trio в hooks/, scripts/, tests/ не дал совпадений; поиск agent-framework/mcp-server-git/n8n в requirements.txt, pyproject.toml, mcp-profiles/ также не дал совпадений.
- GitNexus MCP недоступен. Символы не редактировались; impact/detect_changes не запускались.
- Поведенческие тесты, эксплуатация CVE и live-проверка upstream regression не выполнялись: результат — мониторинг с привязкой к коду.
- Покрытие ограничено перечисленными источниками и файлами. Отсутствие обнаруженного CVE или зависимости не означает отсутствие уязвимостей во всех внешних установках.

