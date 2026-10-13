# Frozen-corpus re-run after PR C (falsification status semantics)

## What changed

`check_status_conditional_fields` stopped demanding `revival_condition` for `KILLED`.
It still demands it for `BLOCKED`, and still demands `kill_reason` for `KILLED`.

## Why — derived from the rules, not chosen by symmetry

The Rescue Review rules (`experiments/_template/decision.md`, echoed in
`falsification-ladder.md`) define four branch states and say, per state, what is
required:

| Rescue state | What the rules say | Revival Condition |
|---|---|---|
| `hard_killed` | "outside Rescue scope; only new theorem-level input can change it" | meaningless — revival needs a theorem, not a trigger |
| `killed` | "formulation falsified; **new branch allowed** (Minimal Relaxation Rule applies)" | not required — the path forward is a NEW experiment id, not a revival of this one |
| `parked` | "Revival Condition **required**" | **required** |
| `weak_alive` | "... + Revival Condition + cheapest differentiating test + AOG passed" | **required** |

The template's own crosswalk maps `hard_killed`/`killed` → `KILLED` and `parked` →
`BLOCKED`. So the rules require `revival_condition` for `BLOCKED` and do **not** require
it for `KILLED`. Cycle 1 had it exactly backwards for the KILLED family.

## Measured effect

| Scenario | before PR C | after PR C |
|---|---|---|
| `KILLED` + real `kill_reason`, no `revival_condition` | **1 error** (false demand) | **0 errors** |
| `KILLED`, no `kill_reason` | 1 error | **1 error** (unchanged) |
| `BLOCKED`, no `revival_condition` | 1 error | **1 error** (unchanged) |
| `ACTIVE`, neither field | 0 | 0 |

The two real records this protects — `20260824-elai-hooks-skeptic-pilot` and
`20260824-permission-policy-skeptic-pilot`, both "claim falsified AND the underlying
defect fixed" — can no longer be asked to invent a resurrection trigger they have no
honest way to fill.

**Mutation-tested, including both ways of "fixing" this wrongly:** reverting to the old
KILLED demand, dropping the `kill_reason` requirement, and dropping the `BLOCKED`
requirement are each caught by exactly their intended tests. Relaxing a false positive
by gutting the check is a real hazard here, and is pinned against.

## Known staleness in the PR #446 harness, stated rather than silently patched

`replay.py`'s **Layer B** embeds its own copy of the old rule
(`status in ("KILLED","BLOCKED") → revival_condition required`), so it still reports
3/12 firings. That harness is the frozen PR #446 baseline and is deliberately NOT
updated: editing the measuring instrument to agree with a later fix would destroy the
before-measurement the whole exercise rests on. Layer B's number should be read as "what
the Cycle-1 rule would have said", which is exactly what it was written to answer.

The *shipped* checker's behaviour is the table above, and it is what
`scripts/check_experiment_graph.py --check` now enforces (exit 0 on the real repository).

## NOT fixed here, and why — one `status` field carrying two questions

Three independent pieces of evidence, documented in
`docs/experiment-dependency-graph.md` § Known limitation:

1. `hard_killed` and `killed` are indistinguishable once flattened to `KILLED`.
2. `20260728-hypothesis-arbiter-taxonomy-pilot` records two verdicts at different levels
   (`Filing status: ARCHIVE` + `Claim-level result: REJECT`).
3. `20260728-osa-fl-protocol-vs-standard-analysis` is verdict `REJECT` while its Rescue
   Review's surviving branch is `weak_alive` — the experiment is killed, the rescued
   formulation is alive.

The obvious fix (a second field carrying the Rescue Review Final Status) is not built,
because only 3 of 13 experiments have a Rescue Review section and only 1 has it filled —
a field derived from a section almost nobody fills would repeat this cycle's own measured
lesson about opt-in additions reaching ~0 coverage. The honest next question is about
process, not schema: is the Rescue Review under-used because it is optional, or because
it is only sometimes applicable?
