---
name: vault-health
sub_type: guide
version: "1.0"
last_tested: "2026-05-07"
description: Obsidian vault health audit — finds orphaned projects, stale MOCs, stuck pipeline items. Reads actual files before declaring issues. Fixes what is safe, reports the rest. Triggers: /vault-health, vault audit, find orphans, check vault, аудит vault, что не так в vault. USE when you need to clean up vault hygiene without manual scanning.
argument-hint: "[--scan | --fix | --full]"
context: fork
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - mcp__obsidian-vault__search_notes
  - mcp__obsidian-vault__read_note
  - mcp__obsidian-vault__write_note
  - mcp__obsidian-vault__list_directory
  - mcp__obsidian-vault__get_vault_stats
  - mcp__obsidian-vault__list_all_tags
  - mcp__obsidian-vault__update_frontmatter
  - mcp__obsidian-vault__patch_note
  - mcp__obsidian-vault__get_notes_info
  - mcp__obsidian-vault__get_frontmatter
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : vault-health
TL;DR  : Аудит Obsidian vault: orphaned projects, stale MOCs, stuck pipeline items
Вызов  : /vault-health, vault health, --scan, --fix, --full
НЕ для : Разовые поиски по vault, задачи без проверки структурной целостности
-->

# vault-health — Obsidian Vault Audit & Sync

Аудит vault'а C:\Users\serge\Documents\claude-vault\ по 5 проверкам.
Структура vault'а жёстко закодирована — скилл знает ЭТУ конкретную конфигурацию.

## Режимы

| Вызов | Что делает |
|---|---|
| /vault-health | --scan по умолчанию: только читает, ничего не пишет |
| /vault-health --fix | scan + автофикс безопасных проблем |
| /vault-health --full | --fix + запись health report в _auto/ |

Запомни режим из аргументов: $ARGUMENTS. Если пусто — режим --scan.

---

## PHASE 1: PARALLEL SCAN

Выполни все reads параллельно (одним блоком tool calls):

### 1a. Читай все 8 MOC файлов
Пути:
- mocs/AI-Era Engineering MOC.md
- mocs/ARCHCODE MOC.md
- mocs/Claude-cod-top-2026 MOC.md
- mocs/Essentialism MOC.md
- mocs/GeoMiro MOC.md
- mocs/Research Science MOC.md
- mocs/Security MOC.md
- mocs/Solo Founding MOC.md

Для каждого MOC извлеки:
- Все [[wikilinks]] — это project references
- frontmatter поля: updated, status, date

### 1b. Список projects/
Вызови mcp__obsidian-vault__list_directory с path="projects"
Собери: все .md файлы (не папки) → это твой PROJECTS_INVENTORY

### 1c. Читай pipeline/active/ и pipeline/inbox/
Вызови mcp__obsidian-vault__list_directory для обоих.
Для каждого файла (кроме .keep) — читай frontmatter: created, updated, stage, type, remind_date

### 1d. Vault stats
Вызови mcp__obsidian-vault__get_vault_stats

---

## PHASE 2: GAP ANALYSIS

### Проверка 1: MOC Orphans (CRITICAL — читай файлы ДО объявления orphan)

АЛГОРИТМ:
1. Возьми PROJECTS_INVENTORY (список файлов из projects/)
2. Возьми все [[wikilinks]] из всех 8 MOC файлов
3. Нормализуй: убери [[]], aliases (часть после |), путь без расширения
4. ORPHAN = файл в projects/ чьё имя НЕ найдено ни в одном wikilink из MOC
5. ВАЖНО: wikilink [[projects/archcode|ARCHCODE]] содержит "archcode" — файл archcode.md НЕ orphan

Для нормализации: проверяй substring match (не только exact), т.к. [[CogniRouter — Project]] матчит CogniRouter — Project.md

### Проверка 2: Stale MOCs

Для каждого MOC:
- Дата = frontmatter "updated" ИЛИ "date" ИЛИ "created" (в порядке приоритета)
- STALE = дата > 14 дней до сегодня (TODAY = используй `date +%Y-%m-%d` для получения текущей даты)
- Если дата отсутствует вообще → пометь как DATE_MISSING

### Проверка 3: Pipeline Health

Для каждого файла в pipeline/active/:
- STUCK = frontmatter "created" или "updated" < 30 дней до сегодня
  ВАЖНО: created: 2026-05-01 = 1 день → НЕ stuck
- Читай remind_date — если он в будущем, файл активно отслеживается

Для pipeline/inbox/:
- PENDING = любой файл который не .keep (нужно routing)
- Читай: type, stage, priority, remind_date

### Проверка 4: Tag Health (только репорт, не фиксим)

Вызови mcp__obsidian-vault__list_all_tags
Найди:
- Явные дубли: lesson/lessons, lesson-learned/lessons-learned, strategy/стратегия
- Noise теги: tag1, tag2, xxx, all (если есть)
- Теги встречающиеся только 1 раз (возможно опечатки)

Не меняй теги автоматически. Только репорт.

### Проверка 5: activeContext.md актуальность

Читай корневой activeContext.md
Проверь: упоминаются ли там проекты которые реально killed (ArgosArb, Router Class B)?
Отметь расхождения для ручного внимания.

---

## PHASE 3: AUTO-FIX (только если --fix или --full)

### Fix 1: Orphaned projects → добавить в нужный MOC

Для каждого ORPHAN определи целевой MOC по routing map:

ROUTING MAP (по тегам и имени файла):
| Паттерн | Целевой MOC |
|---|---|
| теги: genomics, archcode, mpemba, physics, research | Research Science MOC |
| теги: solo-founding, startup, mvp, saas, product | Solo Founding MOC |
| теги: security, pentest, blindspotsec, audit | Security MOC |
| теги: geomiro, geopolitics, geoscan | GeoMiro MOC |
| теги: claude-code, claude-cod-top-2026 | Claude-cod-top-2026 MOC |
| теги: essentialism, productivity, snr | Essentialism MOC |
| теги: ai, agents, llm, architecture | AI-Era Engineering MOC |
| Нет совпадений | Solo Founding MOC (default) |

Для добавления в MOC:
- Solo Founding MOC: добавить строку в секцию "## Активные проекты"
  Формат: `- [[projects/FILENAME|DISPLAY_NAME]] · DESCRIPTION`
- Research Science MOC: добавить в секцию "## Активные исследования"
  Формат: `- [[projects/FILENAME|DISPLAY_NAME]] — DESCRIPTION`
- Остальные MOC: добавить в секцию "## Проекты" (создать если нет)
  Формат: `- [[projects/FILENAME]]`

Используй mcp__obsidian-vault__patch_note с правильным oldString из текущего содержимого MOC.
ЕСЛИ patch_note не работает (ошибка "oldString cannot be empty") — используй mcp__obsidian-vault__read_note + mcp__obsidian-vault__write_note с обновлённым контентом.

### Fix 2: Stale MOC — обновить frontmatter updated

Для каждого STALE MOC:
Вызови mcp__obsidian-vault__update_frontmatter с:
  path: "mocs/XXX MOC.md"
  updates: { updated: "$TODAY", health_checked: "$TODAY" }
  где $TODAY = результат `date +%Y-%m-%d` (выполни перед циклом Fix 2)

СТЕЙЛ = только обновляем дату, НЕ меняем содержимое.

### Fix 3: Pipeline inbox → route items

Для каждого PENDING inbox item применяй классификатор:

INBOX CLASSIFIER (читай frontmatter):
| Условие | Действие |
|---|---|
| type: pipeline-idea ИЛИ type: project-idea | Оставить в inbox (remind_date контролирует) |
| type: hypothesis | Переместить в pipeline/hypothesis/ |
| type: lesson ИЛИ type: lesson-learned | Переместить в raw/ |
| type: research ИЛИ type: analysis | Переместить в knowledge/ |
| remind_date в будущем | Не трогать (ждёт своего времени) |
| remind_date в прошлом | Флаг: "Remind date просрочена, нужна ручная обработка" |

ВАЖНО: если у файла есть remind_date в будущем — НЕ перемещай автоматически, только репортируй когда срок.

---

## PHASE 4: HEALTH REPORT

### Считай Health Score

```
base_score = 10.0

penalties:
- за каждый ORPHAN: -0.3 (обоснование: навигационный gap)
- за каждый STALE MOC (>14 дней): -0.2 (обоснование: карта устарела)
- за каждый STUCK pipeline item (>30 дней): -0.2
- за inbox > 0 с просроченным remind_date: -0.1 за штуку
- за tag noise (tag1, tag2, xxx, all): -0.1 за тег
- за DATE_MISSING в MOC: -0.1 за штуку

floor: 0.0 (не может быть отрицательным)
```

### Выведи отчёт в этом формате:

```
🏥 Vault Health: X.X/10
Дата: 2026-MM-DD | Vault: 2525 notes, 112 folders

━━━ ПРОВЕРКИ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ MOC Coverage: N/8 MOCs имеют все проекты
✅ Pipeline Active: N items, все < 30 дней
⚠️  Stale MOCs: N штук (>14 дней без update)
⚠️  Orphaned projects: N файлов в projects/ без MOC entry
ℹ️  Pipeline Inbox: N items ожидают роутинга
ℹ️  Tag Health: N дублей найдено

━━━ AUTO-FIXED (только в --fix/--full) ━━━━━

[список что было исправлено]

━━━ РУЧНОЕ ВНИМАНИЕ ━━━━━━━━━━━━━━━━━━━━━

1. [конкретная проблема] → [конкретное действие]
2. ...

━━━ TAG AUDIT ━━━━━━━━━━━━━━━━━━━━━━━━━━━

Дубли:
- lesson/lessons/lesson-learned → унифицировать в: lessons-learned
- strategy/стратегия → унифицировать в: strategy (EN)

━━━ СТАТИСТИКА ━━━━━━━━━━━━━━━━━━━━━━━━━━

Projects инвентарь: N файлов
MOC coverage: N/N проектов охвачено
Pipeline active: N/N в рамках дедлайна
Inbox pending: N items

📅 Следующая проверка: +14 дней
```

### Если режим --full: записать отчёт в vault

Перед записью получи текущую дату: `date +%Y-%m-%d` → $TODAY
Вызови mcp__obsidian-vault__write_note с:
  path: "_auto/vault-health-$TODAY.md"
  frontmatter: { type: "health-report", date: "$TODAY", score: X.X, tags: ["vault", "health", "auto-generated"] }
  content: текст отчёта выше

---

## ВАЖНЫЕ ОГРАНИЧЕНИЯ

1. НЕ удаляй файлы автоматически
2. НЕ меняй теги автоматически (только репорт)
3. НЕ перемещай файлы из pipeline/inbox/ если у них remind_date в будущем
4. НЕ объявляй orphan пока не прочитал ВСЕ 8 MOC файлов и не проверил substring match
5. НЕ придумывай даты — используй только frontmatter "updated"/"date"/"created"
6. Если mcp__obsidian-vault__patch_note возвращает ошибку — используй read+write вместо отказа
7. content в write_note НЕ должен содержать тройные кавычки (input_guard блокирует)

---

## ПРИМЕР ПРАВИЛЬНОГО ORPHAN CHECK

Файл projects/CertifiedTwin — Project.md
Ищем "CertifiedTwin" в wikilinks всех MOC:
- AI-Era Engineering MOC: нет
- ARCHCODE MOC: нет
- Solo Founding MOC: нет "CertifiedTwin"
- Research Science MOC: нет
- ...все 8 проверены → ORPHAN подтверждён

Файл projects/CogniRouter — Project.md
Ищем "CogniRouter" в wikilinks:
- Solo Founding MOC: "[[CogniRouter — Project]]" → НАЙДЕН → НЕ orphan

---

## КЛЮЧЕВЫЕ ПУТИ VAULT'А

```
Vault root:     C:\Users\serge\Documents\claude-vault\
MOCs:           C:\Users\serge\Documents\claude-vault\mocs\
Projects:       C:\Users\serge\Documents\claude-vault\projects\
Pipeline:       C:\Users\serge\Documents\claude-vault\pipeline\active\ | pipeline\inbox\ | pipeline\queue\ | pipeline\hypothesis\
Raw:            C:\Users\serge\Documents\claude-vault\raw\
Knowledge:      C:\Users\serge\Documents\claude-vault\knowledge\
Areas:          C:\Users\serge\Documents\claude-vault\areas\
_auto:          C:\Users\serge\Documents\claude-vault\_auto\
activeContext:  D:\Claude-cod-top-2026\.claude\memory\activeContext.md  (НЕ в vault — это проектный файл)
```
