# Agent Gate Decision: datetime.utcnow() поиск

## Решение: НЕ запускать агента

**Агент избыточен.** Задача — поиск по паттерну + локальные правки. Это решается инструментами оркестратора напрямую.

---

## Результат Grep (0 токенов агента)

Найдено 4 вхождения в 4 файлах:

| Файл | Строка | Контекст |
|------|--------|----------|
| `.claude/worktrees/sharp-ride-906eac/skills/extensions/research-pipeline/pipeline.py` | 123 | `"timestamp": datetime.utcnow().isoformat() + "Z"` |
| `.claude/worktrees/sharp-ride-906eac/skills/extensions/research-pipeline/shared_state.py` | 127 | `ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")` |
| `.claude/worktrees/sharp-ride-906eac/tests/test_coverage_gap.py` | 247 | строковый литерал в тесте, не вызов функции |
| `tests/test_coverage_gap.py` | 247 | строковый литерал в тесте, не вызов функции |

---

## Анализ

**Реальные антипаттерны (2 файла):**
- `pipeline.py:123` — продакшн вызов, требует замены
- `shared_state.py:127` — продакшн вызов, требует замены

**Ложные срабатывания (2 файла):**
- `tests/test_coverage_gap.py:247` — строковый литерал `"[AVOID] never use datetime.utcnow()..."`, это тестовая строка-данные, НЕ вызов функции. Трогать не нужно — это именно документация [AVOID] паттерна.

---

## План замен (2 файла)

### pipeline.py:123
```python
# БЫЛО:
"timestamp": datetime.utcnow().isoformat() + "Z",

# СТАЛО:
"timestamp": datetime.now(timezone.utc).isoformat(),
```
Примечание: `.isoformat()` у timezone-aware объекта уже включает `+00:00`, поэтому `+ "Z"` убирается. Если нужен именно формат с `Z` — использовать `.strftime("%Y-%m-%dT%H:%M:%S.%f")` + `"Z"`.

### shared_state.py:127
```python
# БЫЛО:
ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

# СТАЛО:
ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
```

В обоих файлах нужно добавить импорт `timezone` если его нет:
```python
from datetime import datetime, timezone
```

---

## Почему агент был бы расточительством

| Критерий | Grep (оркестратор) | Explorer агент |
|----------|-------------------|----------------|
| Время | < 1 сек | 30–60 сек |
| Токены | 0 | 2000–5000 |
| Точность | 100% (grep точный) | ~100% (тот же grep внутри) |
| Дополнительная ценность | нет | нет |

Агент добавляет ценность когда нужно: семантический анализ, кросс-файловые зависимости, решения по контексту. Здесь — механический поиск по точному паттерну. SNR = ELIMINATE (агент) / KEEP (прямой путь).

---

## Вердикт SNR

**ELIMINATE** — запуск Explorer агента для этой задачи.  
**KEEP** — Grep + Edit оркестратором напрямую.

Правило: если задачу можно сформулировать как `grep "паттерн" --include="*.py"` — агент не нужен.
