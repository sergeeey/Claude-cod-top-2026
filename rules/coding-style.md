---
# Path-scoped: this rule is only relevant when touching source code. It is FILE-triggered
# (activates on editing code), not keyword-triggered — so scoping it is safe (unlike the
# research/evidence rules, which must stay always-on because a conversation can invoke them
# without any file edit). Native Claude Code honours `paths:`; where rules load by CLAUDE.md
# reference instead, the same scope is annotated in claude-md/CLAUDE.md's RULES section.
paths:
  - "**/*.py"
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
  - "**/*.go"
  - "**/*.rs"
---

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
