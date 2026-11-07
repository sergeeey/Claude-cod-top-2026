# Permissions System

## Permission Layers (evaluation order)
1. **PermissionRequest hook** (`permission_policy.py`) — programmatic auto-allow/deny/ask
2. **Static deny list** (`settings.json`) — blocked patterns (hard block)
3. **Static allow list** (`settings.json`) — allowed tool categories
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
- Delete test files (`rm *test_*.py*`, `rm -rf tests`, `git rm *test_*.py*`)
- Write to .env*, secrets/**

Editing test files is NOT denied (owner decision 2026-09-02: no source/test
file-class denies). Weakening a test to force a pass is blocked instead by the
`weakened_test_guard` PreToolUse hook, which inspects the edit itself.

Note: the static allow list is `Bash(*)`, `Edit(*)`, `Write(*)` etc., so the
"Auto-Approved" list above is a floor, not the full set; only the deny list and
PreToolUse hooks restrict. "User prompt" is reached only for tools outside the
allow list.

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
