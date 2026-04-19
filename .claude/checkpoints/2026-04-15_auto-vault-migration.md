# Checkpoint: auto-vault path migration + cogniml idempotency

**Date:** 2026-04-15
**Branch:** feat/auto-vault-paths-cogniml-idempotency
**Base commit:** 94dac65 (main, v3.7.0)
**Tests:** 862 passed

## Current Task
Committing 17 locally-modified files as PR #69.

## Key Changes Staged
- hooks/utils.py: restored hook_main + log_hook_timing (were accidentally deleted)
- hooks/cogniml_client.py: idempotency guard + _PUSHED_LEDGER constant
- hooks/knowledge_librarian.py: preserve original case in wikilinks; _top_avoid_patterns()
- hooks/session_save.py: upsert behavior (no _N suffix)
- hooks/*: _auto/ vault path migration across all hooks
- tests/: TestPushWikiEntry cache fix; collision→upsert test update

## Rollback
```bash
git checkout main
git branch -D feat/auto-vault-paths-cogniml-idempotency
```
