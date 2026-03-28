---
name: tdd-workflow
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-13]
  ALWAYS USE when writing new features, fixing bugs, or adding functionality.
  MUST USE when user mentions: tests, test, TDD, coverage, red-green,
  write tests, cover with tests, add with tests, fix with tests.
  ESPECIALLY when tempted to write code before tests.
---

# TDD Workflow — Test-Driven Development

## Iron Law

**NOT A SINGLE LINE OF PRODUCTION CODE WITHOUT A FAILING TEST.**

Order is always: RED → GREEN → REFACTOR. No exceptions.

## 6-Step Process

### Step 1: RED — Write Tests
Write tests based on requirements, NOT on implementation.
- One test = one behavior
- Clear names: `test_user_login_returns_token_on_valid_credentials`
- Real data, mock only when unavoidable (DB, external API)
- Do not write implementation. Tests only.

### Step 2: RED — Confirm Tests Fail
Run the tests. Confirm that EVERY new test FAILS.
```bash
pytest tests/unit/module_name/ -x -q --tb=short
```

**Critical:** if tests pass before writing code — they are useless.
That means: they test the wrong thing, or they test already existing behavior.

If a test passed → delete it and write a correct test that checks
NEW behavior.

### Step 3: RED — Commit Tests Separately
```bash
git add tests/...
git commit -m "test: add failing tests for <feature>"
```
A separate commit creates clean history: contract (tests) first, then implementation.

### Step 4: GREEN — Write Minimal Implementation
Write MINIMAL code to make all tests green.
- Do not add functionality beyond what the tests require
- **FORBIDDEN to modify tests in this step**
- If a test seems wrong — stop, discuss with user

### Step 5: GREEN — Verification
Run all tests (not just the new ones):
```bash
pytest tests/ -x -q --tb=short
```

If something broke — fix the implementation, NOT the tests.

Dispatch reviewer subagent to check:
- Implementation is not hardcoded to specific test values?
- Edge cases covered?
- No workarounds instead of a real solution?

### Step 6: REFACTOR — Improve While Staying Green
Refactor ONLY with green tests:
- Remove duplication
- Improve naming
- Simplify logic
- Run tests after EVERY change

Commit:
```bash
git add src/... tests/...
git commit -m "feat: implement <feature>"
```

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "Tests are too simple for this function" | Write at least happy path + one edge case. Simple tests catch simple bugs. 30 seconds of work. |
| "I already know the implementation, let's do code first" | No. RED → GREEN → REFACTOR. Tests first, always. Knowing the implementation does not cancel the process. |
| "This module is hard to test" | Hard to test = signal of poor design. Refactor the module, then test. |
| "Just this once without tests, I'll add them later" | "Later" never comes. Tests written after code are fitted to implementation, not requirements. |
| "This is just config/utility, no tests needed" | Config breaks production more often than business logic. One validation test = insurance. |
| "Tests slow down development" | Tests slow down CODE WRITING by 20%. Debugging without tests — by 300%. |
| "I'll write integration tests later" | Unit tests and integration tests are different things. Unit now, integration later. |

## Exceptions (require explicit user confirmation)

- Throwaway prototype (user explicitly said "no tests, prototype")
- Generated code (migrations, protobuf, OpenAPI stubs)
- Configuration files (CI/CD, Docker, package.json)
- Documentation

## Red Flags — STOP if noticed

- "I'll skip TDD just this once" → No. Follow the process.
- "I'll write tests after" → No. RED first.
- "Tests after code give the same result" → No. Tests after code test implementation, not requirements.
- Test passes BEFORE writing code → Test is useless. Rewrite it.
- Modifying test to make it pass → FORBIDDEN. Fix code, not tests.

## Relationship with rules/testing.md

This skill extends the base rules from `@~/.claude/rules/testing.md`:
- testing.md sets CONSTRAINTS (do not delete tests, coverage 80%+)
- tdd-workflow sets PROCESS (RED → GREEN → REFACTOR)
- They complement each other, not conflict

## Gotchas
- Write tests BEFORE implementation — tests after code test implementation, not requirements
- Never weaken a test to make it pass — fix the code, not the test
