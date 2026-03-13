# Пример сессии: Code Review с Evidence Policy

Реальный пример: ревью перед мержем в main.

## Запрос пользователя

```
Сделай ревью feature/user-export перед мержем.
```

## Claude dispatch-ит reviewer agent

```
Dispatch: reviewer (Opus 4.6)
Context: git diff main...feature/user-export (14 файлов, 340 строк)
```

## Ответ reviewer-а

### Критичное (исправить обязательно)

**1. SQL injection в export query**
```python
# user_export.py:45
query = f"SELECT * FROM users WHERE department = '{dept}'"  # ОПАСНО
```

```
[VERIFIED] String concatenation в SQL (Read user_export.py:45)
[DOCS] OWASP Top 10 A03:2021 — Injection
```

**Фикс:**
```python
query = "SELECT * FROM users WHERE department = %s"
cursor.execute(query, (dept,))
```

**2. PII в логах**
```python
# user_export.py:67
logger.info(f"Exporting user: {user.email}, IIN: {user.iin}")
```

```
[VERIFIED] PII (email, ИИН) логируется plain text (Read user_export.py:67)
[CODE] rules/security.md запрещает PII в логах
```

**Фикс:**
```python
logger.info(f"Exporting user: id={user.id}")
```

### Важное (рекомендуется исправить)

**3. Нет пагинации**
```
[CODE] export_users() загружает всех пользователей в память (user_export.py:30)
[INFERRED] при 100k+ записей — OOM. Нужен cursor-based pagination.
[UNKNOWN] не проверял текущее количество пользователей в production.
```

### Положительное

```
[CODE] Type hints на всех public функциях — чисто.
[CODE] Pydantic validation на входном UserExportRequest — по стандарту.
[VERIFIED] 12/12 тестов проходят (pytest output).
```

## Итоговая таблица

| Категория | Кол-во | Статус |
|-----------|--------|--------|
| Критичное | 2 | SQL injection, PII в логах |
| Важное | 1 | Пагинация |
| Положительное | 3 | Types, validation, tests |

**Вердикт**: исправить 2 критичных → повторный ревью → мерж.

## Что показывает этот пример

1. **Evidence маркеры** — reviewer маркирует каждый finding
2. **2-stage review** — сначала security (критичное), потом quality (важное)
3. **Конкретные фиксы** — не абстрактные рекомендации, а код
4. **[UNKNOWN]** — честное «не знаю сколько записей в production»
5. **Положительное** — ревью отмечает что сделано хорошо, не только баги
