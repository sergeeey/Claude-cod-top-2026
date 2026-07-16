# Route trace — scientific-hypothesis (B2, executable architectural coherence)

**Claim:** the `scientific-hypothesis` route is machine-connected end-to-end — every capability
it selects resolves to a real skill that provides it, a verifier gates the result, and the
outcome has a memory sink and a failure sink.

**How this was produced (reproducible):**
```
python scripts/resolve_route.py --task-type scientific-hypothesis --out route.json
python scripts/check_architecture.py --check   # exit 0 = all gates green
```

`route.json` is the machine-readable route artifact. It is not hand-written — it is *resolved*
from `architecture/workflows/scientific-hypothesis.yaml` against `skills/registry.yaml`, and the
resolver refuses to emit an artifact whose workflow/capability/verifier/sink does not exist.

## The resolved route

| # | Skill (exists on disk) | Capability (in its `provides`) | Role |
|---|---|---|---|
| 1 | routing-policy | task.route | classify + attach mandatory safety floor |
| 2 | claim-decomposer | claim.atoms | decompose hypothesis → atomic claims |
| 3 | estimand-bridge | estimand.criteria | MCID/ICE/endpoint → go/no-go criteria |
| 4 | sci-hypothesis | hypothesis.candidates | competing hypotheses + falsification criteria |
| 5 | hypothesis-arbiter | ranked_hypotheses | Chamberlin/Platt strong inference |
| 6 | **skeptic** | falsification.verdict | **verifier** — context-blind adversarial gate |

- **Rejected alternatives (with reasons):** consilience, sci-evidence, proof-ladder — adjacent
  evidence capabilities, not on this route's critical path.
- **Gates:** falsification-ladder(rule), source_trace, safety_floor_check.
- **memory_sink:** `experiments/` · **failure_sink:** `null_results/`
- **Safety floor (from `hooks/routing_floor_classifier.py`, single source):** RESEARCH tier →
  mandatory EstimandOps L0 gate first. The resolver reuses the hook's tier table, so what is
  shown here is exactly what the hook injects — no divergence.

## What this does NOT prove

- It does **not** prove the pipeline produces *correct science* — only that the wiring is
  consistent and complete. Correctness is the job of the skills themselves + the skeptic gate.
- One route proven ≠ the pattern generalizes. Generalization is tested only when a second
  workflow (`release`) is added under the same schema (plan Phase B4).
- No runtime/telemetry evidence: this is design-time structural verification (same honest scope
  as `docs/architecture-coupling/`).

**Verdict:** the invariant is now executable and regression-protected —
`scripts/check_architecture.py --check` runs in CI, and `tests/test_architecture.py` mutation-tests
that the checker actually fails when a dependency, verifier, termination condition, or
registry↔workflow link is broken.
