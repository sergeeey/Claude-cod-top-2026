# Methodology Deep Dive

> Moved out of `README.md` (2026-07-27, P0-B item 6) so the top of the README
> gets a reader to "what is this / how do I start" in under 2 minutes instead
> of 236 lines of methodology vocabulary first. Content unchanged from the
> README sections it replaces.

## From Prompting Agents to Auditing Loops

AI development is shifting from one-shot prompts to **recurring agent loops** — agents that run on
a schedule, verify results, and act autonomously. Platforms like
[Langflow](https://github.com/langflow-ai/langflow) make building these loops easy.

The problem: **loops amplify whatever is inside them.** Without evidence gates, a loop that runs
every 30 minutes will report `SUCCESS ✅` every 30 minutes — even when the agent is testing itself
on synthetic data it just generated.

This config adds the audit layer that loop platforms skip:

```
Vanilla loop:    Trigger → Agent → Report SUCCESS → Repeat
Evidence-safe:   Trigger → Agent → Classify evidence → Audit gate → Act or escalate → Repeat
```

| What loops need | This repo provides |
|---|---|
| Evidence classification | `[VERIFIED-REAL]` vs `[VERIFIED-SYNTHETIC]` — hard rule in `rules/integrity.md` |
| Synthetic detection | `hooks/validation_theater_guard.py` catches inline mock data |
| Skeptic auto-trigger | Fires on F1≥0.9, "all passed", round numbers |
| Null result tracking | `null_results/INDEX.md` — dead paths are data, not noise |
| Human escalation | Audit gate flags; human approves; loop continues clean |

> **Don't just prompt agents. Build loops that audit them.**
>
> Full spec and Loop Spec template: [`docs/LOOP_CODING.md`](LOOP_CODING.md)

---

## Oracle-Aware Evolutionary Mode

Auditing a loop tells you whether *a* result is real. The next step is to *search*
for the best result without fooling yourself — and the way you fool yourself is by
optimizing hard against a judge you never audited. A perfect score from a worthless
oracle (`F1=1.000` on synthetic data) is the canonical trap.

`/evolve-solution` runs the **Oracle-Aware Core** — never one solution, always a
field of competing variants, judged by an oracle that earned trust first:

```
Intent → Oracle-Adequacy Gate → Falsification Contract → Variant Tournament
       → Red-Team → Evidence Gate → Null Result Ledger
```

| Stage | Question it answers | Backed by (no new hooks, no new agents) |
|---|---|---|
| **Intent** | What are we really optimizing? | `rules/estimand-ops.md`, `/estimand-bridge` |
| **Oracle Adequacy** | Is the judge worth optimizing against? | [`docs/oracle-adequacy-gate.md`](oracle-adequacy-gate.md), `validation_theater_guard` |
| **Falsification** | What would prove each variant wrong? | `rules/falsification-ladder.md` |
| **Tournament** | Which of ≥3 variants wins? | `/cross-domain`, `/hypothesis-arbiter`, `/combinatorial-creativity` |
| **Red-Team** | Does the winner survive attack? | `/skeptic`, `/codex-skeptic` |
| **Evidence Gate** | Is the win proven, not claimed? | `rules/integrity.md`, `promotion_gate_guard` |
| **Null Ledger** | What did we learn from the dead? | `null_results/`, `reject_gate_guard`, `null_retroscan` |

The genuinely new piece is the **Oracle-Adequacy Gate**: optimizing against an
inadequate oracle is *worse* than not optimizing — it manufactures false confidence
at scale. So the oracle is audited (gameable? negative control? real data?) before
any variant runs.

```
/evolve-solution "find a non-obvious way to cut our RAG hallucination rate"
```

> Command: [`commands/evolve-solution.md`](../commands/evolve-solution.md) ·
> Gate: [`docs/oracle-adequacy-gate.md`](oracle-adequacy-gate.md) ·
> Templates: `templates/intent_card.yaml`, `oracle_audit.yaml`, `falsification_contract.yaml`
