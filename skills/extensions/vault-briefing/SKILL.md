---
name: vault-briefing
sub_type: guide
version: "1.0"
last_tested: "2026-05-07"
description: >
  Брифинг из Obsidian vault перед стартом работы над проектом.
  Вводишь название проекта — скил сам ищет в vault: паттерны [AVOID]/[REPEAT],
  активные гипотезы, связанные проекты, методы и топ-5 заметок.
  Каждый результат объясняет ПОЧЕМУ он релевантен — не просто список ссылок.
  Триггеры: /vault-briefing [проект], --brief, --deep, --new, брифинг по проекту, что в vault про X.
  НЕ использовать для: поиска конкретного факта (используй Grep) — только для старта работы над проектом.
effort: medium
context: fork
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : vault-briefing
TL;DR  : Брифинг из Obsidian vault — паттерны, гипотезы, заметки с WHY перед стартом проекта
Вызов  : /vault-briefing [проект], --brief, --deep, --new
НЕ для : Поиск конкретного факта — только для старта проекта
-->

# Vault Briefing — Брифинг из Obsidian

## Назначение

Перед началом работы над проектом Claude должен знать:
- Что уже было сделано в этом направлении (не повторять)
- Какие паттерны [AVOID] применимы (не наступать на грабли снова)
- Какие гипотезы и методы уже изучены (использовать готовое)
- Какие заметки в vault прямо сейчас актуальны для этого проекта

**Без этого скилла:** пользователь вручную пишет "найди в Obsidian всё про X" каждый раз.
**С этим скиллом:** один вызов → структурированный брифинг с WHY-объяснением.

---

## Конфигурация vault

```
VAULT_ROOT = C:/Users/serge/Documents/claude-vault
PATTERNS   = C:/Users/serge/.claude/memory/_auto/patterns.md
WIKI       = C:/Users/serge/.claude/memory/wiki/
PROJECT_MD = VAULT_ROOT/projects/[PROJECT].md
```

---

## PHASE 1: DETECT PROJECT CONTEXT

**Входной аргумент:** `$ARGUMENTS` — название проекта или описание задачи.

### Шаг 1а: Читай project file если существует

```bash
# Ищем в projects/ файл с именем похожим на $ARGUMENTS
ls "C:/Users/serge/Documents/claude-vault/projects/" | grep -i "[PROJECT_KEYWORD]"
```

Если файл найден — читай его frontmatter:
- `tags:` → список тегов (основа поиска)
- `status:` → если killed/archived → особое внимание к lessons
- related упоминания внутри файла

### Шаг 1б: Определи домен автоматически

Если проект не найден или нет frontmatter — определяй домен по ключевым словам:

| Ключевое слово в названии | Домен | Дополнительные теги для поиска |
|---|---|---|
| geomiro, geo, scenario, graph | geopolitics | neo4j, graph-rag, scenario-planning |
| archcode, genomics, chromatin, variant | genomics | research, publication, biorxiv |
| verifind, verification, audit | ai-verification | llm, evaluation, accuracy |
| cogni, router, routing | ai-infrastructure | llm, agents, orchestration |
| mpemba, infompemba, physics | research | hypothesis, dynamics, simulation |
| mcp, claude, hooks, skills | ai-tooling | claude-code, automation |
| security, blindspot, osint | security | audit, vulnerability |
| reflexio, memory | memory-systems | knowledge, retention |

---

## PHASE 2: PARALLEL SEARCH

Выполни ВСЕ следующие поиски **одновременно** (один блок tool calls):

### 2а: Паттерны из patterns.md [HIGHEST PRIORITY]

```bash
grep -n -i -A3 "\[AVOID\]\|\[REPEAT\]" "C:/Users/serge/.claude/memory/_auto/patterns.md" | grep -i "[TAG1]\|[TAG2]\|[DOMAIN_KEYWORD]"
```

Ищи паттерны где хотя бы одно слово из тегов/домена проекта встречается в тексте.

### 2б: Активные гипотезы

```bash
ls "C:/Users/serge/Documents/claude-vault/pipeline/hypothesis/"
```
Читай frontmatter каждого файла: `tags`, `project`, `status`.

### 2в: Методология

```bash
ls "C:/Users/serge/Documents/claude-vault/knowledge/methodology/" 2>/dev/null
ls "C:/Users/serge/Documents/claude-vault/knowledge/tools/"
```
Ищи файлы с именами содержащими domain keywords.

### 2г: Wiki (обработанные уроки сессий)

```bash
grep -rl "[DOMAIN_KEYWORD]\|[TAG1]" "C:/Users/serge/.claude/memory/wiki/" | head -10
```

### 2д: MOC cross-references

Grep по уже прочитанным MOC (Solo Founding, Research Science, AI-Era Engineering):
найди упоминания похожих проектов как "related" или "смежный".

### 2е: killed/archived projects (ТОЛЬКО при --deep или если статус = killed)

```bash
grep -rl "KILLED\|killed\|status: killed\|status: archived" "C:/Users/serge/Documents/claude-vault/projects/" | head -5
```
Killed проекты = ценнейший источник lessons learned.

---

## PHASE 3: RELEVANCE SCORING

Для каждого найденного элемента считай Score (используй в уме, не показывай пользователю):

```
Relevance Score = Tag_overlap × 3 + Keyword_match × 2 + Domain_proximity × 1
```

- **Tag overlap:** сколько тегов проекта совпадают с тегами найденной заметки (0-5)
- **Keyword match:** сколько ключевых слов домена встречается в тексте (0-5)
- **Domain proximity:** прямой домен = 3, смежный = 2, косвенный = 1

**Фильтр:** показывай только элементы с Score ≥ 4.
**Лимит:** максимум 15 элементов в финальном выводе.
**Дедупликация:** если два элемента говорят одно и то же — оставь тот с выше Score.

---

## PHASE 4: STRUCTURED BRIEF

Выведи брифинг в этом формате:

```
## Context Brief: [PROJECT NAME]
Домен: [определённый домен] | Статус в vault: [найден/не найден/killed]

━━━ ⚠️ ПАТТЕРНЫ: НЕ ПОВТОРЯТЬ ━━━━━━━━━━━━━━━

[AVOID] [паттерн из patterns.md]
→ Почему релевантно: [объяснение связи с текущим проектом]
→ Как проявляется здесь: [конкретный риск]

(максимум 3 AVOID паттерна)

━━━ ✅ ЧТО РАБОТАЛО — ПРИМЕНИТЬ ━━━━━━━━━━━━━

[REPEAT] [паттерн]
→ Почему применимо: [объяснение]

(максимум 2 REPEAT паттерна)

━━━ 🔬 БЫЛО СДЕЛАНО В ЭТОМ НАПРАВЛЕНИИ ━━━━━━

[если есть killed/archived проект похожего типа]:
⚰️ [Название] — убит потому что [kill reason]
   Главный урок: [что можно взять]

[если есть active related проект]:
🔗 [Название] — [как связан] → можно переиспользовать [что именно]

━━━ 💡 АКТИВНЫЕ ГИПОТЕЗЫ ━━━━━━━━━━━━━━━━━━━

- [Гипотеза] — [почему релевантна для текущего проекта]

━━━ 🔧 МЕТОДЫ И ИНСТРУМЕНТЫ (уже изучены) ━━━

- [Метод/инструмент] из [файл] — [как применить здесь]

━━━ 📚 ТОП-5 ЗАМЕТОК ━━━━━━━━━━━━━━━━━━━━━━━

1. [[путь/к/заметке]] — WHY: [одна фраза почему именно эта заметка полезна]
2. ...

━━━ 🔗 РЕКОМЕНДУЕМЫЕ СВЯЗИ ━━━━━━━━━━━━━━━━━

Добавь в [PROJECT].md эти wikilinks:
- [[notes/X]] — [причина связи]
- [[notes/Y]] — [причина связи]

━━━ ❓ ПРОБЕЛЫ (чего нет в vault) ━━━━━━━━━━

[что было бы полезно но не найдено в vault]
→ Рекомендация: [создать заметку / запустить research / спросить /last30days]
```

---

## Режимы

### `/vault-briefing [проект]` — стандартный брифинг

Все 4 фазы, вывод полный.

### `/vault-briefing --brief [проект]` — быстрый старт (3 мин)

Только:
- Топ-3 AVOID паттерна
- Топ-3 релевантные заметки с WHY
- Один конкретный следующий шаг

### `/vault-briefing --deep [проект]` — глубокий поиск

Дополнительно к стандарту:
- Поиск в `_auto/wiki/` (AI-generated wiki)
- Поиск в `knowledge/research/` (концепции, эксперименты)
- Поиск в `knowledge/predictions/` (прогнозы релевантные домену)
- Поиск по `knowledge/lessons/` или `L3-skills/`
- Чтение 2-3 найденных файлов полностью (не только frontmatter)

### `/vault-briefing --new [проект]` — режим нового проекта

Если projects/[проект].md ещё не существует:
- Создать шаблон с правильным frontmatter
- Предложить связи с существующими MOC
- Предложить теги на основе домена

---

## ВАЖНЫЕ ПРАВИЛА

1. **WHY обязателен** — каждый элемент в выводе должен иметь объяснение почему именно он релевантен. Без WHY = бесполезный список ссылок.

2. **Читай файлы ДО объявления релевантности** — не угадывай по имени файла. Прочитай хотя бы frontmatter.

3. **Killed проекты ценнее активных** — если похожий проект был убит, это критическая информация. Всегда ищи причину смерти.

4. **Не дампить всё подряд** — лучше 5 точных результатов с объяснением, чем 20 без контекста.

5. **Пробелы тоже важны** — если чего-то нет в vault, это тоже инсайт. Скажи что не нашёл и предложи как получить.

6. **Используй Bash для поиска, Read для содержимого** — НЕ MCP для файлов с wikilinks (input_guard риск).

---

## ПРИМЕР ВЫВОДА: `/vault-briefing VeriFind`

```
## Context Brief: VeriFind
Домен: ai-verification | Статус в vault: найден (projects/verifind.md, P1)

━━━ ⚠️ ПАТТЕРНЫ: НЕ ПОВТОРЯТЬ ━━━━━━━━━━━

[AVOID] Lab-grade ML threshold не работает в real-world
→ Почему релевантно: VeriFind оценивает LLM outputs — threshold для "verified"
  будет отличаться на синтетических тестах vs реальных документах
→ Как проявляется: DIR 53% на paper trading может упасть на live data

[AVOID] Coverage overclaim — README заявляет метрику без верификации
→ Почему: Sharpe 3.7 — не публиковать пока нет 30-дневного скользящего окна

━━━ 🔬 БЫЛО СДЕЛАНО В ЭТОМ НАПРАВЛЕНИИ ━━

⚰️ ArgosArb — убит потому что рынок закрыл арбитражное окно
   Главный урок: validation-first + multi-agent + 0% hallucination
   → применимо к VeriFind verification pipeline

━━━ 💡 АКТИВНЫЕ ГИПОТЕЗЫ ━━━━━━━━━━━━━━━

- hypothesis-revival-engine: "LLM confidence scores не коррелируют с accuracy"
  → напрямую релевантно для VeriFind scoring model

━━━ 📚 ТОП-5 ЗАМЕТОК ━━━━━━━━━━━━━━━━━━

1. [[knowledge/research/concepts/Organic Virality]] — WHY: если VeriFind
   показывает Sharpe 3.7, виральный loop через "публичный leaderboard"
2. [[projects/verifind-harvest-2026]] — WHY: готовые harvest assets Score 17+
```

---

## Feedback (опционально)

После выдачи брифинга спроси одним сообщением:

> "Какие секции были полезны? Что можно пропустить в следующий раз?"

Если пользователь ответил — запиши в raw/:
```bash
echo "# Feedback vault-briefing $(date +%Y-%m-%d)

Проект: [ПРОЕКТ]
Полезно: [ответ]
Лишнее: [ответ]
#feedback #vault-briefing" > "C:/Users/serge/.claude/memory/raw/feedback-vault-briefing-$(date +%Y%m%d).md"
```

Не спрашивай если пользователь явно торопится или написал `--brief`.

---

## Связанные скилы

- `/harvest` — если нашёл полезный актив в vault → оцени Score
- `/vault-health` — если vault структура сломана до поиска
- `/hypothesis-arbiter` — если нашёл конкурирующие гипотезы
- `/snr` — если найденного слишком много → приоритизировать
