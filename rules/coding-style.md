# Coding Style Rules

## Backend (Python)
- Python 3.11+, type hints always
- ruff format (double quotes, 100 chars), structlog instead of print()
- Commits: feat/fix/docs/refactor/test
- PII (national IDs, card numbers, account numbers) → never in logs as plain text
- Secrets → env vars only, never in code
- SQL → parameterized queries only
- Input data → Pydantic validation before processing

## Frontend (React/TS)
- React + TypeScript (strict, no `any`)
- Zustand for state management, Tailwind for styles
- Functional components only, PascalCase naming

## Comments
- `# WHY:` before non-trivial decisions
- On errors: "The bug was in X because Y, fixed by Z"
- On choices: "Chose A over B because X matters more for our case"
