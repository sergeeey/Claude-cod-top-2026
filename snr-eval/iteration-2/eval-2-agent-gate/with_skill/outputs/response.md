# SNR Agent Gate: datetime.utcnow() search

## Применён режим: Правило очевидного случая

> **[ОЧЕВИДНО] Используй Grep, не агента. Причина: Grep дал полный ответ за 1 секунду и 0 токенов. Формула не нужна.**

---

## Аргументация по чеклисту Agent Gate (30 сек)

| Вопрос | Ответ |
|---|---|
| Нельзя решить прямым Grep/Bash? | **Нет** — `Grep("datetime\.utcnow\(\)", path, type="py")` решает задачу мгновенно |
| Нужен изолированный контекст? | **Нет** — это read-only поиск, контекст агента не нужен |
| Выход войдёт в решение, а не в архив? | Да, но выход уже получен без агента |
| Смогу верифицировать вывод за < 2 мин? | Уже верифицировано — результат прямо здесь |
| Действие необратимо или затрагивает prod? | Нет — поиск, не изменение |

**Вывод по чеклисту:** все 4 пункта против запуска агента. Explorer — лишний слой.

---

## Результат (получен Grep, не агентом)

**Итого: 4 файла, 4 вхождения**

| Файл | Строка | Контекст |
|---|---|---|
| `tests/test_coverage_gap.py:247` | `"[AVOID] never use datetime.utcnow() — use timezone-aware\n[REPEAT] always use UTC"` | Строковая константа в тесте — не реальный вызов |
| `.claude/worktrees/sharp-ride-906eac/tests/test_coverage_gap.py:247` | То же самое | Дубль в worktree |
| `.claude/worktrees/sharp-ride-906eac/skills/extensions/research-pipeline/pipeline.py:123` | `"timestamp": datetime.utcnow().isoformat() + "Z"` | **Реальный вызов** — требует исправления |
| `.claude/worktrees/sharp-ride-906eac/skills/extensions/research-pipeline/shared_state.py:127` | `ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")` | **Реальный вызов** — требует исправления |

### Классификация:
- **2 файла** — строковая константа в тестах (упоминание паттерна, не использование): исправление не нужно
- **2 файла** — реальные вызовы `datetime.utcnow()` в worktree: следует заменить на `datetime.now(timezone.utc)`
- **В основной кодовой базе** (вне `.claude/worktrees/`) реальных вызовов **нет**

---

## Что нужно исправить

```python
# Было (deprecated в Python 3.12):
datetime.utcnow().isoformat() + "Z"
datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

# Надо:
from datetime import datetime, timezone
datetime.now(timezone.utc).isoformat()
datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
```

Файлы в worktree `sharp-ride-906eac` — проверить, актуален ли этот worktree или уже архивный.

---

## Итог по SNR

Запуск Explorer-агента для поиска паттерна — это **шум**:
- Explorer занял бы 30–120 сек, потратил бы 500–2000 токенов на контекст
- Grep дал тот же результат за ~1 сек, 0 токенов агентного контекста
- "Агент не должен производить новый шум быстрее, чем человек успевает его верифицировать" (SNR Skill)

**Решение:** использовать Grep. Агент — не нужен.
