# State and transitions

Read this file when path dependence is suspected, when state equivalence is ambiguous, or when time lags decide the answer.

## 1. State sufficiency

A state is sufficient when it contains every variable that can materially change future dynamics, and nothing that cannot.

Test: if two situations share this state description, would they plausibly develop the same way? If the answer is "no" and the difference is not in the description, the state is insufficient.

Minimal representation:

```
state:
  id: S0
  as_of:
  established:      # evidence-marked facts
  inferred:         # chains from established facts
  assumptions:      # accepted temporarily for analysis
  unknown:
  actors:
  resources:
  obligations:
  constraints:
  ongoing_processes:
  reference_state:
```

Record only what may materially affect future dynamics. Completeness is not the goal.

Keep separate what is true now and what may become true later. Do not write a future state into the current-state fields.

## 2. Latent variables

Some variables matter but are not observed: a hidden debt, an unknown competitor's readiness, an actor's intention. Record them as UNKNOWN or ASSUMPTION, name the observation that would reveal them, and do not let them disappear silently.

A latent variable that dominates the future and is unobserved is a strong candidate for the residual-uncertainty section.

## 3. State equivalence

Two states can be merged only if they are equivalent on every variable that drives future dynamics.

Checklist:
- resources;
- debts and obligations;
- constraints;
- contracts;
- actor strategies;
- actor beliefs, when they matter;
- irreversible commitments;
- institutional state;
- technical state;
- reputation;
- capabilities;
- information state;
- path-dependent history;
- time;
- external dependencies.

Example:

```
Company A: cash 10M, debt 0
Company B: cash 10M, debt 20M
```

They show the same cash. Their futures differ: B must service debt, can be forced to sell, and has fewer options. The same observable metric does not imply the same future.

Merging rule: merge only when no listed variable would change a future decision, risk or option. If you cannot check a variable, do not merge; keep both states and mark the difference UNKNOWN.

## 4. Convergence

Two different paths may reach the same observable state. Convergence is a claim about the future, not about the metric. Test convergence with the state checklist above. If the paths arrived differently and the history matters, they are not converged.

## 5. Memoryless and path-dependent systems

Ask: would the system behave differently depending on how it arrived here?

If yes, the state must carry the history. Typical carriers:
- technical debt;
- contracts and commitments;
- reputation;
- organizational learning and lost skills;
- political commitments;
- previous failures;
- network relationships;
- investments already sunk;
- user or public expectations;
- regulatory history.

Do not treat a path-dependent system as memoryless. That is the most common way a map becomes falsely clean.

## 6. Transition types

| Type | Meaning | Example |
|---|---|---|
| action | an actor does something | a company launches a product |
| reaction | a response to a previous change | competitors cut prices |
| external_event | caused outside the focal actor | a supplier fails |
| observation | new information becomes available | a test result arrives |
| shock | an unexpected disturbance | a regional outage |
| feedback | a change returns to its own driver | more users attract more developers |
| reference_shift | the comparison point changes | the baseline market price moves |

## 7. Mechanism classes

Name the mechanism class of each important transition. Common classes:
- resource constraint (money, time, people, compute);
- incentive change (rewards, penalties, rules);
- information change (who knows what);
- capability change (what becomes possible or cheap);
- coordination change (standards, partners, platforms);
- adaptation (actors adjust behaviour);
- path lock-in (commitments narrow options);
- measurement change (what is observed and reported).

A missing class is a signal for the coverage check.

## 8. Time lags

Classify each important transition: immediate, days, weeks, months, years, unknown.

Delayed mechanisms need explicit representation:

```
S0 --[mechanism, lag]--> S1
```

Typical traps:
- a short-term gain hides a later structural cost (lock-in, debt, technical debt);
- a short-term loss hides a later option gain (learning, reputation);
- a process with an unknown lag is treated as instant.

If the lag is unknown, say so. A missing lag is an assumption, not a zero.

## 9. Transition contract

Every important edge answers:

- from which state?
- what changed?
- why could it change?
- through which mechanism?
- over what time?
- what assumptions does this require?
- what would we observe if it happens?

Preferred record:

```
transition:
  from: S0
  to: S1
  trigger:
  type:
  mechanism:
  lag:
  assumptions:
  counterforces:
  signposts:
  marker:
```

Do not draw a causal arrow only because two events can be narrated in sequence.

## 10. Common state errors

- Visible metric treated as the whole state.
- Obligations and contracts ignored because they are not in the headline numbers.
- Reference state assumed constant.
- Two paths merged because they end at the same number.
- History dropped from a path-dependent system.
- A latent variable absent from the record, so nobody can check it later.
