# Session Example: Code Review with Evidence Policy

A real-world example: review before merging to main.

## User Request

```
Review feature/user-export before merging.
```

## Claude dispatches the reviewer agent

```
Dispatch: reviewer (Opus 4.6)
Context: git diff main...feature/user-export (14 files, 340 lines)
```

## Reviewer response

### Critical (must fix)

**1. SQL injection in export query**
```python
# user_export.py:45
query = f"SELECT * FROM users WHERE department = '{dept}'"  # DANGEROUS
```

```
[VERIFIED] String concatenation in SQL (Read user_export.py:45)
[DOCS] OWASP Top 10 A03:2021 — Injection
```

**Fix:**
```python
query = "SELECT * FROM users WHERE department = %s"
cursor.execute(query, (dept,))
```

**2. PII in logs**
```python
# user_export.py:67
logger.info(f"Exporting user: {user.email}, ID: {user.national_id}")
```

```
[VERIFIED] PII (email, national ID) logged as plain text (Read user_export.py:67)
[CODE] rules/security.md prohibits PII in logs
```

**Fix:**
```python
logger.info(f"Exporting user: id={user.id}")
```

### Important (recommended to fix)

**3. No pagination**
```
[CODE] export_users() loads all users into memory (user_export.py:30)
[INFERRED] with 100k+ records — OOM. Cursor-based pagination required.
[UNKNOWN] did not check current number of users in production.
```

### Positive

```
[CODE] Type hints on all public functions — clean.
[CODE] Pydantic validation on input UserExportRequest — per standard.
[VERIFIED] 12/12 tests pass (pytest output).
```

## Summary table

| Category | Count | Status |
|----------|-------|--------|
| Critical | 2 | SQL injection, PII in logs |
| Important | 1 | Pagination |
| Positive | 3 | Types, validation, tests |

**Verdict**: fix 2 critical issues → re-review → merge.

## What this example demonstrates

1. **Evidence markers** — reviewer marks each finding
2. **2-stage review** — security first (critical), then quality (important)
3. **Concrete fixes** — not abstract recommendations, but actual code
4. **[UNKNOWN]** — honest "I don't know how many records are in production"
5. **Positive** — review notes what was done well, not only bugs
