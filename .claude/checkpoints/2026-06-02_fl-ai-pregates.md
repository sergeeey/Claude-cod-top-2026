# Checkpoint — FL AI pre-gates renumbering

**Date:** 2026-06-02
**Branch:** feature/fl-ai-pregates
**Task:** add Steps -4/-3 (AI source trace + novelty) to FL, fix Step -2 number collision

## Changes
- `rules/falsification-ladder.md` only
- Renumbered pre-gates Step -3/-2 → Step -4/-3 (fixed Step -2 conflict with EstimandOps classify)
- Updated stack diagram, Full-Ladder table, Quick Reference
- Added 3 anti-patterns: source trace missing, pseudo-novelty, null_results repeat
- Added executable wrapper reference: `/ai-hyp-gate`

## Rollback
```bash
git reset --hard origin/main
git checkout main && git branch -D feature/fl-ai-pregates
```
