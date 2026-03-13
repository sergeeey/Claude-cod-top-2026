---
name: mcp-installer
description: >
  [STATUS: confirmed] [CONFIDENCE: medium] [VALIDATED: 2026-03-12]
  Автопоиск и установка MCP серверов через WebSearch + claude mcp add.
  Triggers: найди MCP, подключи сервер, новый MCP, интеграция с.
---

# Skill: MCP Auto-Installer

## Когда загружать
При старте нового проекта или задачи, где нужны специализированные инструменты (фреймворки, API, базы данных), которых нет среди подключённых MCP серверов.

## Триггеры
- Новый проект с незнакомым стеком
- Задача требует интеграции с внешним сервисом (Stripe, Firebase, Twilio...)
- Работа с фреймворком без подключённого MCP (React Native, Flutter, Django...)
- Пользователь явно просит "найди MCP для X"

## Workflow

### Step 1: Определи потребность
Исходя из задачи определи какие MCP серверы могут помочь:
- Web/mobile app → UI framework MCP, database MCP, auth MCP
- API backend → database MCP, monitoring MCP
- Data science → jupyter MCP, database MCP
- DevOps → docker MCP, cloud provider MCP
- Биоинформатика → NCBI, UniProt, PubMed (уже установлены)

### Step 2: Поиск
```
WebSearch("mcpmarket.com <технология> MCP server")
WebSearch("github MCP server <технология> model context protocol")
```
ВАЖНО: mcpmarket.com блокирует прямой WebFetch (429). Искать через WebSearch, читать README через GitHub.

### Step 3: Оценка кандидата
Перед установкой проверь:
- [ ] GitHub stars > 10 (минимальная валидация)
- [ ] README содержит installation instructions
- [ ] Последний коммит < 6 месяцев (не abandoned)
- [ ] Зависимости: Node.js (npx/npm) или Python (pip/uvx)
- [ ] Нет подозрительных permissions (доступ к файловой системе без причины)

### Step 4: Установка
Два пути в порядке приоритета:

**Путь A — npx (предпочтительный, без клонирования):**
```bash
claude mcp add -s user <name> -- npx -y <package-name>
```
Проверить подключение:
```bash
claude mcp list 2>&1 | grep <name>
```
Если "Failed to connect" → Путь B.

**Путь B — локальная установка:**
```bash
cd /c/Users/serge/mcp-servers
git clone <repo-url>
cd <repo-name>
npm install && npm run build   # для Node.js
# или
pip install -r requirements.txt  # для Python
```
Регистрация:
```bash
# Node.js
claude mcp add -s user <name> -- node C:/Users/serge/mcp-servers/<repo>/build/index.js
# Python
claude mcp add -s user <name> -- python C:/Users/serge/mcp-servers/<repo>/server.py
```

**Путь C — Python (uvx):**
```bash
claude mcp add -s user <name> -- uvx <package-name>
```

### Step 5: Верификация
```bash
claude mcp list 2>&1 | grep <name>
```
Ожидаемый результат: `<name>: ... - ✓ Connected`

Если Failed:
1. Проверь entry point в package.json (`main`, `bin`, `type: module` → dist/)
2. Проверь что runtime (node/python) доступен
3. Попробуй запустить вручную: `node <path>/index.js` — поймай ошибку

### Step 6: Активация
MCP серверы подключаются при инициализации сессии.
Сообщи пользователю:
> "MCP сервер [name] установлен и зарегистрирован. Выполни `/clear` чтобы активировать — после этого инструменты будут доступны."

## Директория установки
Все MCP серверы устанавливаются в: `C:/Users/serge/mcp-servers/<name>/`

## Уже установленные серверы (не дублировать)
Проверяй перед установкой:
```bash
claude mcp list
```

Типичные уже подключённые:
- context7 — документация библиотек
- playwright — браузерная автоматизация
- basic-memory — персистентная память
- sequential-thinking — цепочки рассуждений
- ncbi-datasets — геномика (31 tool)
- uniprot — белки (26 tools)
- pubmed-mcp — литература (5 tools)
- bioRxiv — препринты (plugin)
- ollama — локальный LLM (11 tools)
- sentry, linear, figma, supabase, vercel, netlify — cloud plugins

## Anti-patterns
- НЕ устанавливай MCP если задача решается встроенными инструментами (WebSearch, Bash, Read)
- НЕ устанавливай MCP с 0 stars и без README
- НЕ устанавливай MCP требующий API key который у пользователя нет (спроси сначала)
- НЕ пытайся использовать MCP в той же сессии — нужен /clear
