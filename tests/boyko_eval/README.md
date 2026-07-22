# Boyko Agent Eval Suite — design and honest scope

This is a **scoped MVP slice** of a much larger evaluation-suite proposal (2026-07-22,
"Boyko Evaluation Suite", 8 categories A–H, 40–50 scenarios, A/B/ablation testing,
shadow/controlled/normal rollout modes, persistent task-state directories). That full
proposal is not built here. What's built: the highest-value slice, plus an honest map of
what's deferred and why.

## What this actually is

- `cases.yaml` — 10 scenarios (not 40–50) across the 5 categories judged highest-value
  first: **F** (safety/scope — critical-fail category, zero tolerance, 3 scenarios), **D**
  (reconciliation — the protocol added to `agents/navigator.md` this session, previously
  unproven except by one informal dogfood run, 2 scenarios), **B** (goal understanding /
  ambiguity-gate, 2 scenarios), **A** (skill routing, 2 scenarios), **H** (learning
  proposal, 1 scenario). Categories C (delegation fan-out), E
  (infrastructure-vs-hypothesis-failure), and G (long-horizon/20-40 event drift) are
  not represented at all yet — deferred, not forgotten.
- `grader.py` — a **deterministic, pure-text analyzer**. It checks structural and
  pattern-level properties of a recorded boyko-agent transcript (required Output Format
  sections — reused from `hooks/boyko_protocol_guard.py`, not reimplemented; CTA Card
  acceptance-gate fields; evidence-label presence; forbidden-action-claim patterns;
  destructive-action mentions; outcome-map/kill-criterion presence).
  **Current test status (2026-07-22, correction — an earlier version of this README
  overstated this): there is NO committed pytest file for this grader.** A
  `tests/test_boyko_eval_grader.py` was planned but this session's live
  `~/.claude/settings.json` has a standing `Edit(**/test_*.py)` deny rule that blocks
  writing it (a deliberate protection, respected, not routed around). Verification so
  far: (1) an uncommitted, one-off `python -c` smoke script exercising 5 hand-picked
  cases, and (2) an independent `Agent(reviewer)` pass that read the grader and
  **reproduced two real bugs with a tool** (a destructive-action false-positive on a
  compliant safety refusal, and a forbidden-action-claim false-negative on contraction
  phrasing like "I've committed...") that the smoke script's 5 hand-picked cases had
  missed — both bugs are now fixed in `grader.py`, but this is exactly the kind of gap a
  same-session, author-written smoke test can't be trusted to catch on its own (see
  `rules/audit-verification-gate.md`'s Validation Theater Guard). **Do not treat this
  grader as CI-enforced or fully adversarially tested until `tests/test_boyko_eval_grader.py`
  actually exists and runs in CI.**
- `results/` — where real transcripts + grades get recorded when a scenario is actually
  run. Not auto-populated by CI (see below for why).

## What this deliberately is NOT (and why)

**No CI-automated live-agent execution.** Running a scenario for real means invoking
`Agent(subagent_type='boyko-agent', prompt=...)` — that tool only exists inside an
interactive Claude Code session (this one), not inside a `pytest` process or a GitHub
Actions runner. A prior spike this session (see `agents/navigator.md`'s "Phase B1"
history in `activeContext.md`) already found that headless `claude -p` invocation from a
spawned subprocess hits an authentication wall specific to sandboxed sessions — a real,
already-diagnosed environment constraint, not a design oversight here. So: scenarios are
run **on-demand, by whoever has an active Agent-tool session** (the orchestrator, in
practice), and results are recorded manually into `results/`. This grader exists so that
"on-demand" doesn't mean "ungraded" — the deterministic part of scoring is automatic and
consistent even though the invocation step is manual.

**No behavioral/independent-evaluator harness.** The proposal's "independent evaluator +
blind human spot-check + blind baseline-vs-candidate comparison" tier requires either a
second LLM call per scenario (real cost, and this repo's own `rules/skeptic-triggers.md`
context-asymmetry discipline says a evaluator needs a clean context, which again means a
live Agent-tool call) or a human in the loop. Not built. `Agent(reviewer)` was used
manually this session as an ad hoc version of this for the two dogfood runs already
performed against `agents/navigator.md` — that pattern is documented, not automated.

**No metrics scorecard / dashboard.** The proposal's weighted scorecard
(`route_accuracy`, `false_verified_rate`, `goal_drift_rate`, etc.) needs a real corpus of
completed runs to be meaningful — computing percentages over a handful of manually-run
scenarios would be exactly the kind of round-number theater
`rules/skeptic-triggers.md` exists to catch. Deferred until enough real runs accumulate
in `results/` to make a rate meaningful (this repo's own `MIN_RECORDS_FOR_RATE = 5`
convention from `scripts/false_pass_rate.py` is the right precedent to reuse here later).

**No A/B/ablation framework, no shadow/controlled/normal rollout, no persistent
`.claude/state/tasks/<id>/` directories, no Focus Recitation.** All real, all useful
ideas from the source proposal — none are built. Each needs either orchestrator-level
integration (tracking what Boyko recommended vs what actually got executed, across many
real sessions) or a redesigned session-state layer that doesn't exist yet. Building any
of these now, before the 10-scenario grader has even been dogfooded, would be exactly the
"infrastructure around an unproven mechanism" pattern this repo's own
`rules/skeptic-triggers.md` and `rules/doubt-driven-development.md` warn against.

## How to run a scenario today

1. Pick a scenario from `cases.yaml`.
2. Invoke it for real: `Agent(subagent_type='boyko-agent', prompt=<scenario's prompt>)`.
3. Save the raw transcript text.
4. Run it through the grader:
   ```python
   import yaml
   from grader import grade
   cases = yaml.safe_load(open("cases.yaml"))["cases"]
   scenario = next(c for c in cases if c["id"] == "<scenario-id>")
   result = grade(scenario, transcript_text)
   print(result)
   ```
5. Record the transcript + `GradeResult` in `results/<scenario-id>-<date>.json` (or
   similar) if you want it to count toward a future baseline.

## Relationship to `boyko-baseline-v1`

The git tag `boyko-baseline-v1` freezes the `agents/navigator.md` contract this suite
grades against. When the contract changes, re-tag and re-run the corpus rather than
silently comparing new output against an old, undocumented version.
