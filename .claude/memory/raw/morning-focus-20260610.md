# Morning Focus - 2026-06-10

## 🐸 A1 Task (eat the frog first)
**Close the coverage gap: 81% → 86% CI coverage** — add targeted tests for uncovered hooks/scripts paths until `pytest --cov` on CI hits the ≥86% gate. This is the single explicit blocker in the Scope Fence "Done when" criteria.

## Top-3 Priority
1. **Coverage 81% → 86%** — SIGNAL: the project's "Done when" gate is unambiguous (coverage ≥ 86%). At 81% CI we are 5pp short. Every session that doesn't close this is a day the project stays in "almost done" limbo. Concrete: run `pytest --cov --cov-report=term-missing`, find the top 3 uncovered modules, write tests for them.
2. **Validate install.sh on a 2nd machine** — SIGNAL: "Done when: install.sh works on three machines" — one is confirmed, two remain. Without this the distribution story is unverified. Concrete: spin up a fresh container, run `bash install.sh --profile=standard --non-interactive`, confirm zero failures.
3. **Verify feature/elite-athlete-upgrade landed cleanly on main** — SIGNAL: activeContext.md shows the branch was pushed 2026-05-31 with PR URL `/pull/new/` (never formally opened), but git log shows #131 as the latest merge. Either confirm the work is in main or open + merge the PR today before it drifts further.

## Ignore Today
- GUI / web dashboard / SaaS ideas — explicitly out of scope in Scope Fence ("NOT NOW")
- New skill/hook additions beyond coverage needs — harness is feature-complete; don't add until coverage gate is cleared
- Marketplace/plugin publication prep — premature until install.sh passes on 3 machines
- Review-squad or cross-domain feature extensions — #129–#131 just shipped; let them settle before piling on

## SNR Score yesterday: 1/10
(Source: evening-snr-20260527.md — no morning focus declared on 2026-05-27, entire day structurally unplanned, zero commits, defaulted to reactive mode. Root cause: missing morning intent-setting. Today's morning-focus file IS the fix.)

#morning-focus #focusos #tracy #snr
