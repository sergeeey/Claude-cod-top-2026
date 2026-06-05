# Claude Code: Продвинутый гайд — Часть 2 (март 2026)

## Оглавление
1. [Система плагинов](#1-система-плагинов)
2. [Channels — push-уведомления](#2-channels--push-уведомления)
3. [Agent SDK — глубокое погружение](#3-agent-sdk--глубокое-погружение)
4. [Паттерны оркестрации агентов](#4-паттерны-оркестрации-агентов)
5. [Монорепо и большие кодбазы](#5-монорепо-и-большие-кодбазы)
6. [Docker и Kubernetes](#6-docker-и-kubernetes)
7. [Миграции базы данных](#7-миграции-базы-данных)
8. [Infrastructure as Code](#8-infrastructure-as-code)
9. [Prompt Caching — механика](#9-prompt-caching--механика)
10. [Безопасность и Sandbox](#10-безопасность-и-sandbox)
11. [Enterprise и Managed Settings](#11-enterprise-и-managed-settings)
12. [Cloud Providers (Bedrock/Vertex/Foundry)](#12-cloud-providers)
13. [Приватность данных и Compliance](#13-приватность-данных-и-compliance)
14. [Автоматизация Code Review](#14-автоматизация-code-review)
15. [Оптимизация стоимости](#15-оптимизация-стоимости)
16. [Мульти-репозиторий (Spine Pattern)](#16-мульти-репозиторий)

---

## 1. Система плагинов

### Что такое плагины?

Плагины — это **полные пакеты расширений**, объединяющие skills, agents, hooks, MCP серверы и LSP серверы в одну распространяемую единицу.

| Возможность | Плагины | Skills | Agents | Hooks | MCP |
|-------------|---------|--------|--------|-------|-----|
| Распространение через маркетплейс | ✓ | — | — | — | — |
| Bundled MCP серверы | ✓ | — | — | — | — |
| Bundled LSP серверы | ✓ | — | — | — | — |
| Bundled hooks | ✓ | — | — | — | — |
| User config prompts (keychain) | ✓ | — | — | — | — |
| Версионирование + auto-update | ✓ | — | — | — | — |
| Channels (push events) | ✓ | — | — | — | — |

### Структура плагина

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json              # Манифест (обязателен только name)
├── agents/                      # Кастомные субагенты
│   └── security-reviewer.md
├── skills/                      # Навыки с SKILL.md
│   └── code-review/
│       ├── SKILL.md
│       └── checklist.md
├── hooks/                       # Хуки
│   ├── hooks.json
│   └── scripts/
│       └── format-code.sh
├── .mcp.json                    # MCP серверы
├── .lsp.json                    # LSP серверы
├── settings.json                # Дефолтные настройки
└── README.md
```

### Манифест plugin.json

```json
{
  "name": "deployment-tools",
  "version": "1.2.0",
  "description": "Deploy automation tools",
  "author": { "name": "DevOps Team" },

  "commands": ["./custom-commands/"],
  "agents": ["./custom-agents/"],
  "skills": ["./custom-skills/"],
  "hooks": "./config/hooks.json",
  "mcpServers": "./mcp-config.json",
  "lspServers": "./.lsp.json",
  "outputStyles": "./styles/",

  "userConfig": {
    "api_endpoint": { "description": "API endpoint", "sensitive": false },
    "api_token": { "description": "API token", "sensitive": true }
  },

  "channels": [{
    "server": "telegram",
    "userConfig": {
      "bot_token": { "description": "Bot token", "sensitive": true }
    }
  }]
}
```

### Специальные переменные
- `${CLAUDE_PLUGIN_ROOT}` — путь к установке плагина (НЕ переживает обновления)
- `${CLAUDE_PLUGIN_DATA}` — `~/.claude/plugins/data/{plugin-id}/` (переживает обновления)

### Маркетплейсы

**Официальный маркетплейс** (claude-plugins-official) включает:
- LSP плагины: TypeScript, Python (Pyright), Rust, Go, Java, C/C++, C#, PHP, Swift, Kotlin
- Интеграции: GitHub, GitLab, Atlassian, Asana, Linear, Notion, Figma, Vercel, Firebase, Supabase, Slack, Sentry
- Dev workflow: commit-commands, pr-review-toolkit, agent-sdk-dev, plugin-dev

**Создание своего маркетплейса:**

Файл `.claude-plugin/marketplace.json` в git-репозитории:
```json
{
  "name": "company-tools",
  "owner": { "name": "DevTools Team" },
  "plugins": [
    { "name": "formatter", "source": "./plugins/formatter" },
    { "name": "security", "source": { "source": "github", "repo": "company/security-plugin" } }
  ]
}
```

**Источники плагинов:**
- Relative path (в том же repo)
- GitHub (`"source": "github", "repo": "owner/repo"`)
- Git URL (`"source": "url", "url": "https://gitlab.com/..."`)
- Git subdirectory (монорепо)
- npm package (`"source": "npm", "package": "@company/plugin"`)

### Управление плагинами

```bash
/plugin marketplace add owner/repo       # Добавить маркетплейс
/plugin install formatter@my-marketplace  # Установить
/plugin disable formatter@my-marketplace  # Отключить
/plugin update formatter@my-marketplace   # Обновить
/plugin validate .                        # Валидировать
/reload-plugins                           # Перезагрузить без рестарта
```

**Scopes установки:**
- `user` (по умолчанию) — `~/.claude/settings.json`
- `project` — `.claude/settings.json` (в git)
- `local` — `.claude/settings.local.json` (gitignored)

### Тестирование локально
```bash
claude --plugin-dir ./my-plugin
```

### Ограничения plugin agents
Plugin agents НЕ могут иметь: hooks, mcpServers, permissionMode (по соображениям безопасности).

---

## 2. Channels — push-уведомления

### Что это?

Channels — MCP серверы с возможностью `claude/channel`, которые **пушат события** в running сессию Claude Code: вебхуки, чат-сообщения, алерты.

### Встроенные channel-плагины
- **Telegram** — DM боту, он отвечает pairing кодом
- **Discord** — аналогичный flow
- **iMessage** — macOS only, читает Messages DB
- **Fakechat** — демо на localhost

### Включение

```bash
claude --channels plugin:telegram@claude-plugins-official
```

### Создание кастомного channel

Минимальный webhook receiver (Bun):

```typescript
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'

const mcp = new Server(
  { name: 'webhook', version: '0.0.1' },
  {
    capabilities: { experimental: { 'claude/channel': {} } },
    instructions: 'Events arrive as <channel source="webhook">. One-way: read and act.',
  },
)

await mcp.connect(new StdioServerTransport())

Bun.serve({
  port: 8788,
  async fetch(req) {
    const body = await req.text()
    await mcp.notification({
      method: 'notifications/claude/channel',
      params: { content: body, meta: { path: new URL(req.url).pathname } },
    })
    return new Response('ok')
  },
})
```

### Типы channels
- **One-way** — только forward событий (CI результаты, мониторинг)
- **Two-way** — forward + reply tool (чат-мосты)

---

## 3. Agent SDK — глубокое погружение

### Два SDK

| | Python | TypeScript |
|---|---|---|
| Package | `claude-agent-sdk` v0.1.48 | `@anthropic-ai/claude-agent-sdk` v0.2.71 |
| Entry points | `query()`, `ClaudeSDKClient` | `query()`, `unstable_v2_createSession()` |
| Custom tools | `@tool` decorator | JS functions |
| Extra hooks | — | SessionStart, SessionEnd, Setup, TeammateIdle, TaskCompleted |

### Два способа запуска

**1. `query()` — простой (без кастомных tools/hooks)**:
```python
from claude_agent_sdk import query

async for message in query(
    prompt="Find bug in auth.py",
    options=ClaudeAgentOptions(
        allowed_tools=["Read", "Edit", "Bash"],
        permission_mode="acceptEdits",
        max_budget_usd=0.50,
    ),
):
    print(message)
```

**2. `ClaudeSDKClient` — полный (tools, hooks, sessions)**:
```python
client = ClaudeSDKClient(options, transport)
await client.connect()
async for msg in client.query("task", session_id="resume-id"):
    process(msg)
```

### Кастомные инструменты

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("get_temperature", "Get temperature", {"lat": float, "lon": float})
async def get_temperature(args):
    return {"content": [{"type": "text", "text": f"Temperature: 72F"}]}

server = create_sdk_mcp_server("weather", "1.0.0", tools=[get_temperature])
```

### Хуки (программные)

```python
options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": lambda event: {
            "decision": "block" if "rm -rf" in event.tool_input else "allow",
            "reason": "Dangerous command blocked"
        }
    }
)
```

Хуки работают **вне контекстного окна** — ноль токенов.

### Управление сессиями
- **Создание** — автоматически при первом `query()`
- **Возобновление** — `query("continue", session_id="abc123")`
- **Fork** — создаёт новую сессию с копией истории, оригинал не меняется

### Стриминг
```python
options = ClaudeAgentOptions(include_partial_messages=True)
async for event in query("task", options):
    if event.type == "content_block_delta":
        print(event.delta.text, end="")
```

### Контроль стоимости
- `max_budget_usd` — жёсткий лимит на run
- `max_turns` — лимит tool-use turns
- `total_cost_usd` — в каждом `ResultMessage`
- Subtypes: `success`, `error_max_turns`, `error_max_budget_usd`, `error`

### Аутентификация
1. `ANTHROPIC_API_KEY` — прямой ключ
2. `ANTHROPIC_AUTH_TOKEN` — Bearer token для gateway
3. `apiKeyHelper` — скрипт возвращающий ключ (обновление каждые 5 мин)
4. OAuth — для Pro/Max/Team/Enterprise через `/login`

### SDK vs CLI
| | CLI | Agent SDK |
|---|---|---|
| Для | Разработчик пишет код | Строит AI-продукт |
| System prompt | Полный модульный | Минимальный |
| Аудитория | YOU coding | Others using your agent |

### Demos
- `anthropics/claude-agent-sdk-demos` — 8+ примеров
- `VoltAgent/awesome-claude-code-subagents` — 100+ субагентов

---

## 4. Паттерны оркестрации агентов

### 3 модели оркестрации

**1. Conductor (single agent)**
- Один агент, синхронный, контекст = потолок
- Для фокусной интерактивной работы

**2. Orchestrator (subagents)**
- Hub-and-spoke: координатор + специалисты
- Независимые задачи параллельно, зависимые ждут
- Агенты НЕ общаются между собой

**3. Agent Teams (shared task list)**
- Team Lead раздаёт задачи, teammates self-claim
- Peer-to-peer messaging между агентами
- File locking предотвращает конфликты
- Оптимальный размер: 3-5 teammates
- `Ctrl+T` — toggle task overlay

### The Ralph Loop Pattern

Атомарные stateless циклы:
```
Pick task → Implement → Validate (tests/lint) → Commit → Reset context → Repeat
```

Persistent memory живёт в git history + progress logs + task state files.

### Hierarchical (teams of teams)

Вместо 6 субагентов от одного координатора:
- 2 feature leads, каждый спавнит 2-3 specialists
- Имитирует реальные инженерные иерархии

### Quality gates
- Plan approval перед имплементацией
- `TaskCompleted` hooks запускают lint/tests
- Dedicated `@reviewer` (Opus, read-only, 1 на 3-4 builders)
- **Kill criteria**: reassign после 3+ stuck iterations

### Competing Hypotheses

```
Spawn 5 teammates to investigate different hypotheses.
Have them debate and disprove each other's theories.
```

Противодействует anchoring bias последовательного исследования.

---

## 5. Монорепо и большие кодбазы

### CLAUDE.md layering

```
root/CLAUDE.md              # Только для 30%+ инженеров
root/frontend/CLAUDE.md     # Автоматически при работе в frontend/
root/backend/CLAUDE.md      # Автоматически при работе в backend/
```

### Tiered Context Architecture

| Tier | Что | Токены |
|------|-----|--------|
| 1 (Critical) | Цель проекта, критические правила, quick-start | <800 |
| 2 (On-Demand) | Компонентные доки | 500-1,500 при необходимости |
| 3 (Reference) | Полные спеки, changelogs | 0 (ссылки, не загружаются) |

### Результат оптимизации
2,800-строчный CLAUDE.md → 180 строк = экономия 1,300 токенов/сессию.
Месячные расходы: $189 → $72 для команды из 5.

---

## 6. Docker и Kubernetes

### Официальный devcontainer
- Встроенный firewall: только GitHub, Anthropic API, npm, statsig, sentry
- Всё остальное заблокировано
- **Именно это делает безопасным `--dangerously-skip-permissions`** для unattended работы

### Community tools
- `claude-container` — полная изоляция от хоста
- `claudebox` — пре-конфигурированные dev profiles
- Trail of Bits `claude-code-devcontainer` — для security аудитов

### Docker Sandboxes (official)
- Dedicated microVM для каждого агента
- Disposable — хост не затрагивается
- Поддержка Docker и Podman

### КРИТИЧНО
Docker socket access внутри sandbox = host escape. Если `allowUnixSockets` разрешает `/var/run/docker.sock`, sandbox фактически обходится.

---

## 7. Миграции базы данных

### Safe vs Unsafe
- **Safe**: nullable columns, DEFAULT columns, `CREATE INDEX CONCURRENTLY`
- **Unsafe**: DROP column, RENAME column, type change без плана

### Правило: Deploy code BEFORE removing columns
1. Add column as nullable (instant, no lock)
2. Backfill in batches of 10k
3. Create indexes CONCURRENTLY
4. Add NOT NULL after backfill

### Safety review вопросы для Claude
1. Будет ли lock таблицы и как долго?
2. Нужен ли DEFAULT для существующих строк?
3. Стратегия отката?
4. Надо ли разбить на несколько миграций?

### CI/CD gate
Автоматическое обнаружение:
- `DROP` без `IF EXISTS`
- `NOT NULL` без `DEFAULT`
- `TRUNCATE` в файлах миграций

---

## 8. Infrastructure as Code

### Terraform MCP Server
Exposes Terraform Registry и Cloud APIs прямо в Claude Code. Claude может:
- Запросить документацию провайдера
- Проверить схемы ресурсов
- Генерировать валидный HCL без галлюцинаций атрибутов

### Практический пример
5-шаговый agentic pipeline: 4 AWS ресурса + живой CloudFront сайт.

### AI-powered IaC optimization
15-25% экономия на облаке через улучшенную утилизацию ресурсов.

---

## 9. Prompt Caching — механика

### Иерархия кэша
Tools → System prompt → Messages

**Добавление одного MCP tool меняет prefix и инвалидирует весь cache.**

### Реальные метрики (один таск)
- 92 LLM вызова, ~2M total input tokens
- 92% overall prefix reuse
- Стоимость: $6.00 → $1.15 (**81% экономия**)

### По фазам
| Фаза | Prefix reuse |
|------|-------------|
| Explore | 92.06% |
| Plan | 93.23% |
| Execution | 97.83% |

### System prompt
20,000+ токенов ДО истории разговора: git state, 18 tool specs, execution instructions.

### Cache TTL
- Дефолт: 5 минут
- Extended: 1 час (GA)
- Cache writes: +25% к base input price
- Cache reads: 10% от base input price

### Практическая рекомендация
НЕ добавляйте/удаляйте MCP серверы mid-session — это инвалидирует prefix cache.

---

## 10. Безопасность и Sandbox

### Sandbox по платформам

| Платформа | Технология | Статус |
|-----------|-----------|--------|
| macOS | Seatbelt (встроен) | ✓ Работает из коробки |
| Linux | bubblewrap + socat | ✓ Нужна установка |
| Windows | — | Не поддерживается (workaround: WSL2) |

### Sandbox снижает permission prompts на 84%

### Sandbox runtime — open source!
```bash
npx @anthropic-ai/sandbox-runtime <command>
```
Можно использовать для sandboxing **любого** инструмента, не только Claude Code.

### Filesystem isolation
- Default: read/write только CWD и поддиректории
- Настраивается: `sandbox.filesystem.allowWrite`, `denyWrite`, `denyRead`, `allowRead`

### Network isolation
- Весь трафик через Unix domain socket proxy
- Только approved domains
- Proxy НЕ инспектирует содержимое — фильтрует только по домену
- **Known limitation**: domain fronting обходит фильтрацию

### `sandbox.failIfUnavailable: true`
Для managed deployments: жёсткий отказ если sandbox не может запуститься.

---

## 11. Enterprise и Managed Settings

### Managed-only настройки (нельзя переопределить)
- `allowManagedPermissionRulesOnly` — только managed permission rules
- `allowManagedHooksOnly` — только managed hooks
- `allowManagedMcpServersOnly` — только managed MCP servers
- `sandbox.network.allowManagedDomainsOnly` — только managed domains
- `disableBypassPermissionsMode` — запрет `--dangerously-skip-permissions`
- `disableAutoMode` — запрет auto mode
- `strictKnownMarketplaces` — контроль маркетплейсов

### Приоритет настроек
**Managed > CLI args > Local project > Shared project > User**

Если denied на любом уровне — ни один другой уровень не может allow.

### SSO/SAML
- SAML 2.0 + OIDC
- Okta, Azure AD, любой SAML 2.0 IdP
- Domain capture через DNS TXT
- SCIM provisioning
- JIT provisioning

---

## 12. Cloud Providers

### Amazon Bedrock
```bash
CLAUDE_CODE_USE_BEDROCK=1 AWS_REGION=us-east-1 claude
```
- IAM policies, CloudTrail audit, AWS Guardrails
- Cross-region inference profiles
- Prompt caching support

### Google Vertex AI
```bash
CLAUDE_CODE_USE_VERTEX=1 CLOUD_ML_REGION=us-central1 ANTHROPIC_VERTEX_PROJECT_ID=my-project claude
```
- `roles/aiplatform.user` IAM role
- Cloud Audit Logs

### Microsoft Foundry (Azure)
```bash
CLAUDE_CODE_USE_FOUNDRY=1 claude
```
- Azure RBAC, Azure Monitor, Cost Management

### Все три: telemetry/error reporting OFF по умолчанию

---

## 13. Приватность данных и Compliance

### Что отправляется в API
- Всё, что Claude читает (файлы, команды, результаты)
- Промпты и ответы
- CLAUDE.md правила

### Data Retention
| Plan | Training | Retention |
|------|----------|-----------|
| Free (training on) | Да | 5 лет |
| Pro/Max (training off) | Нет | 30 дней |
| Team/Enterprise/API | Нет | 30 дней (ZDR доступен) |

### Zero Data Retention (ZDR)
Доступен для Enterprise — по запросу.

### Opt-out telemetry
```bash
DISABLE_TELEMETRY=1
DISABLE_ERROR_REPORTING=1
```

### OpenTelemetry мониторинг
- Native OTel support
- Token usage, API costs, cache efficiency, session duration
- Код и файлы НЕ включаются
- Grafana, CloudWatch, Datadog, Honeycomb

### Сертификации
- SOC 2 Type II
- ISO 27001
- Trust Center: trust.anthropic.com

### GDPR
- Data residency: AWS EU regions / Vertex Private Service Connect
- Right to deletion: документированные workflow
- Data minimization: deny rules на PII файлы
- DPA: доступно через Enterprise plan

---

## 14. Автоматизация Code Review

### GitHub Action
```yaml
uses: anthropics/claude-code-action@v1
```
Claude получает live shell: читает файлы, запускает git, правит код, устанавливает deps, пушит коммиты.

### Desktop: Background CI Failure Triage
Агент читает логи, предлагает патчи, открывает/обновляет PR автоматически.

### Parallel Review (Agent Teams)
```
Create an agent team to review PR #142:
- One focused on security implications
- One checking performance impact
- One validating test coverage
```

### Стоимость
$15-$25 за PR review в зависимости от сложности.

---

## 15. Оптимизация стоимости

### Model routing
| Модель | Output cost | Для чего |
|--------|------------|----------|
| Opus | 19x Haiku | Сложное reasoning |
| Sonnet | ~5x Haiku | Большинство задач |
| Haiku | 1x | Простые задачи |

### Одна задача = один промпт
"Add login, write tests, update README" как один промпт → Claude держит всё в контексте одновременно. По отдельности = дешевле.

### MCP server management
Каждый MCP добавляет tool definitions в system prompt. `/context` показывает потребление.

### CLAUDE.md token diet
2,800 строк → 180 строк = $0.063 → $0.024 за сессию (62% reduction).
Годовая экономия: $1,404 для 5 devs, $5,616 для 20 devs.

### Agent Teams
Каждый teammate = отдельное контекстное окно. Токены пропорциональны размеру команды.

---

## 16. Мульти-репозиторий (Spine Pattern)

### Структура
```
spine/
  CLAUDE.md              # master navigation + global context
  _docs/                 # cross-cutting documentation
  _tasks/active/         # active work with prefix routing
  project-a/CLAUDE.md    # project-specific context
  project-b/CLAUDE.md
```

### Task prefix routing
- `be-1-user-migration.md` (backend)
- `fe-2-dashboard.md` (frontend)
- `x-3-auth-flow.md` (cross-cutting)

### Принцип
Cross-repo READ — нужен. WRITE — всегда в одном repo, один PR.

### Боль
Команды с микросервисами тратят 40-60% token budget на cross-repo context duplication.

---

## Бонус: PreToolUse — модификация input (v2.0.10+)

PreToolUse hooks могут **МОДИФИЦИРОВАТЬ** tool inputs перед выполнением:
- Transparent sandboxing
- Automatic dry-run flags
- Secret redaction
- Commit message formatting

Это уникально для Claude Code — Cursor и Copilot поддерживают только command hooks.

---

## Бонус: Permission Escalation Prevention

### Evaluation order: deny → ask → allow (deny ВСЕГДА побеждает)

### Shell operator awareness
`Bash(safe-cmd *)` **НЕ** матчит `safe-cmd && malicious-cmd`

### Consecutive denial escalation
3 consecutive denials или 20 total → system stops и escalates к человеку

### Known issue [WEAK]
Deny rule regressions (Feb 2026) — рекомендуется комбинировать deny rules с PreToolUse Hooks для надёжного блокирования.

---

## Источники

### Официальная документация
- code.claude.com/docs/en/plugins
- code.claude.com/docs/en/sandboxing
- code.claude.com/docs/en/security
- code.claude.com/docs/en/data-usage
- code.claude.com/docs/en/permissions
- code.claude.com/docs/en/agent-teams
- code.claude.com/docs/en/devcontainer
- code.claude.com/docs/en/monitoring-usage
- platform.claude.com/docs/en/agent-sdk/*

### GitHub
- anthropics/claude-agent-sdk-python
- anthropics/claude-agent-sdk-typescript
- anthropics/claude-agent-sdk-demos
- anthropics/skills (87K+ stars)
- trailofbits/claude-code-config
- trailofbits/claude-code-devcontainer
- VoltAgent/awesome-claude-code-subagents (100+ subagents)

### Третьи стороны
- addyosmani.com/blog/code-agent-orchestra
- incident.io/blog/shipping-faster-with-claude-code-and-git-worktrees
- blog.lmcache.ai (prompt caching internals)
- tsoporan.com/blog/spine-pattern-multi-repo-ai-development
- docker.com/blog/docker-sandboxes-run-claude-code
