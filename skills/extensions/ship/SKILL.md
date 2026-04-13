---
name: ship
description: >
  USE when ready to release: bump version, update CHANGELOG, create PR.
  ALWAYS run tests first, then version bump, then PR.
  Triggers: /ship, ship:, готов к релизу, release, bump version, create PR.
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-04-13]
effort: medium
tokens: ~600
---

# /ship — Release Workflow

## When to Use

Ready to merge a feature branch to main. Automates the mechanical release steps:
tests → version bump → CHANGELOG entry → commit → PR.

## Pre-conditions

- You are on a feature branch (NOT main/master)
- All changes are committed
- Tests pass locally

## Workflow

### Step 1 — Verify branch

```bash
git branch --show-current
git status
```

Must be on a feature branch. If on main → STOP, tell user to create branch first.

### Step 2 — Run tests

```bash
pytest tests/ -x -q 2>&1 | tail -20
```

If tests fail → STOP. Report failures. Do NOT proceed to version bump.

### Step 3 — Determine version bump

Ask user (or infer from commits):
- `patch` (x.x.X) — bug fixes, docs, chores
- `minor` (x.X.0) — new features, additive changes
- `major` (X.0.0) — breaking changes

Read current version from `activeContext.md` → `## Project State` → `**Version:**`.

### Step 4 — Bump version in activeContext.md

```bash
grep -n "Version:" .claude/memory/activeContext.md | head -3
```

Update `**Version:** X.Y.Z` → new version.

### Step 5 — Update CHANGELOG.md

Add new entry at the top (after the `# Changelog` header):

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- ...

### Fixed
- ...
```

Populate from `git log --oneline origin/main..HEAD` — actual commits only, [VERIFIED].

### Step 6 — Commit version bump

```bash
git add .claude/memory/activeContext.md CHANGELOG.md
git commit -m "chore: bump version to X.Y.Z"
```

### Step 7 — Create PR

```bash
gh pr create \
  --title "feat: <branch description>" \
  --body "$(cat <<'EOF'
## Summary
- <bullet 1>
- <bullet 2>

## Version
X.Y.Z (patch/minor/major bump)

## Test plan
- [ ] pytest passes
- [ ] ruff check passes
- [ ] CI green

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

## Gotchas

- NEVER bump version on main — branch must exist
- NEVER fabricate commits in CHANGELOG — use `git log` [VERIFIED]
- If CHANGELOG.md does not exist → create it with `# Changelog\n\n` header first
- Version in activeContext.md is the source of truth for this project
- Do not commit to main directly — branch required

## Integration

After `/ship`:
- CI runs automatically (GitHub Actions)
- Merge PR → triggers `pattern_extractor.py` on any `fix:` commits
- Update `activeContext.md ## Current Focus` with next task
