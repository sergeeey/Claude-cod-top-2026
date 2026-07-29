# Research Methodology — Dual-Loop Engine (Раскрытие ⇅ Перепроверка)

**Назначение:** связать разрозненные research-правила в ОДИН сбалансированный цикл.
Без этого документа методология перекошена в скепсис: аудит/фальсификация проработаны,
а раскрытие гипотез — нет. Это ведёт к over-killing (убиваем хорошие гипотезы рано).

**Главный принцип:** исследование = два симметричных контура под управлением арбитра.
Баланс — НЕ фиксированная точка, а **функция стадии исследования**.

```
Stack position:
  research-methodology.md (этот файл)   ← "ЧТО делать сейчас: раскрывать или перепроверять?"
       ↓ арбитр выбирает контур по стадии
  ┌─────────────────────────┬──────────────────────────┐
  Дивергентный контур        Конвергентный контур
  (estimand-ops, FL Micro,   (audit-verification-gate,
   pearl, CDT, cross-domain)  FL Full, perelman, skeptic)
       ↓
  integrity.md / evidence policy   ← "маркеры корректны?"
       ↓
  hooks / CI / tests               ← "код работает?"
```

---

## Два контура

### Дивергентный контур — РАСКРЫТИЕ (цель: НЕ УПУСТИТЬ)

Назначение: из одной гипотезы развернуть пространство возможностей, найти максимум
testable-направлений при минимуме затрат. Доминирует на ранних стадиях.

| Шаг | Действие | Инструмент |
|-----|----------|-----------|
| D1 | Сформулировать пространство вариантов вокруг гипотезы (не одну формулировку) | `estimand-ops.md` L0, FL Micro |
| D2 | Параметрический скан: что при расширении диапазона? где границы? | **gap #3** (пока вручную; см. ниже) |
| D3 | Окна возможностей: что закрыто (сужает) / что открыто (новый вопрос) | FL § Kill Analysis, `cross_domain_insights.md` |
| D4 | Для каждого открытого вопроса → falsifiable prediction + **cheapest differentiating test** | FL § Cheapest Differentiating Test Protocol |
| D5 | Неожиданный testable инсайт → зафиксировать | FL § Pearl Registry, `pearl_registry/INDEX.md` |

**Правило дивергентного контура:** NULL-результат из скана так же ценен, как PROMOTE —
он закрывает механизм и сужает пространство. «Ничего не работает в зоне X» = знание.

### Конвергентный контур — ПЕРЕПРОВЕРКА (цель: НЕ ОБМАНУТЬСЯ)

Назначение: атаковать готовый claim честно, поймать validation theater, не дать
устаревшему PROMOTE пережить новый NULL. Доминирует на стадии промоушена.

| Шаг | Действие | Инструмент |
|-----|----------|-----------|
| C1 | Асимметричный аудит: скептик получает claim+код, БЕЗ reasoning chain | `falsification-ladder.md` § Context Asymmetry, `audit-verification-gate.md` |
| C2 | Маркировка: VERIFIED-tool / HYPOTHESIS / DISMISSED; scope = scope | `audit-verification-gate.md`, CLAUDE.md Claim Scope Discipline |
| C3 | Классификация ошибок (4 типа, см. ниже) | этот файл § Классификатор |
| C4 | Promotion gate: 5 условий Perelman, claim_entropy=0 | `perelman-audit.md`, `promotion_gate_guard.py` |
| C4.5 | **NULL Exploitation Gate**: REJECT обязан содержать «что открывает» (Kill Analysis + Relaxation Map непустые) | ✅ `reject_gate_guard.py` (enforced) |
| C5 | **NULL-ретроскан**: новый NULL → пройти ВСЕ активные PROMOTE на зависимость | ✅ `null_retroscan.py` (enforced) |

---

## Арбитр баланса (центр методологии)

Арбитр = **Research Stage Protocol** (CLAUDE.md). Баланс выбирается по стадии:

| Стадия | Доминирующий контур | Методология |
|--------|---------------------|-------------|
| **idea scouting** | Дивергентный (90/10) | FL Micro, Zero-Signal Gate. Скепсис минимален — только отсев нефальсифицируемого |
| **hypothesis shaping** | Сбалансированно (50/50) | estimand-ops L0 + FL Standard. Раскрываем И проверяем claim+controls |
| **claim promotion** | Конвергентный (10/90) | FL Full, perelman, skeptic Step 8a. Раскрытие почти выключено |
| **paper / release** | Конвергентный (5/95) | FL Full + cross-model + Submission Gate |

### Tie-breaker: SKEPTIC-LEANING ПО УМОЛЧАНИЮ

**Когда стадия неясна или спорна → доминирует конвергентный контур.**

Обоснование: исторический риск пользователя — validation theater (ТОП-10 2026-05-01,
ARCHCODE). Цена ложного PROMOTE (месяцы на ложном следе, retraction) >> цены позднего
раскрытия хорошей гипотезы (она подождёт). Поэтому при сомнении — перепроверять.

**НО** (anti-over-killing guard): прежде чем убить гипотезу скепсисом на ранней стадии —
проверь, не находишься ли ты в idea scouting. Дивергентный контур имеет право на
«слабые но testable» идеи (маркер `[SPECULATIVE]`/`[CANDIDATE]`), пока они не претендуют
на PROMOTE. Skeptic-leaning блокирует ПРОДВИЖЕНИЕ, не ГЕНЕРАЦИЮ.

```
Неясна стадия?
  ├── claim претендует на PROMOTE/публикацию? → конвергентный, полный скепсис
  └── это scouting/кандидат с маркером [SPECULATIVE]? → дивергентный разрешён,
        но БЕЗ повышения статуса до прохождения gate
```

---

## Классификатор источников ошибок (4 типа)

После аудита каждую найденную проблему разобрать по типу. Каждый тип → правило защиты.

| Тип | Описание | Защита | Статус механизма |
|-----|----------|--------|------------------|
| **1. Символьная перегрузка** | один символ = два объекта в разных частях | реестр параметров: перед использованием символа — проверка что не занят | **gap #2** (вручную) |
| **2. FITTED vs DERIVED** | параметр подобран обратно, подаётся как выведенный | явная метка статуса параметра (выведен/подобран/предположен) | ✅ CLAUDE.md Claim Scope Discipline + estimand-ops |
| **3. Условие без условия** | результат верен при X, но X нигде не написан | формат «Если P, то X следует без доп. параметров» | ✅ claim.md § Counterfactual Frame + caveats |
| **4. Лаг обновления** | новый NULL не применён к старым PROMOTE | NULL-ретроскан + Exploitation Gate | ✅ `null_retroscan.py` + `reject_gate_guard.py` (enforced) |

---

## Self-Fix Loop Hardening (enforced gates на FIX-петле)

Помимо research-контуров, FIX-петля (builder↔reviewer) защищена enforced-хуками.
Gap-audit 2026-06-24 показал: из 8 предложенных хуков 5 уже существовали
(`goal_stub_detector`, `pre_commit_guard`, `validation_theater_guard`,
`subagent_verify`, `skeptic_auto_trigger`). Достроены 3:

| Хук | Что enforce | Событие |
|-----|-------------|---------|
| `weakened_test_guard.py` | тест ослаблен ради прохождения (drop assert / skip / `assert True`) | PostToolUse(Edit) на тесты |
| `commit_test_gate.py` | код изменён после последнего прогона тестов → коммит непроверенного | Pre/PostToolUse(Bash/Edit) |
| `iteration_guard.py` | Evaluator-Optimizer cap=3 (≥3 non-LGTM подряд → escalate) | SubagentStop |

Все soft-nudge (additionalContext, не блокируют), симметрично promotion/reject gates.
**Принцип:** PROMOTE, REJECT и FIX-петля теперь имеют enforced-гейты — раньше на доверии был только FIX.

---

## Сквозные принципы (через оба контура)

1. **Compute first** — перед «спросить эксперта» сделать 5-мин численную проверку (CLAUDE.md PVF). Многие вопросы закрываются сразу.
2. **NULL = прогресс** — известное «не работает» > неизвестного «может работает». Серия NULL → теорема через исчерпание.
3. **Честная терминология** — каждое утверждение несёт свои условия; каждый параметр — свой статус. (`integrity.md` evidence markers)
4. **Асимметрия контекста** — рецензент без истории рассуждений найдёт то, что рецензент с историей оправдает. (`falsification-ladder.md` § Context Asymmetry)
5. **Немедленный ретроскан** — новый результат, меняющий предположения, применяется ко всем существующим claims СРАЗУ, не откладывается.
6. **Деградация гипотез** — после числового совпадения спроси: сколько формул дают то же число? Если несколько → нужна ДРУГАЯ конфигурация параметров чтобы различить. (`hypothesis-arbiter`)

---

## Карта: фаза методологии → где живёт

| Фаза твоей методологии | Контур | Артефакт в системе |
|------------------------|--------|--------------------|
| 1. Аудит с асимметрией | C | `audit-verification-gate.md`, FL § Context Asymmetry, agent `skeptic`/`codex-skeptic` |
| 2. Классификация ошибок | C | этот файл § Классификатор (типы 2,3 ✅; 1,4 — gap) |
| 3. Система предотвращения | C | `integrity.md` Submission Gate, `promotion_gate_guard.py`, claim.md |
| 4. Окна из ошибок | D | FL § Pearl Registry + Kill Analysis + CDT, `cross_domain_insights.md` |
| 5. Параметрический скан | D | принцип в FL/cross-domain; executor — gap #3 |
| 6. Размерный анализ + деградация | D | `hypothesis-arbiter`, Buckingham Pi (применялось); checker — частичный gap |

---

## Gap-статус

**✅ gap #1 — ЗАКРЫТ (2026-06-24).** NULL Exploitation Gate + ретроскан реализованы:
- `reject_gate_guard.py` — PostToolUse на decision.md; блокирует* REJECT с пустым
  Kill Analysis / Relaxation Map / расплывчатой причиной. (*soft nudge через additionalContext)
- `null_retroscan.py` — PostToolUse на null_results/INDEX.md; новый NULL → скан активных
  PROMOTE на token-overlap ≥2 → предупреждение.
- 47 тестов, ruff clean. Симметрично `promotion_gate_guard.py`.

**gap #2 — Реестр параметров/символов** (Тип 1, приоритет 2).
Ручной протокол: `experiments/<id>/symbols.md` — таблица `символ | значение | где определён`.
Перед вводом нового символа — grep по таблице.
Автоматизация: symbol-overload checker.

**gap #3 — Параметрический скан как executor** (Фаза 5, приоритет 3).
Ручной протокол: скан вокруг рабочего значения, NULL-зоны фиксировать наравне с PROMOTE.
Автоматизация: лучше через `Workflow` tool (детерминированный sweep), не отдельный скилл.

---

## Anti-patterns

| Антипаттерн | Почему опасно | Контур |
|-------------|---------------|--------|
| Скепсис на стадии scouting | Убиваешь хорошие гипотезы до раскрытия (over-killing) | D задавлен C |
| Раскрытие без gate на promotion | Validation theater проходит в публикацию | C задавлен D |
| Один контур всегда | Методология вырождается: либо гора непроверяемого, либо ноль новизны | арбитр выключен |
| NULL не применён ретроактивно | Цепочка claims устаревает молча (Тип 4) | принцип 5 нарушен |
| Числовое совпадение без degeneracy-проверки | Несколько формул дают то же число — ложная уверенность | принцип 6 нарушен |
| Стадия не названа явно | Арбитр не может выбрать контур → дефолт skeptic, но это не всегда верно | арбитр |

---

## Quick Reference

```
Новая гипотеза/результат?
├── Назови стадию (scouting / shaping / promotion / release)
│     └── неясна? → SKEPTIC-LEANING: конвергентный контур, но не блокируй [SPECULATIVE]-генерацию
├── Стадия → арбитр выбирает контур (таблица выше)
│
├── ДИВЕРГЕНТНЫЙ (раскрытие): варианты → скан → окна → cheapest differentiating test → pearl
├── КОНВЕРГЕНТНЫЙ (перепроверка): асимм. аудит → маркеры → классификатор → promotion gate → NULL-ретроскан
│
├── Ошибку нашёл? → классифицируй (4 типа) → применишь защиту
└── Новый NULL? → ретроскан ВСЕХ активных PROMOTE СРАЗУ (принцип 5)
```

**Last updated:** 2026-06-24
**Status:** ACTIVE — связывает estimand-ops + falsification-ladder + audit-verification-gate + perelman-audit
**Balance default:** skeptic-leaning при неясной стадии (блокирует promotion, не generation)
**Open gaps:** ✅ #1 null-retroscan + exploitation gate (DONE 2026-06-24) · #2 symbol registry (P2) · #3 parametric scan executor (P3)
