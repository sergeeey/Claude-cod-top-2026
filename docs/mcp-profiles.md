# MCP Profiles — Управление серверами

## Проблема

Каждый MCP-сервер добавляет ~1000-2000 токенов tool definitions в контекст
на каждое сообщение. При 16 серверах это ~20 000 токенов мёртвого груза.

## Решение: профили

Подключай только серверы, нужные для текущей задачи.

## 3 профиля

### core.json (по умолчанию)
5 серверов для повседневной работы:
- **context7** — документация библиотек
- **basic-memory** — структурированная память
- **sequential-thinking** — цепочки рассуждений
- **playwright** — браузерная автоматизация
- **ollama** — локальный инференс

### science.json
Core + научные серверы:
- **ncbi-datasets** — геномные данные NCBI
- **uniprot** — белковые базы данных
- **pubmed-mcp** — научные публикации

### deploy.json
Core + деплой серверы:
- **vercel** — деплой фронтенда
- **netlify** — статические сайты
- **supabase** — БД и auth
- **sentry** — мониторинг ошибок

## Переключение

### PowerShell (Windows)
```powershell
~/.claude/mcp-profiles/switch-profile.ps1 science
```

### Bash (Linux/Mac)
```bash
cp ~/.claude/mcp-profiles/core.json ~/.claude/settings.local.json
```

### После переключения
**Обязательно перезапустить Claude Code!** MCP серверы загружаются при старте.

Проверка: `claude mcp list`

## Создание своего профиля

1. Скопируй `core.json` как основу
2. Добавь/убери серверы в секции `permissions.allow`
3. Сохрани как `my-profile.json`
4. Переключись: `switch-profile.ps1 my-profile`

## Важно: .mcp.json vs settings.local.json

- `.mcp.json` — формат Cursor/Windsurf (Claude Code его НЕ читает)
- `settings.local.json` — формат Claude Code
- Серверы добавляются через: `claude mcp add -s user <name> -- <command> <args>`
- Проверка: `claude mcp list`
