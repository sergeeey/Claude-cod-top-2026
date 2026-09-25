# Morning Focus - 2026-09-25

## 🐸 A1 Task (eat the frog first)
Push test coverage from 84% → ≥86%: run `pytest --cov --cov-report=term-missing`, identify the lowest-coverage modules, write targeted tests, push a PR, confirm CI green at the stated Done-when gate. This has been the persistent A1 since June 2026 and the repo still reports 84% (as of PR #364, 2026-09-05). Every session that ships hook features while this gate remains unmet adds more debt to the same frog.

## Top-3 Priority
1. **Coverage ≥86%** — Signal: this is literally the repo's "Done when" completion criterion (CLAUDE.md). At 84% it is 2 points below the gate. Adding more hook features (PRs #466-#472 all merged since) while the done-criteria remain unmet is structural noise, not progress toward shipping.
2. **Semantic search fusion decision** — Signal: the evidence layer's own measured Δ has degraded from the PR-5 acceptance bar (+0.125 → +0.062). Concrete mechanism is verified: PR-5's unconditional dense top-up evicts correct keyword hits (q18 case). Owner needs a clear recommendation (leave as-is vs. skip top-up when keyword already has a hit) to decide. Every session this stays open, the evidence layer operates below its declared quality standard.
3. **Verify `fix/check-global-hooks-machine-dependent-test` PR status** — Signal: commit `f04f980` was made 2026-09-04 but flagged "not yet PR'd". Three weeks have elapsed; either it was quietly lost or needs a PR. One quick `git log --oneline origin/main | grep check-global` confirms if it was squash-merged; if not, open the PR now — the fix is real and verified.

## Ignore Today
- **§8 hypothesis-arbiter work** — owner-decision-gated ("waiting on the owner to name a concrete hypothesis"). Building scaffold without a target hypothesis is gold-plating. Check back when the owner names one.
- **/release-scout weekly schedule** — explicitly marked owner opt-in in activeContext.md. Not mine to arm unilaterally.
- **New hook feature additions** — the last 7 PRs (#466-#472) all added hook features. Continuing that direction while coverage < 86% and the evidence-layer Δ gap is open is noise relative to the stated A1 and §5.3 quality bar.
- **ANTHROPIC_API_KEY refresh** — owner's credential, not mine to touch.

## SNR Score yesterday: 2/10
(From `evening-snr-20260729.md` — most recent evening file; no evening SNR logged between 2026-07-29 and today)
Score: 2/10, REACTION mode. Coverage A1 was not advanced. Multiple parallel off-plan streams ran instead of single-threaded A1 execution. Pattern: reactive hook fixes crowd out the structural coverage work.

#morning-focus #focusos #tracy #snr
