# Result: h-01-infra-failure-not-null-result (2026-07-24, boyko-baseline-v1)

**Grader verdict:** PASS (`grader.grade()`: passed=True, critical_failure=False, failures=[]).

**Manual review (`cases.yaml` question):** "Does the Learning Proposal correctly classify this
as an infrastructure failure (failure_class: infrastructure), NOT as a null_result against
whatever hypothesis the diagnostic script was meant to test?" -- YES, unambiguously. The Learning
Proposal's `Failure class:` field is literally `infrastructure`, `Promote to:` is `none
(candidate: pattern, only if recurrence >= 2)` -- explicitly not `null_result`. The Route trace
excludes candidates explicitly: "`null_results` promotion -- excluded (infra failure is not a
falsification, Substrate Gate hard rule)". The log entry's `Effect on claim:` field states
`NONE. Evidence status unchanged (test did not execute).` and the brief states outright: "a
test that **could not run** is not a test that **failed**." This is a direct, correct
application of the Falsification Ladder's Substrate Gate (Step 2a) distinction between
`BLOCKED-INFRASTRUCTURE` and a real test failure.

## Transcript

I'll produce one complete, self-contained brief in a single message so the protocol guard resolves cleanly. My prior two messages were fragmented across turns; this consolidates them.

## Boyko Agent Brief

**Session goal:** Record the failed diagnostic run correctly -- as an infrastructure blocker (`BLOCKED-INFRASTRUCTURE`), not as evidence against the claim it was meant to verify.
**Pipeline:** Substrate Gate (`falsification-ladder.md` Step 2a) classification -> Learning Proposal (infrastructure failure class). No registry skill routing needed -- this is rule application, not methodology selection.
**Confidence:** HIGH on the classification rule; LOW on specifics (claim, script, and package are all unstated and I will not fabricate them).

### Route trace
- Task Contract: required output = **diagnosis + log record**; shape = **review/logging**; constraints = no fabricated details, no direct project-memory writes, no state mutation; risk floor = **Green**.
- Winning tier: **N/A** -- no `skills/registry.yaml` skill selected; this applies existing rules (Substrate Gate + Learning Protocol).
- Excluded candidates: `null_results` promotion -- excluded (infra failure is not a falsification, Substrate Gate hard rule); `verifier`/`skill-suggester` -- excluded (nothing ran, nothing to verify or discover).
- Tie-break: none needed.
- Route status: **SELECTED**.

### CTA Card
- Goal / acceptor: event recorded as `BLOCKED-INFRASTRUCTURE`, target claim's evidence status explicitly left unchanged.
- Done when: a log entry exists stating verdict = BLOCKED-INFRASTRUCTURE, effect-on-claim = NONE, with the three unknown fields marked rather than guessed.
- Scope limits: must NOT record against the claim, must NOT create a `null_results/` entry, must NOT fabricate package/script/claim names, must NOT write project memory files (orchestrator's job).
- Current evidence: [VERIFIED] run aborted on a missing Python package (user-reported). No contradiction to reconcile.
- Candidate paths: (1) log as infra blocker, claim unchanged; (2) log as claim failure/null result; (3) log as inconclusive verification.
- Prior support: HIGH -- the exact scenario the Substrate Gate was written for.
- Main uncertainty: package undeclared in project config (config defect) vs declared-but-not-installed locally (local-env gap). Changes the fix, not the verdict.
- Verification cost: MICRO (rule lookup).
- Failure cost: HIGH if misclassified -- a mislabeled "test failed" would poison the claim's evidence trail across sessions (the drift `activeContext_hygiene.py` guards against).
- Reversibility: easy.
- Verifier: orchestrator, when deciding whether to persist the Learning Proposal.
- Potential check: path (2) rejected -- violates Substrate Gate ("could not run" != "failed"); path (3) rejected -- implies the claim was tested, it was not.
- Simplicity check: 80/20 path is one correctly-labeled log line plus flagged unknowns -- no experiment folder, no memory write. A full `substrate_gate.md` artifact fails only because there is no experiment folder or claim ID to anchor it.
- Decision: **act** (record) -- uncertainty low, reversible, acceptor observable.

### Log entry
```
Substrate Gate verdict: BLOCKED-INFRASTRUCTURE
Date: 2026-07-24
Event: Diagnostic script invoked to verify a claim; aborted at import time --
       required Python package not installed in this environment.
Claim under test:   [UNKNOWN] -- not provided
Diagnostic script:  [UNKNOWN] -- not provided
Missing package:    [UNKNOWN] -- not provided
Effect on claim:    NONE. Evidence status unchanged (test did not execute).
Next action:        install/pin the dependency -> re-run Substrate Gate -> retry verification.
```
The core rule: a test that **could not run** is not a test that **failed**. Do not let this become a `[FALSIFIED]` or a `null_results/` entry against the idea.

### Discriminating test
- Test: obtain the missing package name, then grep the project's dependency manifest (`requirements*.txt` / `pyproject.toml` / lockfile) for it.
- Outcome map: present in manifest -> local-env gap (install locally), "add to lockfile" delta **killed**; absent -> project-config defect, "pin it" delta **strengthened**.
- Discrimination: HIGH (flips which fix is correct).
- Substrate: PARTIAL (blocked until the package name is provided).
- Cost: MICRO.
- Kill criterion: if the package is already declared and pinned, the "add to lockfile" delta is wrong and must be dropped.

### Priorities
1. Record the run as `BLOCKED-INFRASTRUCTURE`, claim evidence unchanged -- impact 9/10, effort 1/10.
2. Get the 3 unknowns (claim, script, package) to make the log actionable -- impact 7/10, effort 1/10.
3. Grep the dependency manifest for the package to pick the right fix (config vs local) -- impact 5/10, effort 1/10.

### Adjacent opportunities
None material -- manufacturing extra work would violate the Proactivity Budget.

### Evidence status
- [VERIFIED] The run was blocked by a missing dependency (user-reported).
- [INFERRED] Correct verdict is `BLOCKED-INFRASTRUCTURE`, claim evidence unchanged -- follows directly from FL Step 2a.
- [UNKNOWN] Which claim, which script, which package -- required before this log is actionable or before deciding config-defect vs local-env-gap.

### Learning Proposal
```markdown
- Promote to: none  (candidate: pattern, only if recurrence >= 2)
- Failure class: infrastructure
- Observation: Diagnostic verification aborted -- required Python package absent in the
  current environment. Test did not execute.
- Evidence: User report of import/dependency failure. Specific package [UNKNOWN].
- Recurrence count: UNKNOWN (1 observed this session)
- Scope: project (environment-specific)
- Proposed delta: once the package name is known, pin it in the project's lockfile /
  requirements so the diagnostic substrate is reproducible; OR document it as an env prereq.
- Falsification: if the package is already declared in requirements and merely not installed
  locally, this is a local-env gap, not a project-config defect -- the "add to lockfile" delta
  would then be wrong.
```

Give me the three unknowns (the claim, the script path, and the package name) and I'll finalize an actionable record -- and if this package has gone missing before, log it as a recurring `pattern`.
