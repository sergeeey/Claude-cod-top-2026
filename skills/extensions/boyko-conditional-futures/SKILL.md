---
name: boyko-conditional-futures
description: >
  Строит карту условных траекторий: как ситуация может развиться после триггера (действие,
  событие, шок, смена правил, новая информация). Выдаёт набор существенно различающихся
  траекторий с механизмами, временными лагами, ответами акторов, отложенными эффектами,
  внешними триггерами и сигналами наблюдения. Результат — карта сценариев, а не вероятностный
  прогноз. Использовать для: «что будет дальше», «последствия X», «эффекты второго порядка»,
  «как это может развиться», «возможные сценарии», «траектории развития».
  Не использовать для: простого поиска факта, перевода, одного расчёта, обычного пересказа,
  чистого арбитража гипотез (→ boyko-hypothesis-arbiter), проверки рисков запуска (→ pre-mortem),
  прогноза по одной переменной, если есть готовая методика прогноза.
  Триггеры: /boyko-conditional-futures, «возможные сценарии», «что будет дальше», «последствия»,
  «второго порядка», «траектории развития», scenario map, branching, how could this evolve.
allowed-tools: Read, Grep, Glob, WebSearch
triggers: [/boyko-conditional-futures, "«возможные сценарии»", "«что будет дальше»", «последствия», "«второго порядка»", "«траектории развития»", "scenario map", branching, "how could this evolve"]
---

# boyko-conditional-futures — Условные будущие

Build a conditional map of how a situation can develop. Do not predict one future.

The default output is a **scenario map**: conditional paths with mechanisms, lags and signposts.
Do not output a **forecast** (likelihoods) unless the user asks for likelihoods and evidence supports them. See `references/evidence-and-forecast.md`.

Answer in the user's language. Keep technical terms in English where they appear in this file.

## Depth

Default: the minimum depth that answers the question. For a simple question, use the compact output (see Output contract).

Expand (read more references, add branches or checks) when:
- stakes are high;
- mechanisms remain ambiguous;
- the user asks for depth;
- external evidence would materially change the trajectories.

## Six invariants (never break)

1. **ACTION ≠ WORLD RESPONSE.** "We do X" is not "X succeeded". Model X as an action with several possible world responses.
2. **SCENARIO ≠ FORECAST.** A scenario is a conditional sequence. Attach likelihoods only with evidence.
3. **Every material transition has a trigger, a mechanism, a time lag and assumptions.** A sequence of events in prose is not a causal arrow.
4. **States merge only after the State Equivalence Gate.** An equal visible metric does not mean an equal future.
5. **Plausible branches are not adequate coverage.** Run the Coverage & Challenge check before stopping.
6. **Uncertainty stays visible.** Label unknowns and state that the map is not exhaustive.

## Procedure

1. Freeze the starting state S0 (state contract below). Separate what is true now from what may become true later.
2. Identify the trigger type: ACTION, EVENT, EXTERNAL_TRIGGER, SHOCK, OBSERVATION, RULE_CHANGE, TECHNOLOGY_CHANGE, REFERENCE_SHIFT, STATE_CHANGE.
3. If useful as a comparison, write the baseline path: what continues with no new intervention or shock.
4. Generate first-order effects. Propagate them through mechanisms to second-order effects. Add responses of adaptive actors. Add material external triggers.
5. Build 2–4 materially different trajectories. Add more only if a distinct mechanism exists.
6. Apply the Decision Relevance Gate. Find the earliest decision- or knowledge-relevant difference, not merely the earliest difference.
7. Check delayed consequences and feedback loops before concluding.
8. Apply the State Equivalence Gate before merging any nodes.
9. Run the Coverage & Challenge check (`references/coverage-and-challenge.md`).
10. For each important trajectory: counterevidence, signposts, and one distinguishing observation against the main competitor.
11. Record residual uncertainty.
12. Stop by the stopping rules.

## State contract

```
state: S0
  as_of:
  established:      # with evidence marker (see below)
  inferred:         # INFERRED, with the chain stated
  unknown:          # UNKNOWN
  actors:
  resources:
  commitments:      # obligations, contracts, irreversible steps
  constraints:
  reference_state:  # the baseline you compare against
```

Record only variables that can change future dynamics.

**Evidence markers:** use the markers of `~/.claude/rules/integrity.md` (VERIFIED, DOCS, CODE, MEMORY, INFERRED, WEAK, CONFLICTING, UNKNOWN). Do not create a separate evidence system. SCENARIO and FORECAST are output types, not evidence markers.

## Transition contract

```
transition:
  from: S0
  to: S1
  trigger:
  type: action | reaction | external_event | observation | shock | feedback | reference_shift
  mechanism:
  lag: immediate | days | weeks | months | years | unknown
  assumptions:
  counterforces:
  signposts:        # what we would observe if it starts to happen
  marker:           # integrity.md marker
```

A mechanism you cannot name is written as **HYPOTHESIS** in the text. Do not hide it in fluent prose.

## The three gates (apply inline)

**Decision Relevance Gate.** Keep a branch only if it changes at least one of: a future action, understanding of a mechanism, risk exposure, resource position, capability, a constraint, an irreversible commitment, the option set, a strategic position, a research conclusion, or monitoring priority.

**State Equivalence Gate.** Two states may merge only if they match on every variable that drives future dynamics: resources, debts and obligations, constraints, contracts, actor strategies, irreversible commitments, institutional and technical state, reputation, information state, and history. Example: cash 10M with debt 0 is not equivalent to cash 10M with debt 20M.

**Coverage & Challenge Gate.** Ask: Which mechanism class is missing? What happens with no new intervention? Could another actor change the path? Could a shock or rule change invalidate the map? Could the reference state itself change? Is there a realistic unpleasant branch? Is a delayed effect reversing the direction? Full checklist: `references/coverage-and-challenge.md`.

## Delayed effects and feedback

After the nearest decision-relevant divergence, check: is there a known delayed mechanism that could reverse it or dominate it? Example: revenue up 5% after one month, but architectural lock-in after one year.

Look for reinforcing loops (A → B → stronger A) and balancing loops (A → B → weaker A). Add a loop only when a plausible mechanism exists.

## Signposts

For each important trajectory give observables that:
- are connected to its mechanism;
- are available before the final outcome;
- can distinguish it from the other trajectories.

Avoid signposts such as "watch the news".

For the main pair of competing trajectories, give one distinguishing observation: observation, supports, weakens, expected timing, limitations.

## Local safeguards

These rules are kept here on purpose, so this skill does not depend on other skills.

- Do not turn a plausible transition into a causal claim without causal evidence. Mark it HYPOTHESIS and name an alternative mechanism.
- For every major trajectory, give counterevidence and the observation that would downgrade it.
- A simulation is not evidence. Label simulated trajectories as simulated.
- Do not pick a historical analogue because it fits the preferred story.
- Do not assign probabilities without an evidence source. Use "plausible", "less supported", "high uncertainty" or "likelihood not established".

## Stopping rules

Stop when:
- new branches do not change the interpretation;
- the next useful step is an observation, measurement or research, not more branching;
- the remaining states are equivalent under the State Equivalence Gate;
- Coverage & Challenge finds no new important mechanism;
- further steps rest on too many unsupported assumptions, or become speculative.

Do not stop at the first trivial divergence. Do not keep branching to reach a target count.

## Reading guide for references/

- `references/methodology.md`: full theory (consequence depth, actor responses, sequential decisions, opportunity sets, path dependence, lock-in, method router). Read for complex cases.
- `references/state-and-transitions.md`: state sufficiency, latent variables, state equivalence in detail, time lags, convergence. Read when path dependence is suspected or state equivalence is ambiguous.
- `references/coverage-and-challenge.md`: full challenge checklist and branch control. Read when stakes are high or many external actors exist.
- `references/evidence-and-forecast.md`: scenario vs forecast, base rates, probability upgrade, causal caution, simulation, analogues, research mode. Read when probabilities are requested, causal claims matter, or research is needed.
- `references/examples.md`: worked examples. Read only when the task is ambiguous or an example would clarify the method.

## Output contract

**Full output** (complex or high-stakes cases):

1. **Current state (S0):** established, inferred, unknown; baseline; critical assumptions.
2. **Trigger:** what starts the analysis, with its type.
3. **Core mechanisms:** the few that shape development.
4. **Conditional trajectory map:**
   ```
   S0
   ├─ T1: mechanism A → S1
   │   ├─ actor response → S2
   │   └─ external trigger → S3
   ├─ T2: mechanism B → S4
   └─ Baseline (no new intervention) → S5
   ```
5. **Why the terminal states differ:** resources, constraints, commitments, options, history.
6. **Delayed effects and feedback.**
7. **Coverage challenge:** what may still be missing.
8. **Signposts and one distinguishing observation.**
9. **Residual uncertainty:** "These are the main modeled trajectories, not an exhaustive set of futures."
10. **What to watch or decide next.**

**Compact output** (simple tasks):

```
Current state
Trigger
Trajectory A: mechanism → state → signpost
Trajectory B: mechanism → state → signpost
Trajectory C: mechanism → state → signpost
Main missing uncertainty
What to watch next
```


## Final check

Before answering, run the quality check and the anti-pattern list in `references/methodology.md` §22. If a gate fails, weaken the conclusion or revise the map.
