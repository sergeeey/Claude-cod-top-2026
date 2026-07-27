<!-- BSV — Brief Skill View | поиск: BSV
Скил   : incident-response
TL;DR  : Сквозной цикл инцидента: Triage → Containment → RCA → Fix → Postmortem → Pattern
Вызов  : /incident-response, SEV1, инцидент, авария на проде, постмортем, outage
НЕ для : Планирования capacity, мониторинга в норме, code review без инцидента
-->

---
name: incident-response
source: "wshobson/agents (adapted) + сквозной цикл v2.0"
version: "2.0.0"
description: >
  Сквозной цикл производственного инцидента: Triage → Containment → Root Cause (5 Whys) →
  Fix → Postmortem → Pattern в memory. Каждый шаг питается выходом предыдущего.
  Включает runbook-шаблоны, communication templates, blameless postmortem.
  Triggers: /incident-response, postmortem, runbook, incident, outage, SEV1, SEV2,
  on-call, инцидент, постмортем, авария на проде, разбор инцидента.
  [STATUS: active] [CONFIDENCE: high] [VERSION: 2.0.0]
allowed-tools: Read, Grep, Glob, Bash, WebSearch
---

# /incident-response — Сквозной цикл инцидента

> **Главное правило при панике:** не прыгать к Root Cause не сделав Containment.
> Пока ищешь причину — инцидент расширяется. Сначала останови, потом разбирайся.

```
Инцидент обнаружен
  ↓
[Step 0: Severity + War Room]   — объявить, собрать команду
  ↓ severity питает SLA →
[Step 1: Containment]           — остановить кровотечение
  ↓ что остановили питает →
[Step 2: Root Cause Analysis]   — 5 Whys + Causal Debug
  ↓ причина питает →
[Step 3: Fix + Rollout]         — применить + верифицировать
  ↓ fix питает →
[Step 4: Resolution]            — объявить resolved + коммуникация
  ↓ всё питает →
[Step 5: Postmortem]            — blameless разбор (T+24h)
  ↓ выводы питают →
[Step 6: Pattern → memory]      — [AVOID] в patterns.md
```

---

## Step 0 — Severity + War Room (первые 2 минуты)

### Severity Classification

| Severity | Impact | Response SLA |
|---|---|---|
| **SEV1** | Полный outage, потеря данных | 15 мин |
| **SEV2** | Критическая деградация, >20% пользователей | 30 мин |
| **SEV3** | Некритичная деградация | 2 часа |
| **SEV4** | Минимальный impact, один пользователь | Следующий рабочий день |

### Действия (параллельно):
```markdown
- [ ] Объявить severity: написать в #incidents "SEV[N] — [сервис] — [симптом]"
- [ ] Назначить Incident Commander (IC) — принимает решения
- [ ] Назначить Communications Lead — пишет обновления каждые 15 мин
- [ ] Открыть war room (Zoom/Meet link)
- [ ] Отправить Initial Notification (шаблон ниже)
```

**Initial Notification:**
```
[INVESTIGATING] SERVICE: [name] | SEV[N]
Impact: [что сломано, кто затронут, % трафика]
Started: [время UTC]
IC: @[name] | Comms: @[name]
Next update: 15 min
```

**Выход Step 0 → питает Step 1:** задокументированный severity + назначенные роли.

---

## Step 1 — Containment (остановить кровотечение)

**Цель:** минимизировать impact ДО того как найдена root cause.

```markdown
Быстрые действия в порядке приоритета:
- [ ] Проверить последний деплой (был ли в последние 2 часа?)
      → ДА: rollback немедленно, не разбираться почему
- [ ] Feature flags — выключить сломанную фичу
- [ ] Circuit breaker — изолировать проблемный сервис
- [ ] Traffic routing — перенаправить на здоровые инстансы
- [ ] Scale up — если проблема в нагрузке
```

```bash
# Проверить последние деплои
kubectl rollout history deployment/[name] -n [namespace]

# Rollback если деплой подозревается
kubectl rollout undo deployment/[name] -n [namespace]
kubectl rollout status deployment/[name] -n [namespace]

# Проверить статус подов
kubectl get pods -n [namespace]
kubectl logs -l app=[name] -n [namespace] --since=10m | grep ERROR | tail -50
```

**Не найден быстрый fix за 5 мин → продолжай containment параллельно с Step 2.**

**Выход Step 1 → питает Step 2:** что было сделано для containment + остаточный impact.

---

## Step 2 — Root Cause Analysis

**5 Whys + Causal Debug из `rules/integrity.md`:**

```markdown
Симптом: [observable failure — конкретно]

1. Почему? → [первая причина]
2. Почему? → [вторая причина]
3. Почему? → [третья причина]
4. Почему? → [четвёртая причина]
5. Почему? → [root cause — системный, исправимый]
```

**5 Causal Debug вопросов (из integrity.md):**
```
1. Что изменилось? — git diff, git log -5, последние деплои
2. Что говорит ошибка? — читать ПОЛНЫЙ traceback, не только последнюю строку
3. Какие допущения я делаю? — перечислить 3, проверить каждое инструментом
4. Это реальная ошибка или симптом? — crash site ≠ bug site
5. Что бы я сказал другому инженеру? — rubber duck
```

**Диагностика по типу:**

```bash
# High memory / OOM
kubectl top pods -n [namespace]

# Database connection exhaustion
-- СНАЧАЛА CHECK COUNT, не удалять сразу:
SELECT count(*) FROM pg_stat_activity
WHERE state = 'idle' AND query_start < now() - interval '10 minutes';
-- ВЫПОЛНЯТЬ только если count разумный:
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE state = 'idle' AND query_start < now() - interval '10 minutes';

# Disk / IO
df -h && iostat -x 1 5

# Network
netstat -an | grep ESTABLISHED | wc -l
```

**Выход Step 2 → питает Step 3:** root cause одним предложением + contributing factors.

---

## Step 3 — Fix + Rollout

На основе root cause из Step 2:

```markdown
- [ ] Fix разработан и проверен в staging (если есть)
- [ ] Fix применён с наблюдением за метриками
- [ ] Rollback plan готов если fix ухудшит ситуацию
- [ ] Верификация: ключевые метрики вернулись к baseline
```

**Verification checklist:**
```bash
# Проверить error rate вернулся к норме
# Проверить latency P99 в норме
# Проверить что affected users снова могут работать
# Дать 5 мин стабильности перед объявлением resolved
```

**Выход Step 3 → питает Step 4:** подтверждённый fix + метрики recovery.

---

## Step 4 — Resolution

```markdown
- [ ] Объявить RESOLVED в #incidents
- [ ] Отправить Resolution Notification
- [ ] Обновить status page
- [ ] Поблагодарить команду
```

**Resolution Notification:**
```
[RESOLVED] SERVICE: [name] | SEV[N]
Duration: [X min]
Root cause: [одно предложение]
Fix applied: [что было сделано]
Postmortem: [link — добавить позже]
Users affected: [N / % трафика]
```

**Выход Step 4 → питает Step 5:** полный timeline + все артефакты инцидента.

---

## Step 5 — Postmortem (T+24h после resolution)

### Когда писать

| Trigger | Обязательно? |
|---|---|
| SEV1 или SEV2 | Да |
| Customer-facing outage >15 мин | Да |
| Потеря данных или security incident | Да |
| Новый тип отказа | Да |
| Near-miss с потенциально высокой severity | Да |
| SEV3 с интересным root cause | Рекомендуется |

### Blameless культура

| Blame-focused ❌ | Blameless ✅ |
|---|---|
| "Кто это сделал?" | "Какие условия позволили этому случиться?" |
| Наказать человека | Улучшить систему |
| Страх → скрывать инциденты | Безопасность → сообщать о всём |

**Core principle:** если человек сделал ошибку → спроси что сделало эту ошибку возможной, не кто её сделал.

### Шаблон постмортема

```markdown
# Postmortem: [Сервис] — [Дата] — [Краткое описание]

**Severity:** SEV[N]
**Duration:** [start] до [end] UTC ([X] мин)
**Author(s):** [имена]
**Status:** Draft / In Review / Final

---

## Executive Summary
[2-3 предложения: что сломалось, impact на пользователей, root cause, как починили]

## Impact
- **Пользователей затронуто:** [N / % трафика]
- **Revenue impact:** [$N estimated]
- **SLA breach:** Yes / No
- **Потеря данных:** Yes / No

## Timeline (UTC)
| Время | Событие |
|---|---|
| HH:MM | Алерт сработал: [название] |
| HH:MM | On-call engineer получил уведомление |
| HH:MM | [действие / наблюдение] |
| HH:MM | Root cause найден |
| HH:MM | Mitigation применён |
| HH:MM | Инцидент resolved |

## Root Cause — 5 Whys
[заполненный из Step 2]

## Contributing Factors
- [Фактор 1: напр., нет runbook для этого сценария]
- [Фактор 2: напр., threshold алерта слишком высокий]
- [Фактор 3: напр., нет circuit breaker на зависимости]

## Что сработало хорошо
- [Вещь 1: напр., on-call пейджнули за 5 мин]
- [Вещь 2: напр., rollback за 3 мин]

## Что можно улучшить
- [Вещь 1: напр., root cause искали 45 мин]
- [Вещь 2: напр., status page не обновляли 30 мин]

## Action Items
| Action | Owner | Priority | Due | Status |
|---|---|---|---|---|
| [Добавить circuit breaker в X] | @engineer | P1 | YYYY-MM-DD | Open |
| [Обновить runbook для сценария Y] | @engineer | P2 | YYYY-MM-DD | Open |
| [Снизить threshold алерта с 5% до 1%] | @engineer | P2 | YYYY-MM-DD | Open |

## Lessons Learned
[Что предотвратит этот класс инцидентов?]
```

**Выход Step 5 → питает Step 6:** заполненный постмортем + action items.

---

## Step 6 — Pattern → Memory

После постмортема — обязательно зафиксировать паттерн:

```bash
# Добавить в ~/.claude/memory/patterns.md или проект patterns.md
echo "## [AVOID] [Дата] — [Тип отказа]
Что случилось: [1 предложение]
Root cause: [1 предложение]
Как предотвратить: [конкретное действие]
" >> patterns.md
```

**Если это повторение уже известного паттерна:**
```bash
# Найти паттерн в patterns.md
grep -i "KEYWORD" patterns.md
# Инкрементировать счётчик: [AVOID ×N] → [AVOID ×N+1]
# Добавить строку: "- Recurrence [дата]: [краткое описание]"
```

**Выход Step 6:** `[AVOID ×N]` запись в patterns.md — инцидент не повторится по той же причине.

---

## Quick Checklist (для 3 AM мозга)

```markdown
## Quick Checklist — [СЕРВИС] Outage

- [ ] 1. Объявить severity, открыть war room
- [ ] 2. Назначить IC + Communications Lead
- [ ] 3. Отправить Initial Notification в #status
- [ ] 4. Проверить последние деплои (последние 2 часа)
- [ ] 5. Rollback если деплой подозревается
- [ ] 6. Containment: feature flag / circuit breaker / scale up
- [ ] 7. Начать 5 Whys (параллельно с containment)
- [ ] 8. Обновление статуса каждые 15 мин до resolution
- [ ] 9. После resolution: постмортем T+24h
- [ ] 10. Паттерн в patterns.md
```

---

## Escalation Matrix

| Роль | Когда эскалировать | Контакт |
|---|---|---|
| On-call engineer | Немедленно | PagerDuty |
| Team lead | >15 мин нерешённый SEV1 | @[name] |
| VP Engineering | Потеря данных клиентов / >1ч SEV1 | @[name] |
| Legal / Security | Подозрение на data breach | [email] |

---

## Связанные скиллы

| Step | Скилл / инструмент |
|---|---|
| 2 | `integrity.md` (Causal Debug — 5 вопросов) |
| 5 | `/pre-mortem` (превентивный, до инцидента) |
| 6 | `memory-protocol.md` (паттерны) |
| Все | `rules/security.md` (если data breach) |
