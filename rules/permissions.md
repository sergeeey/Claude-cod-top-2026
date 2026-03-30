# Permissions System

## Permission Layers (evaluation order)
1. **PermissionRequest hook** (`permission_policy.py`) — programmatic auto-allow/deny/ask
2. **Static deny list** (`settings.json`) — 27 blocked patterns (hard block)
3. **Static allow list** (`settings.json`) — 11 tool categories
4. **User prompt** — everything not covered by above

## Auto-Approved (no user prompt needed)
- Read, Glob, Grep — read-only, always safe
- Task* — internal task management
- WebSearch, WebFetch — information gathering
- Bash: git status/log/diff/show, pytest, ruff, mypy, ls, pwd, cat, head, tail

## Auto-Denied (blocked with message)
- rm -rf, format, --delete-all
- git push --force, git reset --hard, git clean -fd, git branch -D
- DROP TABLE, DROP DATABASE, TRUNCATE TABLE
- chmod 777, npm publish, curl|bash, wget|bash
- docker rm, kubectl delete
- Edit test files (*.test.py, *.test.ts, *.spec.ts)
- Write to .env*, secrets/**

## Compound Command Splitting
When approving `git add . && git commit -m "msg"`, Claude Code saves TWO rules:
- `Bash(git add .)`
- `Bash(git commit -m "msg")`
Up to 5 rules generated from one compound approval.

## Glob Pattern Syntax
- `*` matches any characters within one directory
- `**` matches across nested directories
- `Edit(src/**/*.test.ts)` — matches all test files recursively
- `Write(.env*)` — matches .env, .env.local, .env.production
