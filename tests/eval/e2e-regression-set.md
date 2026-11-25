# End-to-end regression set (draft, 2026-11-25; no paid run has been made)

Purpose: decide objectively whether the whole system got better or worse after a significant change
(skills, hooks, rules, routing, memory, self-optimization). It reuses what already exists: real fix
commits of this repository with their own tests, the existing TC format and `run_eval.sh`, the
`benchmarks/` pilots, `check_architecture.py` and the unit tests. It adds a specification, not a
runner or a stand. Intermediate numbers (skill activations, Hit@k, passed checks, fewer hook blocks) are
never the target: a change is judged by task outcomes, cost and the guard conditions below.

## How a configuration is compared

Same tasks, same budgets, same grader, two configurations: the frozen baseline and the candidate.
Configuration under test = a recorded git SHA of this repository plus the checksum of the live skill
corpus (`snapshot_state.py`), applied through a project-local `.claude/` or a `--settings` overlay in an
isolated copy. Isolating the whole user config with `CLAUDE_CONFIG_DIR` has NOT been verified in this
environment; verify it once before relying on it. Each task is run at least 3 times per configuration
because model output varies; outcome per task = pass fraction, not a single run.

## Result states (never collapsed into pass/fail)

| State | Meaning |
|---|---|
| confirmed | the objective criterion passed and the independent check agrees |
| partly confirmed | some criteria pass, listed which |
| defect found | a criterion fails or a regression guard trips; recorded with the artifact |
| insufficient evidence | too few runs, an ambiguous criterion, or a broken run (infrastructure failure is not evidence against the claim) |
| needs independent or human check | no objective criterion exists for this part |

## Guards that every comparison reports, whatever the target

false recommendations or needless procedures added, context and token cost, wall time, user
interventions needed, regressions on tasks that passed before, loss of discoverability of other
skills, compatibility of existing calls, data-protection checks still in force. A candidate that
improves a target and worsens a guard is reported as a trade-off, not as an improvement.

## Held-out discipline

Tasks marked `dev` may be used while designing a change; tasks marked `held-out` are only run to
decide. The held-out criteria and any ground truth stay outside the repository (a hash of each is kept
here). A publicly disclosed key is never held-out. This covers every real fix commit: the repository
is public, so the fix and its test can be read by anyone. A plain archive of the parent tree without
`.git` only keeps the test out of the workspace; it does not make the task held-out.

## Tasks

Common rules for the five coding tasks C1-C5: initial state = `git archive <parent>` of the listed
commit (no history); the agent gets only the problem statement; the criterion is the test file of the
fix commit laid over the result; the check was verified on 2026-11-25: parent tree with the commit's
tests fails, fix tree passes. Permitted actions: edit files under `hooks/`, `scripts/`, `tests/` of the
archive, run tests, read files; no network, no git history, no deleting or weakening tests.
Budget (proposal, to be calibrated by 3 unpaid dry reads of past sessions, not by running): at most 40
tool calls, 15 minutes, 300k tokens.
Independent check: the hidden tests must pass and the full suite of the archive must show no failure
that the parent tree does not have (see Readiness); a reviewer reads diffs as sampled below, and any
existing test edited by the agent is a defect.

| ID | Domain | Split | Initial state and statement (from the commit message) | Objective criterion | Fix commit / parent / hidden test sha256 (first 12) |
|---|---|---|---|---|---|
| C1 | coding | dev | `independence_scorer` writes `key:` without a space for an empty YAML value | commit's `tests/test_independence_scorer.py` passes | `ad9671a` / `36fa964` / `adda80e8f779` |
| C2 | coding | dev | `mentor_nudge` must exempt Speed Mode prompts from the TIP/lesson reminder | `tests/test_learning_hooks.py` passes | `278bc52` / `ef5be27` / `ede4882ae63b` |
| C3 | coding | dev | `locality_escalation_guard` state must anchor to the git root, not the working directory | `tests/test_locality_escalation_guard.py` passes | `e210d21` / `a589dbe` / `edb53a9692ec` |
| C4 | coding | dev (public fix; was held-out) | `resource_router` matches the bare homograph token/токен | `tests/test_resource_router.py` passes | `e130a1f` / `45f494a` / `cd1f5fa4e8ee` |
| C5 | coding | dev (public fix; was held-out) | a CI job name `secrets-scan` must not be read as a dangerous command by `permission_policy` | `tests/test_permission_policy.py` passes (at the parent it errors at collection) | `cd0fe91` / `ab48154` / `f4421b2d135e` |
| D1 | data analysis | dev | a seeded synthetic table with a planted effect of known size and a planted confounder (generated by a fixed seed; label `[VERIFIED-SYNTHETIC]`, valid for regression, never for hypothesis validation) | reported effect within the stated tolerance of the planted one; confounder named; causal wording absent when the question class is descriptive | to be generated; seed and tolerance fixed before any run |
| T1 | telemetry | dev | transcript fixtures of `tests/test_skill_usage_report.py` plus a candidates log; ask for slash, model and failed counts | counts equal the expected JSON of the existing test fixtures | existing fixtures |
| R1 | research | dev | `benchmarks/sci-code-audit` pilot. Its ground-truth key is marked `PUBLICLY_EXPOSED` (2026-11-18) and the per-object verdicts are published, so it is development / content regression only and must NOT decide whether a candidate configuration is better. A held-out research task needs fresh sealed objects, not yet prepared | matches the pre-registered scoring of that pilot (regression signal only) | existing pilot; no held-out research task exists yet |
| R2 | research | dev | 10 short statements; classify Descriptive / Predictive / Causal under the EstimandOps L0 rule | agrees with a key written before the run; no causal wording on non-causal items (TC-style `not_contains`) | key kept outside git |
| A1 | architecture change | dev | register a new skill in `skills/registry.yaml` (kind, maturity, capability) with a SKILL.md | `check_architecture.py --check`, `gen_hook_matrix.py --check`, `sync_doc_counts.py --check`, `tests/test_structure.py` pass; no unrelated file touched | existing gates |
| E1 | error recovery | held-out | a seeded settings fixture whose hook path is wrong and a stale state file | the hook runs again and the guard reports clean; the state file is backed up, not silently deleted | to be seeded; criterion fixed before any run |
| E2 | error recovery | dev | the C-tasks with an extra seeded failing import | the agent finds the root cause rather than weakening a test | hidden tests as above |

Open gap: the set has no held-out research task until fresh sealed objects are prepared; until then research changes are judged on human review (R2 has no key yet, see Readiness), and are reported as insufficient evidence for a held-out decision.

Existing assets this set sits on: `tests/eval/TC-001..010` and `run_eval.sh` (text assertions through
`claude -p`: paid when run), `benchmarks/*/run-*` (recorded dogfood runs), `skills/lifecycle_tests`
(content regression), `experiments/*/decision.md` (recorded decisions), and
`scripts/regression_oracle.py` for the oracle side of C1-C5.

## Running C1-C5

```
python scripts/regression_oracle.py selfcheck                 # oracle fails on parent, passes on fix
python scripts/regression_oracle.py prepare C1 <empty dir>    # workspace without history
python scripts/regression_oracle.py --out runs.jsonl check C1 <dir> --full --run-meta meta.json
```

The script never starts a model. `check` requires positive evidence, not the absence of failures:

- control: the hidden test must pass on the fix commit on this machine, otherwise the result is
  `insufficient evidence` (a scope violation is reported as `defect found` first, whatever the control);
- the graded tree is the parent commit plus the candidate's `hooks/` and `scripts/` changes; the
  candidate's test files and root files are listed but never executed;
- editing or deleting an existing test, adding test or import configuration, or changing anything
  outside `hooks/ scripts/ tests/` is a defect;
- every test that passes in the control must pass in the hidden run; with `--full`, every test outside
  the hidden module that passes on the parent tree must still pass (a skip, a removed test or a
  collection error counts as a defect; a flaky test can cause a false one, so rerun before concluding).

Without `--full` a pass is only `partly confirmed`. Exit codes: 0 confirmed, 1 defect, 2 usage error,
3 partly confirmed, 4 insufficient evidence (including a failure of the oracle itself). `--run-meta` stores a JSON about the agent run as given:
model, configuration SHA and corpus checksum, wall time, tokens, cost, tool calls, user interventions.
The oracle needs Python 3.11.4 or later (safe tar extraction); older versions exit 4, not 1.
`tests/eval/results/` is not ignored by git: exclude it by hand when staging.
Files that the candidate's own runs create outside `hooks/ scripts/ tests/` count as scope violations.
Candidate code runs on the grading machine with no sandbox, so it could still deceive the grader on
purpose; the guards cover mistakes and test or configuration edits, not hostile code.

## Readiness (checked 2026-11-25, no model was run)

"Oracle executed" means the criterion was actually run here, not only described.

| ID | Oracle executed | What blocks a comparison | Usable as held-out |
|---|---|---|---|
| C1 | yes: parent 1 of 85 fails, fix passes [VERIFIED] | paid agent run; leakage (below); statement describes the defect, not the required behaviour | no |
| C2 | yes: parent 5 of 55 fail, fix passes [VERIFIED] | same | no |
| C3 | yes: parent 1 of 26 fails, fix passes [VERIFIED] | same | no |
| C4 | yes: parent 1 of 30 fails, fix passes [VERIFIED] | statement describes the defect, not the required behaviour | no |
| C5 | runs, but not a fair criterion: parent fails at collection [VERIFIED] | hidden test imports `NEUTRAL_CI_JOB_NAMES`, a name the statement does not give, so a correct fix with other names fails [VERIFIED] | no |
| D1 | no | specification only: no generator, seed or tolerance | not applicable (dev) |
| T1 | no | expected values are assertions inside the test file; no standalone fixtures or expected JSON [VERIFIED] | not applicable (dev) |
| R1 | no (manual scoring) | key publicly exposed | no |
| R2 | no | 10 statements and key not found by file name in the places checked [UNKNOWN] | not applicable (dev) |
| A1 | gates run | all four gates pass on an untouched tree, so the criterion does not detect that nothing was done; no skill is named [VERIFIED] | not applicable (dev) |
| E1 | no | fixture not seeded | no, until seeded outside git |
| E2 | no | failing import not seeded | not applicable (dev) |

### Excluded from configuration decisions (2026-11-25)

C5 and A1 are kept as development tasks with known limitations. They are not used in any decision
about whether one configuration is more effective than another. C5: the hidden test requires
`NEUTRAL_CI_JOB_NAMES`, which the statement does not give, so a correct fix with other names fails.
A1: the four gates pass on an untouched tree, so the criterion cannot detect a missing change. Neither
is fixed now; the 12-task set is not brought to a perfect state, and no decision waits on it.

Full-suite comparison, run once (C1 with the fix applied, 2026-11-25): the parent tree itself has 4
failing tests of 4460 on this Windows machine; the candidate had no new failures; one pytest run took
6-7 minutes [VERIFIED]. Two of the four need git history and pass once the tree is a repository with
one commit; the other two still fail there: a skill-staleness assertion and a session-start protocol
test [VERIFIED]; why they fail (date, platform or other) is [UNKNOWN]. "The full suite passes" is
therefore not reachable in an archive tree: the criterion is "no failure that the parent tree does not
have on the same machine and day". Not run for C2-C5. One `check --full` runs the suite twice, about
13 minutes.

Held-out tasks usable today: none. Until at least one exists, no result of this set can decide that a
candidate configuration is better; it can only show regressions on development tasks.

## Constraints on any future agent run

- Leakage: the workspace has no history, but the fixes are also in the public remote, in local clones
  and may be installed under `~/.claude/hooks` (the C5 names are in the live `permission_policy.py`
  [VERIFIED]). A run needs no network and no access outside the workspace; the script does not enforce this.
- Configuration comparison: `CLAUDE_CONFIG_DIR` moves settings, session history and plugins [DOCS:
  code.claude.com/docs/en/env-vars]; sign-in for such a directory and the actual isolation are not
  verified here. `--bare` skips hooks, skills and `CLAUDE.md` and needs an API key [DOCS:
  code.claude.com/docs/en/headless], so it cannot compare those.
- Cost: `claude -p --output-format json` reports `total_cost_usd` as a client-side estimate [DOCS, same
  page]. A `-p` run has no user to intervene; interventions can only be counted in interactive runs.
- Until the skill_candidates report of 2026-12-02, an agent run that uses the live configuration would
  add its sessions to the observation window. Do not run one.
- Reproducibility: the oracle uses the current interpreter and packages (checked with Python from the
  local environment; CI uses 3.11 and 3.12). Each record stores the Python version and platform.

## Independent verification sampling

Ordinary tasks: 5-10% of runs get a second, independent check when a suitable method exists, never less
than 2 per configuration compared. A model reviewing a model is a second opinion, not independent
evidence; preferred checks are external tests, reproducible computations, concrete artifacts and
objective criteria. Critical tasks (security, data protection, anything irreversible): depth is set by
the cost of an error, not by a sample.
