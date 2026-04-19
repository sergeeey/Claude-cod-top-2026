# Checkpoint 2026-04-19 — Wave 1 + Wave 2 Complete

## State
- **Branch:** main `6855651`
- **Tests:** 978 passed, 0 failed
- **Coverage:** ~81% (CI threshold: 75%)
- **Open PRs:** 0

## What was done

### PR #75 — fix/ci-green-972-tests
- 4 failing tests fixed (stdlib allowlist, YAML frontmatter, tdd-workflow, routing-policy)
- README badges synced: 907→972 tests, 40→51 hooks
- vector_store: graceful try/except import
- obsidian-vault MCP added to mcp-profiles/core.json

### PR #76 — feat/obsidian-wave2
- session_save.py: glob→rglob for PARA-aware wikilinks
- 4 MOCs created: GeoMiro, AI-Era Engineering, Solo Founding, Security
- Dashboard.md: MOC links + Recent Wiki Dataview block
- .obsidian/graph.json: 6 color groups
- test_learning_hooks.py: 6 new tests for mentor_nudge.py (was 0%)
- ci.yml: fail-under 45%→75%

## Rollback
```bash
git revert 6855651  # или git reset --hard 487f96d (pre-wave2)
```

## Next
- Wave 3: vector_store.py implementation + canvas auto-generation
- install.sh на sboi (PENDING)
