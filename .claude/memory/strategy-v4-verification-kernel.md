# Strategy — v4 Verification Kernel (owner-aligned, 2026-09-21)

> **Status:** active direction (Cursor session + owner confirmation).  
> **Audience:** Claude Code / Cursor continuing this repo.  
> **Not yet:** enterprise control plane, graph DB, multi-vendor dashboard.

## One-line positioning

> AI agents are becoming more autonomous. We make their autonomy falsifiable, auditable and bounded.

**Today:** Claude Code reference implementation + evidence hooks.  
**Next milestone:** vendor-neutral **Verification Kernel** proven on **two harnesses**.  
**Later:** Agent Assurance / policy+intent / control plane (name reserved; do not use for v4).

## Architectural rule (hard)

> **Claude Code remains dogfood and adapter #1. No new control logic may permanently depend on Claude-specific hooks.**

| Stays in thin adapter | Moves into kernel |
|-----------------------|-------------------|
| PreToolUse / PostToolUse / Claude lifecycle formats | evidence, policy, oracle, risk, verification |
| Claude event plumbing | `AgentEvent`, `PolicyDecision`, `EvidenceRecord`, `VerificationResult` |

## Hypotheses & falsification

**Hypothesis:** Claude-specific control logic can become a vendor-neutral assurance kernel.

**Critical test (v4 acceptance):**

```text
Same failure scenario
→ Claude Code
→ Codex
→ same event semantics
→ same policy decision
→ comparable evidence result
```

If it fails — learn early. If it passes — first real milestone beyond “Claude config”.

## Minimal v4 entities (only four)

1. `AgentEvent`
2. `PolicyDecision`
3. `EvidenceRecord`
4. `VerificationResult`

No graph DB, no enterprise dashboard, no distributed control plane in v4.

## Roadmap order (do not reorder into mega-project)

1. **Generated metrics** — stop hand-edited counts in README/docs; generate from registry/CI.
2. **Autonomy wording** — remove public contradiction with Constitution.
3. **Minimal `AgentEvent` schema** — do not boil the ocean.
4. **Lift 5–10 proven guards** from Claude lifecycle into independent Python kernel.
5. **Codex adapter** — only enough to run the same scenarios.
6. **Behavioral corpus** — 20–30 high-quality real failure scenarios (not 500).
7. **Machine-readable verification receipt** — simple JSON first.
8. **Only then** — evidence graph, OpenTelemetry, MCP/A2A, richer policy/intent.

## Behavioral corpus (quality over quantity)

Each scenario from a **real failure mode**, with **expected behavior** (not only final answer):

- Validation Theater
- synthetic-as-real
- oracle contamination
- unauthorized write
- scope drift
- premature success
- hidden benchmark leakage
- null-result repetition
- destructive action without approval

## Adoption KPI (revised)

Not “50 users at any cost”.

1. **5–10 weekly active external users** who run it on real work and send failure cases  
2. **One paying pilot**

Five weekly engineers with real failures > 500 GitHub stars.

## Self-pruning / retirement (telemetry first)

Per guard, accumulate at least:

`trigger count → true positive → false positive → prevented impact`

Only then retirement logic. Plus:

> If the failure mode cannot be reproduced after a model change, the guard is not proven still needed.

Important guards need a **regression fixture** for replay when Claude/GPT versions change.

## Wording fix (marketing = Constitution)

| Bad (current README risk) | Better |
|---------------------------|--------|
| `ralph` = Don't stop. No confirmations. | `ralph` = persistent execution **within delegated authority** |
| `autopilot` = Execute all steps. | `autopilot` = autonomous execution **within policy and autonomy budget** |

Red/Black from Product Constitution still win over mode names.

## Naming

- Call v4 **Verification Kernel**, not “control plane”.  
- Control plane = later product name when identity, central policies, inventory, SIEM exist.  
- Repo `Claude-cod-top-2026` can remain the Claude reference; product name may later become vendor-neutral (EvidenceOps / AgentProof / VeriHarness — TBD).

## Stop doing

- Adding skills/hooks/agents without a **reproducible failure mode**.  
- Competing on skill/hook/agent **counts** (commodity).  
- Building enterprise assurance platform before cross-harness proof.

## Pointers

- Positioning: `docs/positioning.md`
- Constitution: `PRODUCT_CONSTITUTION.md`
- Autonomy budget: `.claude/rules/autonomy-budget.md` / `rules/` equivalent
- This decision also logged in `decisions.md` under 2026-09-21

---

*Saved 2026-09-21 from Cursor strategy alignment (owner + agent consensus ~80% with tightened execution order).*
