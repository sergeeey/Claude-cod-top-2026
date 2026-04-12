# Checkpoint: 2026-04-12 — before plugin manifest

## Branch
feat/plugin-manifest (from main @ d5d3033)

## State
- main: d5d3033 (v3.6.0, 827 tests, PRs: #57 #58 #59 merged)
- Open PRs: #60 feat/statusline-rate-limits

## Task
Adding .claude-plugin/plugin.json + marketplace.json to publish repo as official Claude Code plugin.
Replaces install.sh with: /plugin marketplace add sergeeey/Claude-cod-top-2026 + /plugin install claude-cod-top-2026

## Rollback
git checkout main && git branch -D feat/plugin-manifest
No existing files modified — only 2 new files added.
