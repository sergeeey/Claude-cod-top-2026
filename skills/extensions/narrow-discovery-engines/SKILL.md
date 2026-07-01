---
name: narrow-discovery-engines
description: >
  Specialized search engines for problems where the goal is not "find the best
  solution" but "find the one that actually exists". Standard tournament assumes
  solutions exist and competes them — these engines find the solution space first.
  Invoke when: (1) the hypothesis space is unknown and needs mapping before a
  tournament; (2) data points that break the current model are more informative
  than data points that confirm it; (3) the domain has a known exhaustion
  structure (finitely many mechanisms). Triggers: /narrow-discovery, "find what
  breaks the model", "orphan data", "anomaly-first", "constraint relaxation",
  "map the solution space before tournament". NOT for: competitive optimization
  of known variants — use /evolve-solution for that.
---

# Narrow Discovery Engines

Standard discovery: define hypothesis → test. Works when you have a hypothesis.

Narrow discovery: start from constraints, anomalies, or orphan observations —
work backward to find what must exist. Used when you do not yet have a
hypothesis worth testing, but you have structure you can exploit.

These engines run BEFORE `/evolve-solution` Stage 1 (Intent Card), or as a
standalone discovery pass that produces a hypothesis for the standard pipeline.

---

## Engine 1 — Orphan Data Miner

**When to use:** you have a model, you have data, and some data points do not
fit. The orphans are not noise — they are where the model is wrong.

**Protocol:**

```
Step 1 — Classify all data points against current model
         into EXPLAINED (|residual| < MCID) and ORPHAN (|residual| ≥ MCID).

Step 2 — Cluster the orphans. Do they share any feature?
         (same time window, same category, same input distribution)
         If yes → the cluster IS a hypothesis about what the model misses.
         If no → random noise. Stop. Orphans are not informative here.

Step 3 — For each orphan cluster, write a reverse hypothesis:
         "If [feature X] is causally related to the outcome,
          then [prediction P] should hold for these orphans but not the rest."

Step 4 — Test the reverse hypothesis on held-out data.
         Result: a new mechanism candidate, or confirmed noise.
```

**Required input:** a current model with measurable residuals and a definition
of MCID (minimum change worth caring about). Without MCID, "orphan" is
undefined.

**Output:** zero or more hypothesis candidates → feed into `/evolve-solution`
Stage 3 (Falsification Contract) as new variants.

---

## Engine 2 — Constraint Relaxation Search

**When to use:** the current approach fails because of an assumption you cannot
verify was necessary. Systematically relax one assumption at a time and check
what becomes possible.

**Protocol:**

```
Step 1 — List ALL assumptions currently held:
         (a) assumptions known to be true
         (b) assumptions believed to be true but not verified
         (c) assumptions inherited from prior work without checking

Step 2 — For each assumption in (b) and (c):
         "If this assumption is FALSE, what new solution class becomes available?"

Step 3 — Filter by testability:
         "Can I test whether this assumption is false in under 4 hours?"
         YES → this is a cheapest differentiating test candidate.
         NO  → record as a speculative branch, set revival condition.

Step 4 — Execute the cheapest test for the most consequential assumption.
         If assumption is false → new solution class is open.
         If assumption is confirmed true → continue to next.
```

**Minimal relaxation rule:** relax ONE assumption per branch. Multi-assumption
relaxation creates an untestable space. Use one at a time.

**Output:** a ranked list of assumption-relaxation → solution-class pairs,
ready for `/evolve-solution` Stage 4 as a seeded variant field.

---

## Engine 3 — Anomaly-First Discovery

**When to use:** you observed something that breaks the model, but you do not
know WHY yet. The anomaly is the starting point, not the hypothesis.

Standard discovery: H → test → anomaly or confirmation.
Anomaly-first: anomaly → inference → what must be true for this to exist → H.

**Protocol:**

```
Step 1 — Describe the anomaly precisely:
         "In context [C], under conditions [A], the model predicted [X]
          but observed [Y] with magnitude [Z]."

Step 2 — Enumerate possible causes:
         For each cause: is it consistent with ALL other known observations?
         Kill causes inconsistent with prior confirmed data.

Step 3 — For surviving causes: find the most differentiating test.
         A test differentiates when its result is different under different
         causes. A test that gives the same result under all surviving causes
         is not informative — discard it.

Step 4 — Run the differentiating test. Update surviving causes.
         Repeat until one cause survives → that is the hypothesis.
```

**Evidence discipline:** the anomaly-first result is `[INFERRED]` until
confirmed by a test designed before seeing the anomaly's explanation. Explaining
an anomaly post-hoc is not [VERIFIED].

---

## Engine 4 — Exhaustion Mapping

**When to use:** the solution space is finite and enumerable, and you want to
map what is NOT possible before committing to what IS. Null results as
positive information.

**Protocol:**

```
Step 1 — Define the solution space boundaries:
         (a) what is the complete set of mechanism types that could work?
         (b) what are the axes of variation (scale, direction, scope, timing)?
         (c) are there theoretical impossibilities within the space?

Step 2 — Map already-killed regions:
         Read null_results/INDEX.md.
         For each REJECT entry relevant to this space:
         what exactly was ruled out? (use Kill Analysis, not just the verdict)

Step 3 — Build the exhaustion map:
         [ mechanism type ] → [ killed | unknown | alive ]

Step 4 — Identify the smallest alive region:
         "What remains unexplored after removing the killed regions?"
         This is the focused hypothesis space for the tournament.
```

**Termination condition:** when the alive region contains ≤3 mechanism types,
hand off to `/evolve-solution` with a focused variant field.

**Theorem-by-exhaustion condition:** when the alive region becomes empty AND
the boundary conditions are verified → this IS a null result that proves
impossibility. This is the strongest possible null result. Document it as
such in `null_results/` with evidence level `[VERIFIED-REAL]` if the
exhaustion was complete.

---

## Routing: when to use which engine

| You have | Use |
|---|---|
| A working model with residuals | Engine 1 (Orphan Data Miner) |
| A failed approach, unknown which assumption blocked it | Engine 2 (Constraint Relaxation) |
| An anomalous observation without a cause | Engine 3 (Anomaly-First) |
| A known finite space to map | Engine 4 (Exhaustion Mapping) |
| No model, no anomaly, no space structure | Stop. Use Mode B (Research) first. |

---

## Integration with the Core

```
Narrow Discovery Engine
       ↓
Produces: hypothesis candidates (Engines 1–3) or exhaustion map (Engine 4)
       ↓
Route to /evolve-solution Stage 1 (Intent Card):
       - hypothesis candidate → becomes a variant in Stage 4
       - exhaustion map → constrains the variant field in Stage 4
       OR
Route to null_results/ directly (Engine 4 exhaustion result)
```

---

**Status:** ACTIVE — pre-pipeline discovery engines for `/evolve-solution`.
**Position:** runs BEFORE Stage 1 (Intent Card) or as standalone discovery.
**Produces:** hypothesis candidates → feed into tournament, or exhaustion maps
→ constrain tournament, or proven null results.
**Does not replace:** the standard falsification pipeline — it populates the
input to the pipeline when the hypothesis is not yet known.
