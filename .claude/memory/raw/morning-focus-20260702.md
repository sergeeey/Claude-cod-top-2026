# Morning Focus - 2026-07-02

## 🐸 A1 Task (eat the frog first)
**Merge + push `fix/readme-metrics-match-ci-actuals` (7c5d388) to main and verify CI goes green.** The CI has been broken across 3 layered bugs this session (ruff version drift → README badge hardcoding → hook count miscount). The final fix is committed locally but NOT yet merged or pushed. Until this lands on main and CI turns green, the project cannot accept new PRs and all further work is blocked. Run: `git checkout main && git merge fix/readme-metrics-match-ci-actuals && git push origin main`, then re-check GitHub Actions.

## Top-3 Priority
1. **Merge + push CI fix to main** — SIGNAL: green CI is the gate for all downstream work. The branch `fix/readme-metrics-match-ci-actuals` (7c5d388) has the third and final README fix (hooks 86→85, tests 1681→1677, coverage 76%→75% to match CI's own numbers). Until this hits main and GitHub Actions confirms green, the repo is in a broken state. Skipping = CI stays red indefinitely.
2. **Pin ruff version in pyproject.toml** — SIGNAL: root cause of the CI regression that consumed the entire 2026-07-01 session was local ruff 0.3.2 vs CI's unpinned (0.15.20+). If not fixed, the same class of failure will happen again silently. Action: add `ruff>=0.15.20` (or exact pin) to `[dev-dependencies]` in pyproject.toml, document in LESSON block.
3. **Validate install.sh on 2nd machine** — SIGNAL: Scope Fence "Done when" = install.sh works on three machines. One confirmed (live ~/.claude updated 2026-07-01). Two remain. Project cannot be declared done until this is verified. Action: spin up a fresh container, run `bash install.sh --profile=standard --non-interactive`, confirm 0 failures and commands/+redact.py present.

## Ignore Today
- **Coverage gap (75%→86%)** — Real goal, but premature. CI must be green first; coverage work on a broken main is wasted. Also, the "86%" number in the Scope Fence may have been a pre-regression target — re-baseline after CI is confirmed green.
- **New skills/hooks/features** — Harness is feature-complete per Scope Fence. Scope Fence explicitly says "NOT NOW: GUI, web dashboard, SaaS, marketplace". Don't add until CI green + install.sh 3-machine validation done.
- **Distribution sprint / Show HN** — mcp-bouncer is live on PyPI, but the repo CI is currently broken. Don't promote while the project health is fragile — optics risk.
- **Obsidian graph resets / cosmetic config** — Zero leverage on Scope Fence criteria.

## SNR Score yesterday: 1/10
(Source: evening-snr-20260527.md — most recent file available. 2026-07-01 session had very high activity but no evening SNR file recorded. Pattern: CI debugging consumed the day reactively. Root cause was toolchain drift, not poor planning — but the layered CI failures suggest insufficient pre-push checklist discipline.)

#morning-focus #focusos #tracy #snr
