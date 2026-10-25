---
name: code-materiality
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-05-24]
  Triages code audit findings by their actual impact on the active scientific pipeline.
  Answers the key question: "does this bug actually affect what we're running right now?"
  Core insight: bug found ≠ current pipeline broken. Call graph trace from active entry
  point determines real exposure.
  Triggers: /code-materiality, code audit, "which bugs matter", "found bugs", materiality,
  "код аудит", "какие баги важны", "баги в коде", code review findings, "влияет ли это",
  "аудит нашёл баги", "critical bugs found".
  Invoke proactively when user pastes a list of bugs/findings from any code reviewer,
  linter, security scanner, or external audit — especially when the user seems unsure
  which findings require immediate action.
effort: medium
tokens: ~800
triggers: [/code-materiality, "code audit", "which bugs matter", "found bugs", materiality, "код аудит", "какие баги важны", "баги в коде", "code review findings", "влияет ли это", "аудит нашёл баги", "critical bugs found"]
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : code-materiality
TL;DR  : Триажируем баги из code audit по реальному влиянию на активный пайплайн
Вызов  : /code-materiality, "какие баги важны", "аудит нашёл баги", code audit triage
НЕ для : Общего code review без конкретного активного пайплайна/гейта
-->

# Code Materiality Audit

## Суть

Внешний code review находит баги в файлах проекта. Но не все баги равны:
- Баг в функции, которую активный пайплайн никогда не вызывает → **мусор для тикетов**
- Баг в критическом пути активного гейта → **стоп, чини сейчас**

Этот скил делает **call graph trace** от точки входа активного пайплайна и определяет,
какие найденные баги реально пересекаются с исполняемым кодом.

**Главный фильтр:** "bug found ≠ current pipeline broken"

---

## Когда активировать

- Получил список багов от code reviewer / linter / security scanner / внешнего аудита
- Не понимаешь, что чинить сейчас, а что можно отложить
- Нужно решить: перезапускать пайплайн или результаты валидны
- Пишешь `CODE_MATERIALITY_AUDIT.md` для проекта

---

## Что нужно от пользователя

Спроси (или извлеки из контекста):

1. **Список багов** — что нашёл аудит (файл:функция + описание)
2. **Активный пайплайн** — точка входа: имя гейта, скрипт, функция, тест
3. **Что уже запущено** — есть ли результаты, которые нужно оценить

---

## Алгоритм (4 шага)

### Шаг 1: Карта пайплайна

Определи точку входа активного пайплайна. Найди:
```
entry_point → вызывает → [список функций/модулей]
```

Инструменты:
- `grep -rn "def <function>" <project>/` — где определена
- `grep -rn "<function>(" <project>/` — где вызывается
- Читай import chain от entry point вниз

Зафиксируй **активный call graph** — множество функций, реально вызываемых пайплайном.

### Шаг 2: Intersection check

Для каждого бага из аудита:
```
баг в <файл>:<функция> → входит ли <функция> в активный call graph?
```

| Результат | Значение |
|-----------|---------|
| НЕ входит | Баг изолирован от активного пайплайна |
| Входит, но в ветку которая не выполняется | Условная экспозиция — нужна проверка |
| Входит, выполняется | Прямая экспозиция |

### Шаг 3: Вердикт по каждому багу

Для каждого бага назначь:

**Приоритет (A/B/C):**
- **A** — Immediate: баг в активном критическом пути, нужно чинить до следующего запуска
- **B** — Soon: баг в пайплайне, но не в критическом пути / есть workaround
- **C** — Backlog: баг вне активного пайплайна, технический долг

**Вердикт результатов:**
- `NO_ACTIVE_PIPELINE_IMPACT` — баг не пересекается с активным пайплайном; результаты валидны
- `PATCH_REQUIRED` — баг в пайплайне, но текущие результаты не затронуты; почини до следующего запуска
- `RERUN_REQUIRED` — баг мог исказить уже полученные результаты; нужен перезапуск
- `INCONCLUSIVE` — call graph неясен; нужна информация от пользователя

### Шаг 4: Создай CODE_MATERIALITY_AUDIT.md

---

## Формат вывода: CODE_MATERIALITY_AUDIT.md

Создай файл с такой структурой:

    # CODE_MATERIALITY_AUDIT — <Проект> / <Дата>

    ## Активный пайплайн
    - Entry point: `<файл>:<функция/скрипт>`
    - Гейт/задача: <название>
    - Статус: <что сейчас запущено / что уже получено>

    ## Call Graph (активный)
    
    entry_point
    ├── module_a
    │   ├── func_1  ← БАГ #2 (RERUN_REQUIRED)
    │   └── func_2
    └── module_b
        └── func_3  ← не затронуто

    ## Итоговый вердикт

    > PATCH_REQUIRED / NO_ACTIVE_PIPELINE_IMPACT / RERUN_REQUIRED / INCONCLUSIVE
    > [одно предложение почему]

    ## Баги по приоритету

    ### 🔴 A — Immediate (чинить сейчас)
    | # | Файл:Функция | Описание бага | Вердикт |
    |---|---|---|---|
    | B1 | file.py:func | описание | RERUN_REQUIRED |

    ### 🟡 B — Soon (до следующего запуска)
    | # | Файл:Функция | Описание бага | Вердикт |
    |---|---|---|---|
    | B3 | file.py:func | описание | PATCH_REQUIRED |

    ### 🟢 C — Backlog (технический долг)
    | # | Файл:Функция | Описание бага | Вердикт |
    |---|---|---|---|
    | B5 | file.py:func | описание | NO_ACTIVE_PIPELINE_IMPACT |

    ## Трассировка (доказательство)
    Для каждого A/B бага — доказательство входа в call graph:
    - B1: entry.py → module_a.func_1() (line 47) → баг: wrong sign in normalization
    - B3: entry.py → module_b.compute() (line 89, only if flag=True) → условная экспозиция

    ## Следующие шаги
    1. [ ] Приоритет A: <действие>
    2. [ ] Приоритет B: <действие>
    3. [ ] C зафиксированы в backlog: <ссылка>

---

## Шаг 2b — Silent Fallbacks (параллельно с Шагом 2)

Пока делаешь intersection check — добавь быстрый grep на silent fallbacks в active files:

```bash
grep -n "except.*pass\|except.*continue\|return full\|return \[\]\|nan_to_num\|fillna(0)" <active_files>
```

Если найдено → добавить в triage таблицу как отдельный пункт.
Полный 10-layer анализ silent fallbacks — см. `/sci-code-audit` Layer 2.

---

## Ключевые инсайты

**Почему это важно:**
Внешние аудиторы смотрят на код статически — они находят всё что теоретически может сломаться.
Но активный пайплайн исполняет только подмножество кода. Материальность = пересечение {найденные баги} ∩ {активный call graph}.

**Про RERUN_REQUIRED:**
Используй, только если баг мог изменить уже вычисленное значение (неверный знак, деление на ноль
при ненулевом знаменателе, накопленная ошибка). Если баг в display/logging — не нужен перезапуск.

**Про INCONCLUSIVE:**
Лучше честное INCONCLUSIVE с вопросом чем ложное NO_IMPACT. Спроси пользователя:
"Вызывается ли <функция> в вашем текущем запуске?" 

**Companion скилы — трёхуровневая защита:**
- `gate-check` — "execution success ≠ scientific verdict" (методология)
- `code-materiality` — "bug found ≠ current pipeline broken" (triage) ← этот скил
- `sci-code-audit` — "что ещё могли упустить?" (10-layer code hardening)

**Типичная цепочка:** внешний аудитор нашёл баги → `/code-materiality` (triage конкретных багов) → `/sci-code-audit` (проверяем 10 классов рисков которые могли не проверить).
