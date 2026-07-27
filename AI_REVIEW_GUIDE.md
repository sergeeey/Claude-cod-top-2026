# AI Review Guide

You are evaluating this repository from scratch. This file is the canonical
starting point for any AI agent auditing this repo.

## What this repo is (one sentence)

A trust layer for Claude Code agents: evidence gates, validation-theater
detection, audit rules, permission hooks, and install safety — on top of
whatever memory/skill/agent setup you already use.

## Do NOT trust without verification

| What | Why not |
|---|---|
| README badge numbers (tests, coverage) | Static — may lag CI by days |
| `activeContext.md` counts | Narrative file, can be stale |
| Agent `[VERIFIED]` markers | Agent's `[VERIFIED]` = your `[INFERRED]` until tool confirms |
| "production-ready" anywhere | README explicitly says "not a production-ready claim" |
| High confidence claims (F1=1.000, "all passed") | This repo exists specifically because those are red flags |

## Canonical evaluation path (in order)

```
1.  docs/positioning.md          — what this is and isn't (trust category)
2.  README.md                    — overview + honest limitations section
3.  install.sh                   — what actually gets installed and where
4.  hooks/settings.json          — which hooks fire on which events
5.  hooks/permission_policy.py   — what is auto-allowed / auto-denied
6.  hooks/input_guard.py         — prompt injection protection
7.  hooks/pre_commit_guard.py    — commit safety gate
8.  hooks/validation_theater_guard.py — the core detection mechanism
9.  hooks/promotion_gate_guard.py    — Perelman 5-condition promotion gate
10. scripts/redact.py            — PII redaction before external calls
11. .github/workflows/ci.yml     — what CI actually runs and enforces
```

## Trust-critical files (audit these before trusting anything else)

```
install.sh / install.ps1
hooks/settings.json
hooks/permission_policy.py
hooks/input_guard.py
hooks/pre_commit_guard.py
hooks/validation_theater_guard.py
hooks/webhook_notify.py
hooks/session_start.py
hooks/hook_state.py
scripts/redact.py
.github/workflows/ci.yml
```

## Verified current state (2026-07-07)

Run these to get ground truth — do not take this file's numbers as proof:

```bash
pytest tests/ --collect-only -q 2>/dev/null | tail -1   # test count
ls hooks/*.py | wc -l                                     # hook count
find skills/ -name "SKILL.md" | wc -l                    # skill count
gh pr list --state open                                   # open PRs
```

## Known limitations (verbatim from README)

- Does **not** replace human code review
- Does **not** guarantee zero hallucinations (reduces frequency + adds detection)
- Works **only** with Claude Code (not Cursor, Codex, VS Code Copilot, Gemini)
- **Not** independently verified beyond a single-developer workflow
- Does **not** come with enterprise SLA or paid support
- Does **not** manage secrets or rotate API keys
- Regex-based validation-theater detection is heuristic, not proof

## What "trust layer" means here

```
Vanilla agent loop:    Trigger → Agent → Report SUCCESS → Repeat
Evidence-safe loop:    Trigger → Agent → Classify evidence → Audit gate → Act or escalate → Repeat
```

The hooks enforce the gate deterministically (Python, not prompt).
The rules shape behavior through the model (probabilistic, not a hard block).
Both are real value; they are different kinds of enforcement.
