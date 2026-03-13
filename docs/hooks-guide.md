# Руководство по Hooks

## Что такое Hooks

Hooks — скрипты, запускающиеся автоматически в определённые моменты работы Claude Code.
В отличие от инструкций CLAUDE.md (которые модель может проигнорировать), hooks исполняются 100%.

## 14 доступных событий

| Событие | Когда | Наши hooks |
|---------|-------|------------|
| SessionStart | Старт/resume/clear/compact | `session_start.py` |
| SessionEnd | Завершение сессии | — |
| UserPromptSubmit | Перед отправкой промпта | — |
| **PreToolUse** | Перед вызовом инструмента | `pre_commit_guard.py`, `redact.py` |
| PermissionRequest | Запрос разрешения | — |
| **PostToolUse** | После вызова инструмента | `post_format.py`, `plan_mode_guard.py`, `memory_guard.py`, `checkpoint_guard.py`, `post_commit_memory.py` |
| PostToolUseFailure | После ошибки инструмента | — |
| **PreCompact** | Перед сжатием контекста | `pre_compact.py` |
| Stop | Остановка агента | `session_save.py` |
| SubagentStart | Старт субагента | — |
| SubagentStop | Стоп субагента | — |
| Notification | Уведомление | — |
| Setup | Первый запуск | — |
| InstructionsLoaded | Загрузка инструкций | — |

## Описание каждого hook

### session_start.py (SessionStart)
Загружает activeContext.md текущего проекта и выводит его в контекст.
Позволяет Claude "вспомнить" где остановились.

### pre_compact.py (PreCompact)
Перед сжатием контекста сохраняет текущее состояние в activeContext.md.
Защищает от потери важной информации при автоматическом compaction.

### pre_commit_guard.py (PreToolUse → Bash)
Сканирует Bash-команды на опасные паттерны:
- `git push --force`, `git reset --hard`
- `DROP TABLE`, `TRUNCATE TABLE`
- `rm -rf /`, `chmod 777`
Блокирует выполнение (exit code 2) с предупреждением.

### redact.py (PreToolUse → MCP)
PII redaction перед отправкой во внешние MCP-серверы.
Очищает: ИИН, email, телефоны, API-ключи.
Исключения: ClinVar ID, dbSNP, геномные координаты, git SHA.

### post_format.py (PostToolUse → Edit/Write)
Автоматически форматирует файлы после редактирования.
Python: black/ruff. JS/TS: prettier.

### plan_mode_guard.py (PostToolUse → Edit/Write)
Если Claude в Plan Mode — предупреждает о попытке редактирования файлов.
Plan Mode = только планирование, без изменений кода.

### memory_guard.py (PostToolUse → Bash)
После значимых Bash-операций напоминает обновить память проекта.
Триггеры: git commit, npm/pip install, docker операции.

### checkpoint_guard.py (PostToolUse → Bash)
Детектирует рисковые операции и напоминает создать checkpoint.
Триггеры: rebase, merge, миграции БД, rm -rf.

### post_commit_memory.py (PostToolUse → Bash)
После git commit автоматически предлагает обновить activeContext.md.

### session_save.py (Stop)
При остановке агента сохраняет текущее состояние сессии.

## Конфигурация в settings.json

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "startup|resume|clear|compact",
      "hooks": [{
        "type": "command",
        "command": "python ~/.claude/hooks/session_start.py",
        "timeout": 10
      }]
    }],
    "PreToolUse": [{
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "python ~/.claude/hooks/pre_commit_guard.py",
        "timeout": 15
      }]
    }]
  }
}
```

## Как создать свой hook

1. Напиши Python/Bash скрипт
2. Скрипт получает контекст через stdin (JSON)
3. Exit code 0 = OK, exit code 2 = заблокировать действие
4. stderr → сообщение пользователю
5. Зарегистрируй в settings.json

## Матчеры

- `"Bash"` — только Bash-команды
- `"Edit|Write"` — Edit или Write
- `"mcp__ollama|mcp__ncbi"` — конкретные MCP-серверы
- `"*"` — все инструменты
- `"startup|resume|clear|compact"` — события сессии
