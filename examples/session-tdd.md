# Session Example: TDD Workflow

A real-world example using the tdd-workflow skill — adding JWT authorization.

## User Request

```
Add JWT authorization to the auth module with tests.
```

## Step 1: RED — Claude writes tests

Claude automatically picks up the `tdd-workflow` skill (trigger: "with tests").

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

## Step 2: RED — Tests fail

```
$ pytest tests/unit/test_auth.py -x -q --tb=short
ERRORS: ModuleNotFoundError: No module named 'auth.jwt_handler'
4 errors in 0.12s
```

Claude confirms: **all 4 tests fail** (module does not exist yet). RED confirmed.

## Step 3: RED — Commit tests

```
$ git add tests/unit/test_auth.py
$ git commit -m "test: add failing tests for JWT auth"
```

## Step 4: GREEN — Minimal implementation

```python
# auth/jwt_handler.py
import jwt
import time
from typing import Any

SECRET = os.environ["JWT_SECRET"]  # [CODE] from .env, not hardcoded

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

## Step 5: GREEN — All tests pass

```
$ pytest tests/unit/test_auth.py -x -q --tb=short
4 passed in 0.08s
```

Claude dispatches a reviewer subagent:
> [VERIFIED] 4/4 tests pass (pytest output).
> Implementation is not hardcoded — uses jwt.encode/decode.
> Edge cases covered: expired token, invalid token.

## Step 6: REFACTOR + Commit

```
$ git add auth/jwt_handler.py
$ git commit -m "feat: implement JWT auth (create_token, verify_token)"
```

## Evidence markers in Claude's response

```
[VERIFIED] 4/4 tests pass (pytest -x -q output)
[CODE] SECRET loaded from os.environ["JWT_SECRET"] (jwt_handler.py:5)
[INFERRED] HS256 is sufficient for internal API (from project context — not public-facing)
[UNKNOWN] did not check rate limiting on verify_token — may be needed for production
```
