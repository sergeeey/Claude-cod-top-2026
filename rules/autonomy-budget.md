# Autonomy Budget — General Interactive-Task Policy

## Why this file exists

`delegation-contract.md`'s own "Relationship to existing rules" table has
referenced `autonomy-budget.md` since 2026-09-02 — but this repo never shipped
it. A clean install of this config always had that reference dangling: nothing
in `check_architecture.py`'s Gate 9 catches a dangling prose reference between
two `rules/*.md` files (it only validates `depends_on:` entries in
`skills/registry.yaml`), so this class of gap had no gate. Found live
(2026-09-09) when a session in a project using this config asked elementary
yes/no questions mid-task despite being told to "act autonomously" — there was
nothing more concrete than `CLAUDE.md`'s one-line "act decisively, confirm only
for irreversible operations" to act on.

## The tier system

| Tier | Scope | Ask first? | Example |
|------|-------|------------|---------|
| **Green** | Read-only, local, reversible | No — just do it | Read/Grep/Glob, running existing tests, checking git status/log/diff |
| **Yellow** | Local edits, reversible via git | No — with tests + evidence, per this stack's own Falsification Ladder / pre-commit checklist | Editing files, `git commit` on a feature branch, opening a PR against a fork/worktree, creating/deleting a local branch |
| **Red** | Affects shared state, hard to reverse, or leaves the local machine | Yes — always, no exception | `git push` to a shared branch, merging a PR, `git push --force`, `git reset --hard`, schema migration, deploy |
| **Black** | Money, credentials, legal/compliance, mass-delete, sending on the user's behalf | Never done unilaterally — human must act, or an explicit live "yes" every single time | Financial transfer, entering a password, `DROP TABLE`, sending an email/Slack/PR comment, publishing |

**Hard rule:** Red or Black never proceeds silently.

## The one thing no project-level rule can change

Green/Yellow above is a methodology choice this file makes concrete. Red/Black
is different: it maps onto the harness's own baseline safety categories
(prohibited actions / explicit-permission-required actions), which the
system's own safety instructions state cannot be overridden by anything loaded
as context — `CLAUDE.md` included. No wording of "act autonomously," in any
project using this config, removes the live confirmation requirement for
Red/Black-class actions. That boundary is intentional, not a gap this file
closes.

## What this actually changes in practice

For Green/Yellow work — most of an ordinary coding session — act without
pausing to ask "should I do this?": read files, edit them, run tests, create
branches, commit, open PRs against a worktree/fork. Reserve an explicit
check-in for genuine Red/Black actions or a real ambiguous decision point (see
`meta-loop.md`'s DECIDE → NEEDS_HUMAN node) — not as a default reflex before
every step.

## Violation Protocol

If a tier classification turns out wrong mid-task (a Green action turns out to
touch shared state — e.g. a "local" branch that turns out to already be pushed
and watched by CI):
1. Stop, name the misclassification explicitly to the user.
2. Do not silently continue as if it were still Green/Yellow.
3. Re-classify and follow the corrected tier's rule from that point on.

For an automated loop specifically (not an interactive session), the same
idea applies mechanically: log the violation, fail open rather than proceed
with the forbidden action, and never treat a budget overrun as license to
continue.

## Relation to Evidence Policy

```
Autonomy Budget  = safety floor  (prevents harm)
Evidence Policy  = quality floor (prevents falsehood)
Both required.   Neither replaces the other.
```

## Project-specific extensions

A project may declare its own narrower budget for a specific automated loop
or agent (exact runtime caps, forbidden actions, file-count limits) — see this
repo's own `.claude/rules/autonomy-budget.md` for a worked example (3
SessionStart hooks, each Green-by-construction). Such a project addendum
should extend this file, not restate the tier table from scratch.

**Last updated:** 2026-09-09
**Status:** ACTIVE
**Source:** dangling `delegation-contract.md` reference, closed after being
found live in a session using this config.
