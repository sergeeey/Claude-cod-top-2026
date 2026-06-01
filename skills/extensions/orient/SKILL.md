---
name: orient
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-05-26]
  Быстрый брифинг проекта на основе СВЕЖИХ данных — git log + git status +
  raw notes за 14 дней + активные удалённые задачи. Не доверяет автоматически
  activeContext.md (он часто summarized и отстаёт на недели). Запускать при
  первом открытии после паузы, переключении между проектами, или когда забыл
  где остановился.
  Triggers: /orient, orient me, что за проект, где я, покажи контекст, refresh my memory,
  открыл проект, давно не работал, напомни что делали, what is this project,
  where did we leave off, catch me up, project briefing, покажи статус проекта,
  я забыл что делал, what were we working on, введи в курс дела.
effort: minimal
tokens: ~700
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : orient
TL;DR  : Брифинг проекта из СВЕЖИХ источников (git+raw+remote), а не stale memory
Вызов  : /orient, что за проект, где я, давно не работал, refresh my memory
НЕ для : Глубокого анализа кода или планирования — только быстрый контекст
-->

# Orient — Project Briefing (Fresh-First)

Дать пользователю одностраничный брифинг проекта за минимальное время.
Пользователь открыл папку которую не видел несколько дней/недель и хочет вспомнить
где он был, что в процессе, и что осталось.

## Главный принцип — FRESH-FIRST

**Никогда не доверяй автоматически `activeContext.md` как источнику истины.**
Этот файл часто summarized и отстаёт от реальности на недели.

Источники по убыванию свежести:
1. 🟢 **Fresh (всегда верить):** `git log`, `git status`, файлы в `raw/` за 14 дней
2. 🟡 **Recent (проверить дату):** `.claude/memory/checkpoints/` последний по mtime
3. 🟠 **Possibly stale (валидировать):** `activeContext.md` — если mtime > 7 дней или есть `[summarized]` маркеры — пометить как `[STALE]`
4. 🔵 **Static (не меняется):** `CLAUDE.md`, `README.md`

## Шаг 1 — Определи папку проекта

Если пользователь указал путь в сообщении — используй его.
Иначе — текущий рабочий каталог (`.`).

## Шаг 2 — Собери СВЕЖИЕ данные ПЕРВЫМИ (параллельно через одну Bash команду)

Запусти всё одной Bash командой для скорости:

```bash
echo "=== GIT LOG (20 last) ===" && git log --oneline -20 2>&1
echo "=== GIT STATUS ===" && git status --short 2>&1
echo "=== GIT BRANCH ===" && git branch --show-current 2>&1
echo "=== RECENT FILES (14d) ===" && find . -type f -newer "$(date -d '14 days ago' +%Y-%m-%d 2>/dev/null || date -v-14d +%Y-%m-%d)" \
  -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/__pycache__/*' \
  -name '*.md' 2>/dev/null | head -20
echo "=== RAW NOTES (last 7d) ===" && ls -lt ~/.claude/memory/raw/ 2>/dev/null | head -10
echo "=== CHECKPOINTS ===" && ls -lt .claude/checkpoints/ 2>/dev/null | head -3
echo "=== ACTIVECONTEXT MTIME ===" && stat -c '%y' .claude/memory/activeContext.md 2>/dev/null || stat -f '%Sm' .claude/memory/activeContext.md 2>/dev/null
echo "=== UNCOMMITTED DIFF SIZE ===" && git diff --stat 2>&1 | tail -3
```

Затем — статичные источники:
- `CLAUDE.md` (если есть) — цель проекта
- `README.md` (если есть) — публичное описание
- `.claude/memory/activeContext.md` — но **проверь дату**, пометь как `[STALE]` если >7 дней

## Шаг 3 — Детектируй активные внешние задачи

Грепни в `~/.claude/memory/` и в проекте за последние 14 дней ключевые маркеры:

```bash
# Remote endpoints / serverside jobs
grep -rE "ssh|tmux|screen|nohup|systemd|HANDOFF|RERUN" ~/.claude/memory/raw/ \
  .claude/memory/ 2>/dev/null | head -10

# Long-running processes started recently
grep -rE "started.*[0-9]{4}-[0-9]{2}-[0-9]{2}|ETA|in progress" \
  .claude/memory/ 2>/dev/null | head -5
```

Если нашёл упоминания — добавь секцию **🌐 АКТИВНЫЕ ВНЕШНИЕ ЗАДАЧИ** с пометкой "проверить состояние".

## Шаг 4 — Проверь drift (рассинхрон между activeContext и реальностью)

Если в activeContext.md есть числа (Tests: N, Coverage: X%, HOOKS: N) — сравни с реальностью:
- `pytest --collect-only -q 2>&1 | tail -1` для теста count
- `ls hooks/*.py | wc -l` для hooks count
- Если расходится >5% → пометь как `[DRIFT: actContext says X, actual Y]`

## Шаг 5 — Выведи брифинг

Используй этот формат. Каждая секция помечена источником.

```
🗺️ ORIENT — [Название проекта]
════════════════════════════════

📌 ЧТО ЭТО                                       [source: CLAUDE.md]
  [1-3 строки: цель проекта и для кого]
  Стек: [технологии через запятую]
  Repo: [github URL если есть в git remote]

📅 ПОСЛЕДНЯЯ АКТИВНОСТЬ                          [source: git log]
  • [последний коммит: hash | дата | описание]
  • [предпоследний коммит]
  • [+N коммитов за последние 7 дней]
  Uncommitted: [N файлов / "clean"]

🔥 ЧТО В ПРОЦЕССЕ (свежее, 7-14 дней)            [source: raw/ + git]
  • [тема из raw notes, дата]
  • [тема из последних коммитов]
  • [тема из uncommitted diff]

🌐 АКТИВНЫЕ ВНЕШНИЕ ЗАДАЧИ                       [source: memory grep]
  ⚠️ ПРОВЕРИТЬ: [server / tmux / handoff с указанием когда последний раз touched]
  → Команда для проверки: ssh ... / git fetch / ls remote logs

⏳ ЧТО ОСТАЛОСЬ                                  [source: activeContext / TODO]
  [Если activeContext старше 7 дней — добавь префикс [STALE может быть устаревшим]]
  • [пункт из TODO/PLAN]
  • [пункт из roadmap]

🔴 ГОРИТ                                         [только если реально критично]
  • [дедлайн / сломанный CI / блокер / длительный idle процесс на сервере]
  • [drift: activeContext врёт про X — реально Y]

▶ СЛЕДУЮЩИЙ ШАГ
  [Одно конкретное действие чтобы продолжить работу]
  [Если есть unverified внешний state — сначала проверка]
```

## Правила качества

**Свежесть > красота.** Лучше 3 строки из вчерашнего git log чем 20 из месячного activeContext.

**Каждая секция помечена источником.** `[source: git log]`, `[source: raw notes 2026-05-25]`, `[source: activeContext, may be STALE]`.

**Active remote check — обязательно.** Если в памяти упоминается сервер, tmux, или handoff за последние 14 дней — ВСЕГДА включай секцию **🌐 АКТИВНЫЕ ВНЕШНИЕ ЗАДАЧИ** с явным предложением проверить. Это критично — пользователь может терять часы на молча мёртвых job'ах.

**Drift detection.** Если activeContext говорит "Tests: 1167" а pytest collects 1306 — пометь `[DRIFT]`. Это сигнал что файл надо обновить.

**Конкретно, не абстрактно.** Вместо "работали над кодом" → "починили S³ Dirac operator k=0 branch (коммит 093573b, вчера)".

**Без вопросов.** Пользователь хочет быстрый ответ, не диалог. Собери всё сам.
Единственное исключение: если совсем непонятно какой проект — спроси путь.

**Коротко.** Брифинг умещается на один экран. Если данных много — выбирай свежее.

## Anti-patterns (не делать)

❌ Цитировать activeContext.md без проверки даты — он часто устарел на недели
❌ Брать только `git log -7` если есть 50 коммитов за неделю — увеличь до 20
❌ Игнорировать `git status` — uncommitted = горячая работа
❌ Пропускать `raw/` notes — там самые свежие наблюдения
❌ Не упоминать активные удалённые задачи — пользователь забудет про них
❌ Молча верить числам из activeContext (tests count, coverage %) — проверять
