# Morning Focus - 2026-05-27

## 🐸 A1 Task (eat the frog first)
**Close the coverage gap: hooks+scripts 77% → ≥86%** — run `pytest --cov=hooks --cov=scripts` to identify uncovered paths, write targeted tests, and push CI to meet the Scope Fence "Done when" threshold.

## Top-3 Priority
1. **Coverage: 77%→86% (hooks+scripts)** — Signal. This is the only "Done when" criterion actionable in this environment. CI shows ~81% full, but hooks+scripts layer sits at 77%. Delta = 9pp. Every test written here directly unblocks project completion.
2. **EstimandOps integration test verification** — Signal. activeContext shows validate_experiment.py was extended (REQUIRED_YAML_FIELDS, check_yaml_estimand_fields, --estimand flag) in [2026-05-16] session. Confirm these new code paths are covered in tests/test_validate_experiment.py and not creating a coverage dead zone.
3. **Delegate to user: install.sh on sboi** — Signal (for Scope Fence), but requires physical 3rd machine. Write a one-liner reminder in activeContext that the only remaining gate is user-side: `bash install.sh --profile=standard --non-interactive` on sboi.

## Ignore Today
- **graph.json colorGroups (Obsidian)** — C-level. Cosmetic/UX, no project consequence, requires Obsidian to be closed. Zero leverage vs coverage goal.
- **"merge PR #57"** — Eliminate. This carried note is stale — PR #57 is confirmed merged in Recent Merges list. Remove from mental backlog.
- **GUI / web dashboard / SaaS** — Explicitly outside Scope Fence (NOT NOW). No discussion.
- **New features / hooks beyond current 58** — Noise until "Done when" gates are met.

## SNR Score yesterday: N/A
(No evening-snr-*.md files found in raw/ — this is the first triage run of the project)

## Context Snapshot
- Tests: 1304 passing | Hooks: 58 active | Open PRs: 0
- Coverage: hooks+scripts 77% | CI/Linux 81% | Target: ≥86%
- Scope Fence status: CI ✅ | Coverage ❌ (gap) | install.sh 3rd machine ⏳ (user-side)
- Version: 3.8.0 | Branch: main green ✅

#morning-focus #focusos #tracy #snr
