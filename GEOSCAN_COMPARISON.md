# Geosran-Gold-2026: Сравнительная таблица использования потенциала Claude Code

**Дата**: 2026-03-31 | **Repo**: github.com/sergeeey/Geosran-Gold-2026

---

## 1. ОБЗОР ПРОЕКТА

| Метрика | Значение |
|---------|----------|
| Назначение | Спутниковый поиск золоторудных аномалий (Sentinel-2, IsolationForest) |
| Стек | Python 3.11+, scikit-learn, rasterio, geopandas, Pydantic, Typer |
| Код ядра | 3,760 строк (40 файлов в src/) |
| Тесты | 2,901 строк (28 файлов), 172 passed |
| Скрипты | 63 файла в scripts/ |
| Документация | 28 markdown файлов |
| CI | GitHub Actions (ruff + pytest) |
| Docker | Dockerfile + docker-compose.yml |
| Commits | 10 PRs merged, CI green |
| Результат | AUC 0.9489 (GBM, 20 features), 1,264 зоны на 7 тайлах |

---

## 2. CLAUDE CODE КОНФИГУРАЦИЯ В ПРОЕКТЕ

### 2.1 CLAUDE.md

| Аспект | Geoscan | Ваш global (~/.claude/) | Best Practice | Оценка |
|--------|---------|------------------------|---------------|--------|
| Размер | 95 строк | 66 строк | ≤200 строк | ✅ Оба отлично |
| Структура | Commands → Architecture → Anti-hallucination → Code Style → ADR → Status | Identity → Workflow → Integrity → Agents → Rules | Sections by priority | ✅ Geoscan |
| Anti-hallucination | ✅ 7 конкретных правил с примерами | ✅ Integrity.md (полный протокол) | Domain-specific rules | ✅✅ Geoscan лучше |
| Architecture map | ✅ Полная (pipeline flow + file tree) | Нет (rules-based) | В проектном CLAUDE.md | ✅✅ Geoscan лучше |
| ADR (решения) | ✅ 6 решений inline | ✅ decisions.md отдельно | Любой формат | ✅ Оба |
| Commands section | ✅ install/test/lint/run/map | Нет (глобальный) | В каждом проекте | ✅ Geoscan |
| Current Status | ✅ С датой и метриками | Нет | Для проекта — да | ✅ Geoscan |
| Code Style | ✅ Краткий (5 строк) | ✅ Детальный (rules/) | Модульный в rules/ | ⚠️ Ваш лучше |
| NO SYNTHETIC rule | ✅ Уникальный (domain-specific) | Нет | Для ML проектов — must | ✅✅ Geoscan |
| Data paths | ✅ С .env указанием | Нет | В проекте — да | ✅ Geoscan |

**Вердикт CLAUDE.md**: Geoscan — **эталонный проектный CLAUDE.md**. Содержит domain-specific anti-hallucination rules, architecture map, pipeline flow, ADR, и current status. Один из лучших примеров, что можно встретить.

### 2.2 .claude/ directory

| Компонент | Geoscan | Ваш global | Максимум | Оценка |
|-----------|---------|-----------|----------|--------|
| `.claude/memory/` | ✅ 3 файла | ✅ 5 файлов + templates | Full system | ✅ Оба |
| `activeContext.md` | ✅ 172 строки (подробный) | ❌ В проектах нет | Текущий фокус + метрики | ✅✅ Geoscan |
| `decisions.md` | ✅ 11 ADR | ❌ В проектах нет | Все архитектурные решения | ✅✅ Geoscan |
| `projectOverview.md` | ✅ 203 строки (полный обзор) | ❌ В проектах нет | Overview для новых сессий | ✅✅ Geoscan |
| `.claude/settings.json` | ❌ Нет | ✅ 380 строк | Permissions + hooks | 🔴 Geoscan |
| `.claude/agents/` | ❌ Нет | ✅ 9 agents + 3 teams | Custom agents | 🔴 Geoscan |
| `.claude/skills/` | ❌ Нет | ✅ 8 core + 5 ext | Custom skills | 🔴 Geoscan |
| `.claude/rules/` | ❌ Нет | ✅ 8 rule files | Modular rules | 🔴 Geoscan |
| `.claude/hooks/` | ❌ Нет | ✅ 30 scripts | Automation | 🔴 Geoscan |
| `.claude/.mcp.json` | ❌ Нет | ❌ Нет | MCP servers | 🔴 Оба |

### 2.3 Cursor Memory Bank (бонус)

| Аспект | Geoscan | Оценка |
|--------|---------|--------|
| `.cursor/memory_bank/` | ✅ 7 файлов | Dual-IDE support |
| activeContext.md | ✅ | |
| decisions.md | ✅ | |
| dataContext.md | ✅ Уникальный (data-specific) | |
| systemPatterns.md | ✅ | |
| progress.md | ✅ | |
| projectbrief.md | ✅ | |
| audit_2026-02-23.md | ✅ | |

**Примечание**: Geoscan поддерживает и Claude Code, и Cursor — dual-IDE memory. Это продвинутый паттерн.

---

## 3. СРАВНИТЕЛЬНАЯ ТАБЛИЦА: Geoscan vs Ваш global config vs Максимум

| Категория | Geoscan | Ваш global | Макс | Geoscan % | Ваш % |
|-----------|---------|-----------|------|-----------|-------|
| **CLAUDE.md качество** | ✅✅ Эталон | ✅ Хороший | — | **95%** | 80% |
| **Project memory** | ✅✅ 3 файла, 500+ строк | ❌ 0 в проектах | Full system | **90%** | 0% |
| **ADR (решения)** | ✅✅ 11 ADR | ❌ В проектах нет | Без лимита | **95%** | 0% |
| **Anti-hallucination** | ✅✅ 7 domain rules | ✅ Generic protocol | Domain-specific | **98%** | 70% |
| **Permissions** | 🔴 Нет | ✅✅ 27 deny rules | Granular | 0% | **90%** |
| **Hooks** | 🔴 Нет | ✅✅ 30 scripts, 20/26 events | 26 events | 0% | **77%** |
| **Agents** | 🔴 Нет | ✅✅ 9 + 3 teams | Custom agents | 0% | **95%** |
| **Skills** | 🔴 Нет | ✅✅ 19 skills | Custom skills | 0% | **90%** |
| **MCP servers** | 🔴 Нет | ⚠️ 8 cloud-only | 400+ | 0% | 2% |
| **Plugins** | 🔴 Нет | ⚠️ 2 disabled | 50+ | 0% | 0% |
| **CI/CD** | ✅ GitHub Actions | ❌ Нет | Full pipeline | **70%** | 0% |
| **Docker** | ✅ Dockerfile + compose | ❌ Нет | Full container | **60%** | 0% |
| **Makefile** | ✅ 15 targets | ❌ Нет | Build automation | **80%** | 0% |
| **Tests** | ✅✅ 172 passed, unit+integration | ❌ Project-specific | 80%+ coverage | **85%** | N/A |
| **Docs** | ✅✅ 28 files | ❌ Project-specific | Living docs | **90%** | N/A |
| **PR template** | ✅ .github/pull_request_template.md | ❌ Нет | PR Gate | **70%** | 0% |
| **Dual-IDE (Cursor)** | ✅ memory_bank | ❌ | Both IDEs | **80%** | 0% |
| **Scheduling** | ❌ Нет | ❌ Нет | /schedule | 0% | 0% |
| **Worktrees** | ❌ Нет | ❌ Нет | claude -w | 0% | 0% |
| **Status line** | ❌ Нет | ✅ statusline.py | Custom scripts | 0% | **80%** |
| **Spinner tips** | ❌ Нет | ✅ 21 custom | Custom tips | 0% | **90%** |

---

## 4. ЧТО В GEOSCAN ЛУЧШЕ

### 4.1 Эталонный CLAUDE.md (то, что стоит скопировать)

**Anti-hallucination rules** — 7 конкретных правил с доменной спецификой:
```
1. 414 zones != 414 deposits. Expected TPR: 5-20%
2. contamination != selection method
3. 1 MRDS proximity != validation
4. Clay Index false positives when NDVI > 0.3
...
7. Never output accuracy metrics unless formally validated
```

Это **не общие** "don't hallucinate" — это **конкретные** ошибки, которые Claude может совершить в этом домене. Каждое правило предотвращает реальную ошибку.

**Architecture map с pipeline flow** — Claude видит весь data flow от input до output. Не нужно изучать код чтобы понять что куда идёт.

**NO SYNTHETIC DATA rule** — для ML-проектов это критично. SyntheticDetector блокирует fake data в production code. Тесты — единственное исключение.

### 4.2 Project Memory — 500+ строк живого контекста

`activeContext.md` — самый подробный из виденных:
- 16 записей сессий с конкретными действиями
- Таблица метрик (AUC, тесты, зоны, coverage)
- Composite status по тайлам
- Pipeline results
- What's Next с приоритетами
- Known Issues
- Auto-commit log
- Context Recovery section

`projectOverview.md` — 203 строки. Объясняет проект с нуля, включая:
- Аналогию из другого домена ("как антифрод, только для геологии")
- Сильные и слабые стороны (честно!)
- Научную методологию
- Стек технологий
- Roadmap по фазам

### 4.3 ADR (Architecture Decision Records) — 11 записей

Каждый ADR содержит: Date, Status, Decision, Rationale, Impact/Risk. Примеры:
- ADR-008: Buffer 5km вместо contains() → AUC 0→0.46
- ADR-010: merge_tiles.py must use ranked zones → урок после делегирования Codex
- ADR-011: Temporal stability per-tile, NOT cross-tile → исправление ошибки Codex

**ADR-010 и ADR-011 — уникальны**: записывают ошибки AI-агентов (Codex), чтобы не повторять их. Это meta-learning pattern.

### 4.4 Dual-IDE support

Проект поддерживает и Claude Code (`.claude/memory/`) и Cursor (`.cursor/memory_bank/`). Это rare pattern — большинство проектов выбирают одну IDE.

### 4.5 Честность в документации

`LIMITATIONS.md`, `VALIDATION_NOTE_v3.2.md`, обязательные disclaimers в каждом output — это domain-driven design для geological exploration. Pydantic валидация отвергает отчёт без disclaimers.

---

## 5. ЧТО В ВАШЕМ GLOBAL CONFIG ЛУЧШЕ

### 5.1 Hooks — 30 scripts, 20/26 events

Geoscan: **0 hooks**. Ваш config: **30 hook scripts** covering 77% events.

| Hook | Ваш config | Geoscan | Что даёт |
|------|-----------|---------|----------|
| pre_commit_guard | ✅ | ❌ | Блокирует rm -rf, push --force |
| security_verify | ✅ | ❌ | Предупреждает о .env/auth edits |
| mcp_circuit_breaker | ✅ | ❌ | 3 ошибки → fallback |
| PII redaction | ✅ | ❌ | Маскировка перед MCP |
| evidence_guard | ✅ | ❌ | Проверка маркеров evidence |
| drift_guard | ✅ | ❌ | Обнаружение drift от плана |
| pattern_extractor | ✅ | ❌ | Auto-learning паттернов |
| async_wrapper | ✅ | ❌ | Non-blocking hooks |
| team_rebalance | ✅ | ❌ | Agent Teams idle handling |
| webhook_notify | ✅ | ❌ | Slack/Telegram alerts |

### 5.2 Agents — 9 agents + 3 teams

Geoscan: **0 agents**. Ваш config:

| Преимущество | Описание |
|-------------|----------|
| navigator | Task planning с 80/20 |
| builder + tester | Parallel build+test в worktrees |
| reviewer + sec-auditor | review-squad (параллельный review) |
| explorer + verifier | research-squad (explore → verify) |
| architect | Architecture design |
| teacher | Educational explanations |

### 5.3 Skills — 19 навыков

Geoscan: **0 skills**. Ваш config:

| Skill | Impact |
|-------|--------|
| routing-policy | Автоматический выбор agent/tool |
| tdd-workflow | RED → GREEN → REFACTOR |
| brainstorming | Design before code |
| agent-teams | Parallel orchestration |
| security-audit | Security checks |
| humanizer | Remove AI-writing patterns |

### 5.4 Permissions — defense-in-depth

27 deny rules + PermissionRequest hook = enterprise-level security. Geoscan полагается на **дефолтные** permissions.

### 5.5 Status line + Spinner tips

Custom status bar + 21 educational tips — улучшают DX, но Geoscan их не использует.

---

## 6. ЧТО НЕ ИСПОЛЬЗУЕТ НИ ОДИН

| Возможность | Geoscan | Ваш config | Impact |
|------------|---------|-----------|--------|
| MCP servers (.mcp.json) | ❌ | ❌ | GitHub MCP → прямой доступ к PRs |
| Plugins (enabled) | ❌ | ❌ (2 disabled) | LSP code intelligence, CI tools |
| /schedule (cloud) | ❌ | ❌ | Ночные pipeline runs |
| Worktrees | ❌ | ❌ | Isolated experiments |
| Sandbox | ❌ | ❌ (Win limit) | OS-level isolation |
| Auto mode | ❌ | ❌ | Fewer permission prompts |
| Headless CI | ❌ | ❌ | AI в CI/CD pipeline |
| Chrome extension | ❌ | ❌ | Browser automation |
| Channels | ❌ | ❌ | Push notifications |

---

## 7. РЕКОМЕНДАЦИИ ДЛЯ GEOSCAN

### 🔴 Высокий приоритет

| # | Что | Почему | Действие |
|---|-----|--------|----------|
| 1 | **Добавить .claude/settings.json** | Нет permissions → default mode, Claude может всё | Скопировать deny rules из вашего global |
| 2 | **Добавить hooks** | 0 hooks = 0 автоматизации | Минимум: pre_commit_guard, security_verify, post_format |
| 3 | **GitHub MCP** | PRs через web вместо прямого API | `.claude/.mcp.json` с GitHub token |
| 4 | **Проектные agents** | Нет domain-specific agents | `geology-reviewer.md` — проверяет geological claims, ADR-005 compliance |

### ⚠️ Средний приоритет

| # | Что | Почему | Действие |
|---|-----|--------|----------|
| 5 | **Coverage gate** | Tests: 172, но coverage% неизвестен | `pytest --cov=src --cov-fail-under=70` в CI |
| 6 | **Type checking в CI** | basedpyright настроен, но не в CI | Добавить step в ci.yml |
| 7 | **Security scan в CI** | Makefile имеет bandit + pip-audit | Добавить в GitHub Actions |
| 8 | **Pyright-lsp plugin** | Нет real-time type checking | `/plugin install pyright-lsp@claude-plugins-official` |

### ⚪ Низкий приоритет

| # | Что | Почему |
|---|-----|--------|
| 9 | `/schedule` для nightly pipeline runs | Автоматический re-run при новых снимках |
| 10 | Worktree для экспериментов | Изолированные ветки для Phase B features |
| 11 | Agent Teams для review | review-squad при больших изменениях |

---

## 8. ИТОГОВАЯ ОЦЕНКА

### Geoscan Gold 2026

| Аспект | Оценка | Комментарий |
|--------|--------|-------------|
| **CLAUDE.md** | ⭐⭐⭐⭐⭐ | Эталонный. Domain-specific anti-hallucination = gold standard |
| **Project memory** | ⭐⭐⭐⭐⭐ | activeContext 172 строки, projectOverview 203 строки |
| **ADR** | ⭐⭐⭐⭐⭐ | 11 ADR, включая meta-learning от ошибок Codex |
| **Code quality** | ⭐⭐⭐⭐ | 172 tests, type hints, Pydantic, structlog |
| **CI/CD** | ⭐⭐⭐ | Базовый (lint + test), нет coverage/security |
| **Docker** | ⭐⭐⭐ | Есть, но не в CI |
| **Hooks/Agents/Skills** | ⭐ | Не используются (0%) |
| **MCP/Plugins** | ⭐ | Не используются (0%) |
| **Automation** | ⭐ | Всё ручное |

### Ваш global config

| Аспект | Оценка | Комментарий |
|--------|--------|-------------|
| **CLAUDE.md** | ⭐⭐⭐⭐ | Хороший, но generic (не project-specific) |
| **Project memory** | ⭐⭐ | Templates есть, но не применяются к проектам |
| **ADR** | ⭐⭐ | Шаблон есть, не заполняется |
| **Hooks** | ⭐⭐⭐⭐⭐ | 30 scripts, 20/26 events — enterprise level |
| **Agents** | ⭐⭐⭐⭐⭐ | 9 + 3 teams с memory и isolation |
| **Skills** | ⭐⭐⭐⭐⭐ | 19 skills, routing-policy |
| **Permissions** | ⭐⭐⭐⭐⭐ | 27 deny rules + PermissionRequest hook |
| **MCP/Plugins** | ⭐ | 8 cloud MCP, 2 plugins disabled |
| **Status line** | ⭐⭐⭐⭐ | Custom statusline.py + 21 tips |

### Идеальная комбинация

```
Geoscan CLAUDE.md + project memory + ADR
    +
Ваш global hooks + agents + skills + permissions
    +
Missing: MCP (.mcp.json) + Plugins (enabled) + scheduling + worktrees
    =
~90% потенциала Claude Code
```

---

## 9. WHAT GEOSCAN DOES UNIQUELY WELL (стоит перенять)

| Паттерн | Описание | Применимость |
|---------|----------|-------------|
| **Domain anti-hallucination** | 7 конкретных ошибок, не generic "be honest" | Любой ML/data проект |
| **Codex error ADR** | ADR-010, ADR-011 записывают ошибки AI-агентов | Все проекты с AI delegation |
| **Context Recovery section** | Одно предложение для восстановления контекста после /clear | Все проекты |
| **Dual-IDE memory** | .claude/ + .cursor/ параллельно | Если используете оба |
| **Mandatory disclaimers** | Pydantic отвергает output без warnings | Любой проект с external stakeholders |
| **Pipeline flow в CLAUDE.md** | Data flow от input до output | ETL, ML pipelines |
| **NO SYNTHETIC rule** | SyntheticDetector блокирует fake data | ML production code |
| **Честные слабые стороны в docs** | LIMITATIONS.md | Научные проекты |
