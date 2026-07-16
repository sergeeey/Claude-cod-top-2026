# Positioning — Trust Layer for AI Coding Agents

## 1. Category

**Trust Layer for AI Coding Agents.**

Not a memory system. Not a skill catalog. Not a multi-agent framework. Not a tool
manager. Those categories already have strong, mature players. This repo does not
compete with them — it sits on top of whichever ones you already use.

## 2. What this is not

- Not a replacement for a memory/context system (e.g. Claude-Mem-style persistence).
- Not a skill/plugin catalog competing on breadth of capability.
- Not a virtual-team framework competing on number of agent roles.
- Not a CLI/config manager competing on ease of switching between tools or models.

If your problem is "my agent forgets things," "my agent can't do X," "I need more
specialized roles," or "I want to switch tools easily" — this repo is not the primary
answer to that problem. It assumes you already have (or are evaluating) something for
those, and adds a layer they don't provide on their own.

## 3. What this adds

- **Evidence gates** — every validation claim carries a marker (`[VERIFIED-REAL]` vs
  `[VERIFIED-SYNTHETIC]`); synthetic data can never silently pass as a production claim
  (`rules/integrity.md`).
- **Oracle checks** — before an agent optimizes against a judge (a test, a metric, an
  LLM grader), the judge itself is audited for gameability
  (`docs/oracle-adequacy-gate.md`, `hooks/validation_theater_guard.py`).
- **Validation-theater detection** — catches the specific failure mode of an agent
  writing a test, running it on data it just generated, and reporting a suspiciously
  perfect score (`hooks/validation_theater_guard.py`, `rules/skeptic-triggers.md`).
- **Stop conditions** — tournaments and revival experiments carry a pre-declared budget
  and kill criteria, so a search does not drift indefinitely
  (`docs/stop-condition-gate.md`).
- **Null-result memory** — a killed approach is recorded with a Kill Analysis, not
  silently discarded, so the same dead branch is not blindly re-attempted
  (`null_results/`, `hooks/null_results_pre_check.py`).

None of this makes an agent more capable. All of it makes an agent's claims checkable.

## 4. Comparison

| Tool type | What it gives | What this repo adds on top |
|---|---|---|
| Memory systems | Remembers context across sessions | Evidence-gated memory — a remembered "success" still needs a `[VERIFIED-REAL]` marker before it's trusted again |
| Skill catalogs | More capabilities, more prebuilt workflows | Trust discipline — a new skill still runs through the same evidence/oracle gates as everything else |
| Virtual agent teams | More specialized roles, more parallelism | Audit gates between roles — a reviewer agent's "LGTM" is itself subject to the same verification standard |
| Tool/config managers | Easier install, switch, and manage of AI tooling | A verification policy layered underneath whatever tool is installed — it governs claims, not tool selection |

This is a positioning statement, not a benchmark. No head-to-head performance numbers
are claimed here against any named tool — the comparison is about what problem each
category solves, not which is "better."

## 5. Integration strategy

This repo is designed to be additive:
- Rules-only install (`rules/integrity.md` alone, ~500 tokens) works standalone in any
  Claude Code config, regardless of what memory/skill/team setup you already run.
- Full install adds hooks that gate on evidence markers and validation-theater signals
  without assuming a specific upstream memory or agent framework.
- If you already use a memory layer, a skill catalog, or a multi-agent framework, this
  repo does not ask you to replace any of them — it asks that whatever they produce
  passes through an evidence gate before being trusted as a claim.

## 6. One-line positioning

**Other tools make agents more powerful. This repo makes agents more verifiable.**

## Current status (honest, not aspirational)

- Conceptually strong: the oracle-aware pipeline (`/evolve-solution`, `/revive-project`)
  is coherent and, per an independent audit, does not duplicate existing machinery
  without reason (see `experiments/` for the audit trail).
- Clean-install path: fixed and re-verified — a fresh `install.sh --profile=standard`
  now deploys everything its own configuration references, with zero spurious
  artifacts on an empty target.
- Dogfood evidence: growing, not exhaustive — 2 real runs completed so far:
  - `experiments/20260701-p1-hooks-reproducible-install/` — PROMOTE; includes a
    variant tournament and an oracle audit (`tournament.md`, `oracle_audit.yaml`).
  - `experiments/20260701-revive-session-save/` — NEEDS-HUMAN; the run's own premise
    ("this file is abandoned") was falsified by its autopsy stage. No red-team pass
    was run on this one — the premise died before there was a claim left to red-team.

  This is a starting trend, not a mature track record yet.

Not claimed: "production-ready," a final maturity score, or a competitive benchmark
against any named tool.
