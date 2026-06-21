# SNR Agent Gate — Оценка задачи datetime.utcnow()

**Дата:** 2026-05-15  
**Режим:** Agent Gate (Режим 5)  
**Задача:** Найти все `datetime.utcnow()` в кодовой базе, составить план замен, сделать замены.

---

## Шаг 0: Прямая проверка до оценки агента

Перед тем как решать "запускать агента или нет", сделал одно действие:

```
Grep(pattern="datetime\.utcnow\(\)", path="D:/Claude-cod-top-2026", type="py")
```

**Результат (полный, за 2 секунды):**

| Файл | Строка | Содержимое |
|------|--------|------------|
| `tests/test_coverage_gap.py:247` | строковый литерал | `"[AVOID] never use datetime.utcnow()..."` — это тест-строка, не использование паттерна |
| `.claude/worktrees/sharp-ride-906eac/tests/test_coverage_gap.py:247` | то же | worktree-копия того же файла |
| `.claude/worktrees/sharp-ride-906eac/skills/extensions/research-pipeline/shared_state.py:127` | реальное использование | `datetime.utcnow().strftime(...)` |
| `.claude/worktrees/sharp-ride-906eac/skills/extensions/research-pipeline/pipeline.py:123` | реальное использование | `datetime.utcnow().isoformat() + "Z"` |

**Итог разведки:** 2 реальных файла с паттерном (оба в одном worktree), 2 строковых литерала (не код).

---

## Agent Gate Чеклист (Режим 5)

| Вопрос | Ответ | Вывод |
|---|---|---|
| Нельзя решить прямым Read/Grep/Bash? | **НЕТ — уже решено Grep за 2 сек** | Не запускать агента |
| Нужен реально изолированный контекст? | Нет | Не запускать агента |
| Выход агента войдёт в решение, а не в архив? | Частично | — |
| Я смогу верифицировать вывод за < 2 мин? | Да, но вывод уже есть | — |
| Действие необратимо или затрагивает prod? | Правки кода — обратимы через git | — |

**Первый вопрос — жёсткий блокер.** Grep уже дал полный ответ. Агент не нужен.

---

## SNR-оценка запуска агента Explorer

```
Signal Value:
- Impact:       2  (два файла, косметическая правка, не блокирует фичи)
- Compounding:  1  (разовая задача, не накапливается)
- Leverage:     1  (не открывает новых решений)
- Reusability:  1  (результат одноразовый)
- Confidence:   5  (данные точные, паттерн известен)

Signal = 2 × 1 × 1 × 1 × 5 = 10

Noise Cost:
- Time:          3  (агент: ~5-10 мин vs Grep: 2 сек)
- Fragmentation: 3  (ожидание агента, переключение контекста)
- Coordination:  2  (передача контекста агенту, верификация вывода)
- Rework:        1  (малый риск переделки)
- Governance:    1  (нет особых разрешений)

Noise = 3 + 3 + 2 + 1 + 1 = 10

SNR = 10 / 10 = 1.0
```

**Решение: ELIMINATE** — агент убит формулой. SNR < 2.

---

## Прямой путь (без агента)

### Шаг 1 — Поиск (ГОТОВО)
```bash
Grep("datetime\.utcnow\(\)", "D:/Claude-cod-top-2026", type=py)
```
Результат: 2 файла для правки, 2 строковых литерала — трогать не нужно.

### Шаг 2 — Замены (2 файла, 2 строки)

**Файл 1:** `.claude/worktrees/sharp-ride-906eac/skills/extensions/research-pipeline/shared_state.py:127`
```python
# ДО:
ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

# ПОСЛЕ:
from datetime import timezone
ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
```

**Файл 2:** `.claude/worktrees/sharp-ride-906eac/skills/extensions/research-pipeline/pipeline.py:123`
```python
# ДО:
"timestamp": datetime.utcnow().isoformat() + "Z",

# ПОСЛЕ:
from datetime import timezone
"timestamp": datetime.now(timezone.utc).isoformat(),
# Примечание: .isoformat() на aware datetime включает +00:00, суффикс "Z" не нужен
```

### Шаг 3 — Верификация
```bash
Grep("datetime\.utcnow\(\)", "D:/Claude-cod-top-2026", type=py)
# Ожидаем: только строковые литералы в test_coverage_gap.py (они правильно остаются)
```

---

## Вердикт

**ELIMINATE агента. SIMPLIFY задачу до 3 шагов.**

| | Агент Explorer | Прямой путь |
|---|---|---|
| Время | 5-10 мин | 3 мин |
| Файлов изменено | 2 | 2 |
| Риск ошибки агента | есть (plan + делает) | минимальный (человек контролирует) |
| Верификация вывода | требуется | тривиальна |

**Правило OpenAI (из SNR skill):** "Сначала выжать максимум из single-agent + tools. Multi-agent — только при реальной необходимости."

Здесь single-tool (Grep) дал полный ответ. Агент — это overengineering.

---

## Что делать прямо сейчас

1. Открыть `shared_state.py:127` — заменить 1 строку
2. Открыть `pipeline.py:123` — заменить 1 строку + добавить импорт  
3. Запустить Grep — убедиться что реальных вхождений не осталось
4. Commit: `fix: replace datetime.utcnow() with timezone-aware datetime.now(timezone.utc)`

Итого: ~3 минуты, 0 агентов.
