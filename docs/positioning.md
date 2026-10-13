# Positioning — Evidence-aware Goal Operating Layer for Claude Code

> Repositioned 2026-07-16 (PRODUCT_CONSTITUTION §12, owner-approved). Previously framed
> as a pure "Trust Layer... makes nothing more capable." That framing contradicted the
> actual repository, which ships goal orchestration (`/evolve-solution`), a scientific
> method stack, dispatcher/routing, and memory. The category below reflects what the code
> is; the trust/evidence machinery is repositioned as its *control system*, not the whole
> product.

## 1. Category

**Evidence-aware Goal Operating Layer for Claude Code.**

Give Claude Code a goal; it turns it into an explainable plan, composes the right
capabilities (skills, agents, tools, memory), executes within a bounded autonomy budget,
verifies the result, and remembers what worked. It is still not a memory system, a skill
catalog, or a multi-agent framework on its own — it *composes* whichever of those you use,
and adds the one thing they don't provide alone: the evidence + autonomy **control system**
that makes handing the agent more work safe. More capability, made checkable — not
capability withheld.

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
  `[VERIFIED-SYNTHETIC]`); synthetic data is flagged as such by rules and hooks (`rules/integrity.md`); the
  detection hook is a PostToolUse warning, not a preventive block.
- **Oracle checks** — before an agent optimizes against a judge (a test, a metric, an
  LLM grader), the judge itself is audited for gameability — a
  documented procedure (`docs/oracle-adequacy-gate.md`, stage 2 of `/evolve-solution`, stage 3 of `/revive-project`);
  no hook verifies that it was run.
- **Validation-theater detection** — catches the specific failure mode of an agent
  writing a test, running it on data it just generated, and reporting a suspiciously
  perfect score (`hooks/validation_theater_guard.py`, `rules/skeptic-triggers.md`).
- **Stop conditions** — tournaments and revival experiments are specified to carry a
  pre-declared budget and kill criteria (`docs/stop-condition-gate.md`,
  `commands/revive-project.md`); a documented procedure, not code-enforced.
- **Null-result memory** — a killed approach is recorded with a Kill Analysis, not
  silently discarded, so the same dead branch is not blindly re-attempted
  (`null_results/`, `hooks/null_results_pre_check.py`).

None of this *is* the capability — it is the control system around it. It makes an
agent's claims checkable, which is what lets you safely hand the agent more of the work.

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
- Rules-only install (`rules/integrity.md` alone, ~1.8k tokens: 7 KB, estimated as bytes/4) works standalone in any
  Claude Code config, regardless of what memory/skill/team setup you already run.
- Full install adds hooks that gate on evidence markers and validation-theater signals
  without assuming a specific upstream memory or agent framework.
- If you already use a memory layer, a skill catalog, or a multi-agent framework, this
  repo does not ask you to replace any of them — it asks that whatever they produce
  passes through an evidence gate before being trusted as a claim.

## 6. One-line positioning

**Give Claude Code a goal; get back an explainable plan, a bounded-autonomy execution, a
verified result, and a remembered procedure. More capability handed over — made checkable.**

## Current status (honest, not aspirational)

- Conceptually strong: the oracle-aware pipeline (`/evolve-solution`, `/revive-project`)
  is coherent and, per an independent audit, does not duplicate existing machinery
  without reason (see `experiments/` for the audit trail).
- Clean-install path: fixed and re-verified — a fresh `install.sh --profile=standard`
  now deploys everything its own configuration references, with zero spurious
  artifacts on an empty target.
- Dogfood evidence: growing, not exhaustive — 2 real goal-pipeline runs completed
  (count unchanged since 2026-07-01; status last reviewed 2026-09-25):
  - `experiments/20260701-p1-hooks-reproducible-install/` — PROMOTE; includes a
    variant tournament and an oracle audit (`tournament.md`, `oracle_audit.yaml`).
  - `experiments/20260701-revive-session-save/` — NEEDS-HUMAN; the run's own premise
    ("this file is abandoned") was falsified by its autopsy stage. No red-team pass
    was run on this one — the premise died before there was a claim left to red-team.

  `experiments/` now holds 14 dated folders, but only the two above ran the goal pipeline
  (`tournament.md` / `oracle_audit.yaml`). The others are separate pilots and replays,
  and several ended REJECT or ARCHIVE — e.g. `20260728-osa-fl-protocol-vs-standard-analysis`:
  REJECT — on 2 cases the full protocol scored lower than plain analysis; a same-night
  follow-up re-run of one case with a single modified instruction scored 11/12 vs 7/12 for
  the unchanged arm (`followup-v1-v2-rerun.md`, which itself notes up to 2 points of
  re-grading noise). Verdicts live in each `decision.md` and in `null_results/INDEX.md`.

  This is a starting trend, not a mature track record yet.

Not claimed: "production-ready," a final maturity score, or a competitive benchmark
against any named tool.
