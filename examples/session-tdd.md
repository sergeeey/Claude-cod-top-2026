# Пример сессии: TDD Workflow

Реальный пример работы с tdd-workflow skill — добавление JWT-авторизации.

## Запрос пользователя

```
Добавь JWT-авторизацию в auth модуль с тестами.
```

## Шаг 1: RED — Claude пишет тесты

Claude автоматически подхватывает `tdd-workflow` skill (триггер: «с тестами»).

```python
# tests/unit/test_auth.py
import pytest
from auth.jwt_handler import create_token, verify_token, TokenExpiredError

def test_create_token_returns_valid_jwt():
    token = create_token(user_id=42, role="admin")
    assert isinstance(token, str)
    assert len(token.split(".")) == 3  # header.payload.signature

def test_verify_token_returns_payload():
    token = create_token(user_id=42, role="admin")
    payload = verify_token(token)
    assert payload["user_id"] == 42
    assert payload["role"] == "admin"

def test_verify_expired_token_raises():
    token = create_token(user_id=1, role="user", expires_in=-1)
    with pytest.raises(TokenExpiredError):
        verify_token(token)

def test_verify_invalid_token_raises():
    with pytest.raises(ValueError):
        verify_token("not.a.valid.token")
```

## Шаг 2: RED — Тесты падают

```
$ pytest tests/unit/test_auth.py -x -q --tb=short
ERRORS: ModuleNotFoundError: No module named 'auth.jwt_handler'
4 errors in 0.12s
```

Claude подтверждает: **все 4 теста падают** (модуль ещё не существует). RED подтверждён.

## Шаг 3: RED — Коммит тестов

```
$ git add tests/unit/test_auth.py
$ git commit -m "test: add failing tests for JWT auth"
```

## Шаг 4: GREEN — Минимальная реализация

```python
# auth/jwt_handler.py
import jwt
import time
from typing import Any

SECRET = os.environ["JWT_SECRET"]  # [CODE] из .env, не hardcoded

class TokenExpiredError(Exception):
    pass

def create_token(user_id: int, role: str, expires_in: int = 3600) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": int(time.time()) + expires_in,
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def verify_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Token expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")
```

## Шаг 5: GREEN — Все тесты проходят

```
$ pytest tests/unit/test_auth.py -x -q --tb=short
4 passed in 0.08s
```

Claude dispatch-ит reviewer subagent:
> [VERIFIED] 4/4 тестов проходят (pytest output).
> Реализация не hardcoded — использует jwt.encode/decode.
> Edge cases покрыты: expired token, invalid token.

## Шаг 6: REFACTOR + Коммит

```
$ git add auth/jwt_handler.py
$ git commit -m "feat: implement JWT auth (create_token, verify_token)"
```

## Evidence маркеры в ответе Claude

```
[VERIFIED] 4/4 тестов проходят (pytest -x -q output)
[CODE] SECRET загружается из os.environ["JWT_SECRET"] (jwt_handler.py:5)
[INFERRED] HS256 достаточен для внутреннего API (из контекста проекта — не public-facing)
[UNKNOWN] не проверял rate limiting на verify_token — может понадобиться для production
```
