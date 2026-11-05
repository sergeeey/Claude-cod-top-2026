# Claim and pre-registration: does a minimal Boyko help reach goals? (pilot, T1)

Written and committed BEFORE any arm was run. Later edits are listed in `protocol.md` under
"Deviations".

## L0 gate

- **Type: Causal.** The question is whether the outcome changes because of the add-on.
- Pilot scope: one task (T1), four arms, one run per arm. This is a **smoke-and-cost pilot**,
  not evidence of superiority.

## Estimand (one sentence, written before results)

We estimate the difference in task success (criteria 1–3 of T1) and in cost, turns and tool use
for a registry-audit task on `Claude-cod-top-2026` at commit `bc02e1c`, comparing plain Claude
Code (A), the current full add-on (B), a goal contract only (C′) and a minimal Boyko method (C);
a run aborted by the environment counts as a failure, a tool call denied by permissions is
counted and reported.

## Arms (frozen)

| Arm | Configuration |
|---|---|
| A | `--safe-mode` (all customizations off) |
| B | no safe-mode: the full live setup (global CLAUDE.md, hooks, skills) |
| C′ | `--safe-mode` + `arms/C_prime_contract.md` |
| C | `--safe-mode` + `arms/C_prompt.md` (contract + Boyko method + the `boyko-goal-compass` skill text) |

Same model (`claude-sonnet-5-5`), same prompt (`tasks/T1_prompt.txt`), same allowed tools, no
MCP servers, a fresh clone of commit `bc02e1c` per arm. File hashes: `HASHES.txt`.

## What this result does NOT mean

1. It does not show that Boyko helps on other task types, larger tasks or other models.
2. One run per arm cannot separate an effect from chance: LLM runs vary run to run.
3. It does not show that Boyko, rather than any extra system prompt, caused a difference; that
   is what arm C′ is for.
4. The checker and the task were written by the same model family that is being evaluated.

## Detectability

`n=1 run per arm, baseline_or_sigma=unknown (no prior runs), alpha=0.05, power=0.8,
MDE=undetectable, MCID=one extra failed criterion or more than a 2x cost ratio (owner to
confirm)`.

With `MDE=undetectable` no null claim is allowed. Any statement is "observed in this one run",
with the estimate and no interval.

## Decision rules (fixed in advance)

- If an arm fails criterion 2 (reports one of the four trap names as missing), the failure is
  recorded as the headline result for that arm, whatever the other criteria say.
- If every arm succeeds on criteria 1–3, T1 does not discriminate; the next step is a harder
  task, not a conclusion about Boyko.
- Cost and token differences are reported as observed numbers, not as significant.
- Whatever happens, the pilot decides only whether to run the next cells (more tasks, repeats),
  and it does not decide whether to keep or remove any component.

## Known threats

- Arm B writes to the owner's live hook logs while running (contamination of those logs).
- In arm B the global instructions may lead the model to read memory outside the clone.
- A single run per arm: nondeterminism is not controlled.
- T1 turned out to have an easy correct answer (the empty list); its main discriminating
  feature is the trap of four entries that look missing but are not `type: directory`.
