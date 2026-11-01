# Evidence and forecast

Read this file when probabilities are requested, when causal claims matter, when simulations or analogues are used, or when research is needed.

## 1. Scenario is not forecast

A scenario describes a conditional sequence: if the trigger occurs and these mechanisms operate, these states follow.

A forecast asserts a likelihood: this outcome is more or less likely, by a given amount.

A scenario ranking is not a probabilistic forecast. Calling plausible paths "likely" without evidence is the most common error of this kind of analysis.

## 2. When a forecast is requested

If the user asks which outcome is more likely, and by how much, follow the forecast upgrade procedure:

1. Identify suitable reference classes.
2. Estimate base rates where possible.
3. Collect current evidence.
4. Separate the evidence that supports each branch.
5. Assess dependence between sources. Two sources that copy each other count as one.
6. Produce ranges, not false precision.
7. State confidence in the probability estimate separately from the event probability.

The trajectory map stays the structural layer. The forecast is an additional layer on top of it.

## 3. Evidence for probabilities

Acceptable evidence:
- reference classes;
- base rates;
- historical frequencies;
- validated forecast models;
- market-implied information;
- surveys with known methodology;
- calibrated expert judgment;
- empirical transition frequencies.

If none is available, do not invent a number. Use qualitative labels:
- plausible;
- material;
- less supported;
- high uncertainty;
- likelihood not established.

## 4. Probability gate

Do not assign probabilities merely because a scenario looks plausible. A numerical probability needs an evidence source named in the output. Without it, the number is decoration.

## 5. Causal caution

Distinguish five levels, and use the stronger language only when the evidence supports it:

| Level | Meaning | Marker in integrity.md |
|---|---|---|
| sequence | one event follows another | VERIFIED or DOCS for the order itself |
| association | the two co-occur | INFERRED or WEAK |
| plausible mechanism | a credible path exists | HYPOTHESIS in the text |
| causal hypothesis | a testable causal claim | HYPOTHESIS, with the test named |
| identified causal effect | estimated with a design that supports causality | DOCS or CODE with the design stated |

A plausible transition is not automatically an identified causal relationship. When causality is uncertain, mark the transition as HYPOTHESIS and give an alternative mechanism. For causal estimands in research, the EstimandOps rule applies: identify population, intervention, comparator and endpoint, and check identifiability before claiming a causal effect.

## 6. Simulation governance

Simulation output is not observation.

Monte Carlo, agent-based models, game simulations and LLM-agent simulations explore the consequences of assumptions. They do not validate those assumptions.

Rules:
- label every simulated trajectory as simulated;
- state the assumptions that drive the result;
- do not cite a simulation as empirical support;
- if a simulation is the only support for a trajectory, mark the trajectory as hypothesis.

## 7. Historical analogues

For each analogue consider:
- similarities;
- differences;
- whether the mechanism matches;
- whether the regime is the same;
- what actually happened.

Do not pick the analogue that fits the preferred story. Choose the analogues before deciding which story you prefer, or list the ones that disagree. Analogues inform possibility and base rates. They do not guarantee repetition.

## 8. Counterevidence

For each major trajectory state:
- evidence against it;
- a mechanism that could stop it;
- the most fragile assumption;
- an alternative explanation;
- the observation that would downgrade it.

A trajectory without these five items is not finished.

## 9. Signposts in detail

A useful signpost is:
- observable;
- connected to the mechanism;
- available before the final outcome;
- able to distinguish competing trajectories.

Bad signposts: "watch the news", "monitor the market", "see how it develops". Good signposts name the variable, the direction, and the threshold or timing: "output per employee rises for two quarters while competitor output does not converge".

Distinguishing observation record:

```
distinguishing_observation:
  observation:
  supports:
  weakens:
  expected_timing:
  limitations:
```

## 10. Research mode

Research is needed when external evidence materially changes the map. Research the assumptions that most affect the structure of the trajectories, not everything.

Priority sources:
- primary sources;
- official data;
- regulators;
- peer-reviewed research;
- high-quality professional sources;
- historical evidence.

Use research to check:
- the current state;
- transition mechanisms;
- actor incentives;
- historical analogues;
- base rates;
- timing;
- signposts.

Record what was checked and what was not. A search that finds nothing is weak evidence of absence, not proof.

## 11. Evidence markers

Use the markers of `~/.claude/rules/integrity.md`. Typical use in this skill:
- VERIFIED: checked with a tool or the user's own data;
- DOCS: from documentation or a primary source you read;
- INFERRED: a consequence of verified facts, with the chain stated;
- WEAK: a single or indirect source;
- UNKNOWN: not established.

SCENARIO and FORECAST are output types. They are not evidence markers, and a scenario must never be labelled VERIFIED.
