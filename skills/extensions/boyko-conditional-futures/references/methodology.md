# Conditional Futures — full methodology

This file holds the full theory behind the operational skill in `../SKILL.md`. Read it for complex or high-stakes cases. The invariants and gates in SKILL.md stay in force here.

## 1. Purpose and core question

The skill explores how a situation can develop through time. It does not attempt to predict one inevitable future. It builds a conditional map.

Core question: given the current state and a triggering event, action or change, through what materially different mechanisms could the situation develop next?

Secondary questions:
- What causes each transition?
- How do other actors respond?
- What changes immediately versus with delay?
- What new possibilities open or close?
- Which external events could alter the path?
- Which observations would distinguish competing trajectories?
- Which important mechanism class might be missing from the map?

## 2. Basic chain

```
CURRENT STATE
      ↓
EVENT / ACTION / SHOCK / OBSERVATION
      ↓
DIRECT EFFECTS
      ↓
ACTOR / SYSTEM RESPONSES
      ↓
SECOND-ORDER EFFECTS
      ↓
NEW STATE
      ↓
NEW EVENTS / DECISIONS / CONSTRAINTS
      ↓
FURTHER TRAJECTORIES
```

The chain is a guide, not a ritual. Stop expanding a link when additional layers do not improve the analysis.

## 3. Scenario and forecast

A scenario describes a conditional future: if the trigger occurs and these mechanisms operate, these states follow.
A forecast asserts how likely an outcome is.
Never treat a scenario as a forecast without additional evidence. The boundary is developed in `evidence-and-forecast.md`.

## 4. Trigger classification

A trigger starts a trajectory. Use the type that fits:

- **ACTION**: a deliberate action by an actor.
- **EVENT**: something that occurred.
- **EXTERNAL_TRIGGER**: a change caused by another actor or by the environment.
- **SHOCK**: an unexpected external disturbance.
- **OBSERVATION**: new information becomes available.
- **RULE_CHANGE**: laws, incentives, standards, policy, permissions or constraints change.
- **TECHNOLOGY_CHANGE**: a new capability becomes available or cheaper.
- **REFERENCE_SHIFT**: the baseline or comparison state itself changes.
- **STATE_CHANGE**: the system has already moved into a new state.

Do not force every trajectory to start from a decision. Many start from a change in the world.

## 5. Action is not world response

The most important invariant: never collapse "we decided to do X" into "X succeeded".

Correct structure:

```
ACTION X
   ↓
possible world responses:
   O1
   O2
   O3
```

An actor controls the action. It usually does not control the response of the world.

Example: an experiment is run. The effect replicates, or the effect disappears, or the result stays ambiguous, or an external condition invalidates the experiment. These are four different states, and only the first is the one the actor wanted.

## 6. Consequence depth

Distinguish four levels:

- **First-order effect**: the direct, immediate consequence.
- **Second-order effect**: the response to the first consequence.
- **Third-order effect**: the adaptation of the system to that response.
- **Structural effect**: a change in rules, incentives, capabilities, institutions or long-term constraints.

Do not expand automatically to arbitrary depth. Expand only while the next layer materially changes the interpretation, the risk, or the decision. Structural effects are often the most important and the least visible, so check for them explicitly.

## 7. Mechanisms

For each significant transition:

```
DRIVER
   ↓
MECHANISM
   ↓
INTERMEDIATE EFFECT
   ↓
NEW STATE
```

Example: AI lowers the marginal cost of a task → one employee produces more output → expectations rise → the previous productivity advantage becomes the new baseline.

If the mechanism is unknown, mark it HYPOTHESIS. Do not hide the gap behind smooth wording.

## 8. Actor response

For each important transition, ask:
- Who notices the change?
- Which incentives change?
- Which actions become more attractive?
- What information do they have, and what do they lack?
- How might they respond?
- How does that response affect other actors?

Actor classes include individuals, companies, competitors, states, regulators, investors, users, researchers, suppliers, agents and automated systems.

Do not model actors as passive when their adaptation is central to the outcome.

## 9. External triggers

After the initial paths, ask: what important event could change the trajectory without being caused by the focal actor?

Check in particular: parallel actors, competitors, regulators, technology changes, new information, macroeconomic changes, market prices, resource constraints, security events, mergers, political changes, parallel development, unexpected failures, and changes in the reference state.

An external trigger can change: the world state, the available actions, the reference baseline, the incentives, the rules, the actors themselves, or the interpretation of previous evidence.

## 10. Reference shift

Ask whether an apparent change comes from a change in the reference state rather than in the target.

Represent two things separately:
- **OBJECT CHANGE**: the target changed.
- **REFERENCE CHANGE**: the comparison point changed.

Example: a branch looks stale. This may mean the file changed, or that the main line advanced while the branch stayed fixed. The two imply different actions.

A reference shift is a first-class transition type.

## 11. Time and lags

Give each meaningful transition a rough temporal character when it matters: immediate, days, weeks, months, years, or unknown.

Avoid implying instantaneous causality for processes with delays. Represent delays explicitly:

```
S0 --[mechanism, lag]--> S1
```

A delayed effect can overturn an attractive short-term trajectory. A trajectory that looks good at one month can be the worst at three years.

## 12. Path dependence

Ask: would the system behave differently depending on how it arrived here?

If yes, keep the relevant history in the state. Typical carriers of path dependence:
- technical debt;
- contracts;
- reputation;
- organizational learning;
- political commitments;
- previous failures;
- network relationships;
- investments;
- user expectations;
- regulatory history.

Do not collapse a path-dependent system into a memoryless state.

## 13. Opportunity set

For important states, identify changes in what becomes possible. Use only when relevant:

```
option_changes:
  opened:
  closed:
  easier:
  harder:
  cheaper:
  more_expensive:
  irreversible_commitments:
```

This matters most when a trajectory changes future flexibility. Lock-in is the case where the option set narrows irreversibly: a standard, a contract or a platform choice makes other futures expensive.

## 14. Sequential decisions

Some trajectories contain decision nodes:

```
EVENT
  ↓
NEW STATE
  ↓
DECISION
├─ A
├─ B
└─ C
```

Each decision then generates world responses:

```
ACTION A
├─ O1 → S1
└─ O2 → S2
```

Sequential decision analysis is a mode inside this method. It is not the definition of the method.

## 15. Feedback loops

Look for effects that return to influence their own drivers.

- **Reinforcing loop**: A → B → stronger A. Example: adoption → more ecosystem investment → better product → more adoption.
- **Balancing loop**: A → B → weaker A. Example: high margins → new competitors → lower margins.

Represent a loop only when a plausible mechanism exists. Do not add feedback because complex-system vocabulary sounds appropriate.

## 16. Method router

The skill may use other analytical methods, but none is mandatory. Possible additions: causal DAG or SCM, systems thinking, game theory, reference classes, structured analogies, time-series forecasting, Bayesian updating, real options, network analysis, Monte Carlo, agent-based modelling, change-point detection, early-warning signals, pre-mortem, sensitivity analysis, value of information.

Activate a method only when it adds predictive, causal, explanatory, monitoring or decision value beyond a simpler trajectory graph. Do not turn the skill into a checklist of every available method.

## 17. Depth control

Default to the minimum depth that answers the question. Expand when:
- stakes are high;
- mechanisms remain ambiguous;
- the user asks for depth;
- external evidence materially changes the trajectories.

The model chooses the depth from the task. Do not pre-assign fixed modes.

## 18. Residual uncertainty

The map never exhausts the future. Say so when it matters. Typical residual uncertainty:
- unknown unknowns;
- unmodeled actor behaviour;
- structural breaks;
- measurement uncertainty;
- unobserved constraints;
- future technologies;
- policy surprises.

## 19. Conceptual boundary

These tools interact but should not be merged:

| Tool | Question |
|---|---|
| Hypothesis tree | What may be true? |
| Solution space | What can we do? |
| Forecast | What is likely to happen? |
| Causal analysis | What changes if we intervene? |
| Pre-mortem | How could the plan fail? |
| Conditional futures | Through which conditional mechanisms can the situation evolve from here? |

## 20. Fluent language is not evidence

Smooth prose can hide weak links. When writing, keep the distinctions visible: fact, inference, hypothesis, assumption, scenario, forecast, unknown. The reader must be able to see which sentence rests on what.

## 21. Final principle

The skill does not try to know the future. It makes conditional futures more explicit, more causal, more temporally disciplined, more challengeable, more observable and less narratively arbitrary.

Optimize for: decision-relevant distinctions, mechanism quality, state fidelity, coverage challenge, observable signposts. Avoid: unsupported assumptions, branch explosion, false certainty.


## 22. Anti-patterns and quality check (moved from SKILL.md)

### Anti-patterns

1. Treating an action as if its intended outcome already occurred.
2. Generating branches to reach a target count.
3. Calling a coherent story a forecast.
4. Assigning unsupported probabilities.
5. Merging states on one visible metric.
6. Ignoring obligations, history or timing.
7. Treating delayed effects as instantaneous.
8. Ignoring external actors or a moving reference state.
9. Assuming the modeled branches exhaust the future.
10. Stopping at the first trivial divergence, or continuing into speculation.
11. Using simulation as validation.
12. Using causal language stronger than the evidence supports.
13. Hiding assumptions.
14. Optimizing for narrative elegance instead of discriminating value.

### Quality check (silent, before answering)

- Is action separated from world response?
- Does every major transition have a mechanism, a lag and assumptions?
- Were adaptive actors and external triggers considered?
- Was the reference state checked for change?
- Are first-order and delayed consequences distinguished?
- Were merged states checked for future equivalence?
- Is the baseline considered where useful?
- Is residual uncertainty visible?
- Are scenario and forecast clearly separated, and are probabilities justified or absent?
- Do the main trajectories have signposts and one distinguishing observation?
- Does the complexity add value over a simpler answer?

If a gate fails, weaken the conclusion or revise the map.
