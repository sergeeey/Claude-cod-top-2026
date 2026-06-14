# Claude-cod-top-2026 (Public Repo): Сравнительная таблица потенциала

**Дата**: 2026-03-31 | **Repo**: github.com/sergeeey/Claude-cod-top-2026

---

## 1. ЧТО ЭТО

Публичный пакет конфигурации Claude Code — **one-liner installer** для любого проекта:
- 30 hooks, 9 agents + 3 teams, 16 skills, 8 rules
- 3 профиля установки (minimal/standard/full)
- Plugin manifest + marketplace
- 395+ tests, CI pipeline, doctor diagnostics
- MCP profiles (core/science/deploy)
- PII redaction (12 patterns)
- Evidence Policy + Confidence Scoring

---

## 2. ИСПОЛЬЗОВАНИЕ ПОТЕНЦИАЛА CLAUDE CODE

| Возможность Claude Code | Repo использует | Максимум | % | Оценка |
|-------------------------|----------------|----------|---|--------|
| **CLAUDE.md** | ✅ 66 строк, модульный | ≤200 строк | 95% | ✅✅ |
| **Rules (модульные)** | ✅ 8 файлов | Без лимита | 95% | ✅✅ |
| **Hooks (events)** | ✅ 20/26 events | 26 events | 77% | ✅✅ |
| **Hooks (scripts)** | ✅ 30 скриптов | Без лимита | 90% | ✅✅ |
| **Hooks (4 типа)** | ✅ command + async | command/http/prompt/agent | 50% | ⚠️ |
| **Agents** | ✅ 9 active + 4 archived | Без лимита | 95% | ✅✅ |
| **Agent Teams** | ✅ 3 teams | Без лимита | 90% | ✅✅ |
| **Agent memory** | ✅ 4 agents with memory | Per-agent | 85% | ✅ |
| **Agent isolation** | ✅ 2 agents with worktree | Per-agent | 80% | ✅ |
| **Skills (core)** | ✅ 8 core | Без лимита | 90% | ✅✅ |
| **Skills (extensions)** | ✅ 8 extensions | Без лимита | 85% | ✅ |
| **Skills registry** | ✅ registry.yaml | Без лимита | 90% | ✅✅ |
| **Deny rules** | ✅ 27 правил | Без лимита | 95% | ✅✅ |
| **Permission hook** | ✅ permission_policy.py | Auto-allow/deny | 85% | ✅ |
| **MCP profiles** | ✅ 3 profiles (core/science/deploy) | Без лимита | 70% | ✅ |
| **Plugin manifest** | ✅ plugin.json + marketplace.json | Full plugin system | 60% | ⚠️ |
| **Memory templates** | ✅ 7 шаблонов | Без лимита | 85% | ✅ |
| **Status line** | ✅ statusline.py | Custom scripts | 90% | ✅✅ |
| **Spinner tips** | ✅ 21 custom tips | Без лимита | 85% | ✅ |
| **CI/CD** | ✅ GitHub Actions (pytest+ruff+mypy+secrets+metrics verification) | Full pipeline | 90% | ✅✅ |
| **Tests** | ✅ 395+ tests, 16 files | Без лимита | 85% | ✅ |
| **Installer** | ✅ install.sh (3 profiles, --link, --target) | — | 95% | ✅✅ |
| **Doctor diagnostics** | ✅ doctor.py (11 checks) | — | 90% | ✅✅ |
| **Power Modes** | ✅ 5 keyword modes | — | Уникально | ✅✅ |
| **PII redaction** | ✅ 12 patterns + smart exceptions | — | 85% | ✅ |
| **Input guard** | ✅ 7 injection categories | — | 90% | ✅✅ |
| **Circuit breaker** | ✅ CLOSED/OPEN/HALF_OPEN + fallbacks | — | 95% | ✅✅ |
| **Webhook notify** | ✅ Slack/Telegram | — | 80% | ✅ |
| **Documentation** | ✅ 9 docs (architecture, guides, anti-patterns) | — | 85% | ✅ |
| **Examples** | ✅ 3 session examples | — | 70% | ✅ |
| **Eval tests** | ✅ 6 test cases (adversarial) | — | 75% | ✅ |

### НЕ используемые возможности

| Возможность | Статус | Почему | Рекомендация |
|------------|--------|--------|-------------|
| **HTTP hooks** | ❌ | Все hooks = command type | Добавить для webhook интеграций |
| **Prompt hooks** | ❌ | Не реализовано | Для LLM-based проверок |
| **Agent hooks** | ❌ | Не реализовано | Для multi-turn verification |
| **PostToolUseFailure** | ❌ | Не покрыт event | Добавить error recovery |
| **StopFailure** | ❌ | Не покрыт event | API error handling |
| **SessionEnd** | ❌ | Не покрыт event | Cleanup + final save |
| **PostCompact** | ❌ | Не покрыт event | Re-inject context after compact |
| **WorktreeCreate/Remove** | ❌ | Не покрыт event | Track worktree lifecycle |
| **Elicitation events** | ❌ | Не покрыт event | MCP user input handling |
| **Channels** | ❌ | Нет channel plugins | Telegram/Discord push |
| **LSP servers** | ❌ | Нет LSP config | Code intelligence |
| **PreToolUse input modification** | ❌ | v2.0.10+ feature | Secret redaction at tool level |
| **Output styles** | ❌ | Не реализовано | Custom output formatting |
| **Sandbox config** | ❌ | Не в пакете | OS-level isolation |
| **Scheduled tasks** | ❌ | Не в пакете | /schedule для автоматизации |

---

## 3. ЧТО СДЕЛАНО ЛУЧШЕ ЧЕМ У КОНКУРЕНТОВ

### vs Trail of Bits (github.com/trailofbits/claude-code-config)

| Аспект | Claude-cod-top-2026 | Trail of Bits | Кто лучше |
|--------|-------------------|---------------|-----------|
| Hooks | 30 scripts, 20 events | ~5 hooks | **Вы** (6x больше) |
| Agents | 9 + 3 teams | 0 | **Вы** |
| Skills | 16 (8 core + 8 ext) | 0 | **Вы** |
| Evidence Policy | ✅ + Confidence Scoring | ❌ | **Вы** |
| MCP Circuit Breaker | ✅ 3-state machine | ❌ | **Вы** |
| Input Guard | ✅ 7 categories | ❌ | **Вы** |
| PII Redaction | ✅ 12 patterns | ❌ | **Вы** |
| Tests | 395+ | ~20 | **Вы** (20x больше) |
| Installer | ✅ 3 profiles | ✅ basic | **Вы** |
| Sandbox focus | ⚠️ Minimal | ✅ Primary focus | **ToB** |
| Devcontainer | ❌ | ✅ Official | **ToB** |
| Security audit focus | ⚠️ Hook-level | ✅ Full methodology | **ToB** |

### vs Anthropic Official Skills (github.com/anthropics/skills)

| Аспект | Claude-cod-top-2026 | Anthropic Skills | Кто лучше |
|--------|-------------------|-----------------|-----------|
| Hooks | ✅ 30 | ❌ 0 | **Вы** |
| Agents | ✅ 9+3 | ❌ 0 | **Вы** |
| Rules | ✅ 8 | ❌ 0 | **Вы** |
| Evidence Policy | ✅ | ❌ | **Вы** |
| Skill variety | 16 | Skill-creator + few | **Вы** |
| Plugin system | ⚠️ Basic | ✅ Full marketplace | **Anthropic** |
| Official support | ❌ Community | ✅ Official | **Anthropic** |

### Уникальные фичи (нет у конкурентов)

| Фича | Описание | Impact |
|------|----------|--------|
| **Power Modes** | ralph/autopilot/ultrawork/deep/quick keywords | Behavioral override по одному слову |
| **Doctor diagnostics** | 11 checks, score, actionable fixes | Self-repair capability |
| **MCP Circuit Breaker** | 3-state machine (CLOSED/OPEN/HALF_OPEN) | MCP sessions never hang |
| **Input Guard** | 7 injection categories, auto-block encoding attacks | Prompt injection defense |
| **Evidence Guard + Spot Check** | Deterministic hooks enforce evidence markers | Anti-hallucination at hook level |
| **Keyword Router** | Natural language → skill activation | Zero-config skill triggering |
| **Thinking Level** | Auto-suggest ultrathink for complex tasks | Adaptive reasoning depth |
| **Drift Guard** | NOT NOW keywords detection | Scope creep prevention |
| **Pattern Extractor** | Auto-learn from fix: commits | Continuous improvement |
| **Skill Registry** | registry.yaml with tokens/triggers | Structured skill management |
| **CI metric verification** | README badges verified against actual | Честность even in docs |

---

## 4. ЧТО СТОИТ ДОБАВИТЬ (по приоритету)

### 🔴 Высокий Impact

| # | Что | Почему | Как |
|---|-----|--------|-----|
| 1 | **PostToolUseFailure hook** | Ошибки MCP/tools не обрабатываются | Добавить error recovery + retry logic |
| 2 | **SessionEnd hook** | Нет cleanup при выходе | Добавить final memory save + cleanup |
| 3 | **Plugin.json обновить до v3.0** | Manifest = v2.0.0, marketplace = v12.0.0 (рассинхрон) | Синхронизировать версии |
| 4 | **Channels support** | Нет push-уведомлений | Telegram channel plugin |
| 5 | **Devcontainer** | Нет sandboxed environment | Добавить `.devcontainer/` для безопасного запуска |

### ⚠️ Средний Impact

| # | Что | Почему | Как |
|---|-----|--------|-----|
| 6 | **HTTP/Prompt/Agent hooks** | Только command hooks (50%) | Добавить примеры для 3 других типов |
| 7 | **LSP config** | Нет code intelligence | `.lsp.json` для Python (pyright) |
| 8 | **PreToolUse input modification** | v2.0.10+ фича | Update hooks для transparent redaction |
| 9 | **Output styles** | Нет custom output | Добавить explanatory/terse стили |
| 10 | **Coverage: 48% → 70%** | Below target | Добавить тесты для evidence_guard, drift_guard, webhook_notify |

### ⚪ Низкий Impact (nice to have)

| # | Что | Почему |
|---|-----|--------|
| 11 | PostCompact hook | Re-inject critical context |
| 12 | WorktreeCreate/Remove hooks | Track worktree lifecycle |
| 13 | Sandbox config template | OS-level isolation |
| 14 | Windows installer (PowerShell) | install.ps1 уже есть, но basic |
| 15 | Scheduled task examples | /schedule templates |

---

## 5. СВОДНАЯ ОЦЕНКА

### По категориям

| Категория | Score | Vs Maximum |
|-----------|-------|-----------|
| Hooks & Guards | ⭐⭐⭐⭐⭐ | 90% — лучший в open-source |
| Agents & Teams | ⭐⭐⭐⭐⭐ | 95% — полная система |
| Skills | ⭐⭐⭐⭐⭐ | 90% — registry + manager |
| Evidence Policy | ⭐⭐⭐⭐⭐ | 95% — уникально |
| Security (InputGuard, PII) | ⭐⭐⭐⭐ | 85% — нет sandbox/devcontainer |
| MCP Resilience | ⭐⭐⭐⭐⭐ | 95% — circuit breaker уникален |
| Installer & DX | ⭐⭐⭐⭐⭐ | 95% — 3 profiles, doctor, one-liner |
| Testing & CI | ⭐⭐⭐⭐ | 80% — 395 tests, metrics verification |
| Plugin system | ⭐⭐⭐ | 60% — manifest есть, не полный |
| Documentation | ⭐⭐⭐⭐ | 85% — 9 docs, examples |
| Platform coverage | ⭐⭐⭐ | 70% — Linux/Mac focus, Windows basic |

### Общая оценка: **~85% потенциала Claude Code**

Это значительно выше вашего локального конфига (60%), потому что repo:
- Содержит **installer** (reproducible setup)
- Имеет **tests** (395+ verified behaviors)
- Имеет **CI** (metrics auto-verified)
- Имеет **docs** (architecture, guides, anti-patterns)
- Имеет **plugin manifest** (marketplace-ready)

### Vs ваш локальный config (~60%)

| Аспект | Local (~/.claude/) | Repo (Claude-cod-top-2026) | Delta |
|--------|-------------------|---------------------------|-------|
| Hooks | Same scripts | + tests + CI | +15% |
| Agents | Same agents | + archived + docs | +5% |
| Skills | Same skills | + registry.yaml + manager | +10% |
| Installer | Manual | install.sh 3 profiles | +20% |
| Tests | 0 | 395+ | +25% |
| CI | 0 | GitHub Actions 7 steps | +20% |
| Doctor | 0 | 11 diagnostic checks | +10% |
| Plugin | 0 | manifest + marketplace | +10% |
| Docs | 0 | 9 documents | +15% |
| Power Modes | 0 | 5 keyword modes | +5% |

---

## 6. ПОЗИЦИОНИРОВАНИЕ НА РЫНКЕ

### Конкурентный ландшафт (март 2026)

| Repo | Stars | Hooks | Agents | Skills | Tests | Focus |
|------|-------|-------|--------|--------|-------|-------|
| **anthropics/skills** | 87K+ | 0 | 0 | skill-creator | 0 | Official skills |
| **trailofbits/claude-code-config** | ~5K | ~5 | 0 | 0 | ~20 | Security/sandbox |
| **ykdojo/claude-code-tips** | ~10K | 0 | 0 | 0 | 0 | Tips collection |
| **FlorianBruniaux/claude-code-ultimate-guide** | ~3K | 0 | 0 | 0 | 0 | Guide |
| **sergeeey/Claude-cod-top-2026** | ? | **30** | **9+3** | **16** | **395+** | **Full config** |

**Уникальная позиция**: единственный repo с полным стеком (hooks + agents + skills + tests + CI + installer + plugin). Ближайший конкурент (Trail of Bits) фокусируется только на security/sandbox.

### Что нужно для доминирования

1. **Stars & visibility** — README уже отличный, нужен маркетинг
2. **Devcontainer** — закроет gap с Trail of Bits
3. **Coverage 70%+** — credibility для enterprise
4. **Plugin marketplace registration** — стать частью official ecosystem
