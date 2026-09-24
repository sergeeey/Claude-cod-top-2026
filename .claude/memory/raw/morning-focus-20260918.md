# Morning Focus - 2026-09-18

## 🐸 A1 Task (eat the frog first)
**Push coverage from 84% → 86%**: run `pytest --cov --cov-report=term-missing`, find the
lowest-coverage modules, write targeted tests, push branch, confirm CI green at ≥86%.
This is the explicit "done-when" condition in the Scope Fence. It has been the frog since
2026-06-10. The last 7 PRs (#333–#364) cleared all known blockers — the runway is clean.

## Top-3 Priority
1. **Coverage ≥86% push** — Signal: explicit project done-condition; every day it stays at 84% is a day the project is not shippable. No new discovery needed; just run the cov command and write the tests the output names.
2. **Open PR for test_check_global_hooks.py fix** — Signal: the machine-independent fix was committed 2026-09-04 (fix committed, not yet PR'd per activeContext). One dangling commit blocking a clean `main`. Takes < 10 minutes once coverage work has set the context.
3. **Owner check-in on semantic search fusion decision** — Signal: Observed−Floor delta shrank from +0.125 to +0.062 on the now-cleaner 76-file corpus; root cause is verified (q18 case: PR-5's unconditional semantic top-up evicts a correct keyword hit). Data is in hand, decision is not. Raise the concrete options: (a) leave as-is — still net-positive; (b) guard: don't let dense top-up evict an existing keyword hit. Owner decides, not the agent.

## Ignore Today
- **§8 hypothesis-arbiter work** — blocked: owner hasn't named a concrete hypothesis/subject. Building infrastructure without a target is Noise. Do not start until owner names the first hypothesis.
- **ANTHROPIC_API_KEY rotation** — owner's credential, not ours to touch.
- **/release-scout weekly scheduling** — C task, no consequence if deferred. Noise vs the coverage frog.
- **Badge/README admin** — low-leverage admin. Only touch if coverage push lands and CI syncs the badge automatically.
- **CogniML/`populate_vault.py` follow-ups** — pearl_registry items with explicit next-check 2026-10-04. Not now.

## SNR Score yesterday: 2/10 (last logged: evening-snr-20260729.md)
No evening-snr since 2026-07-29 (50 days). The absence of the evening accountability anchor
likely contributed to the multi-week coverage avoidance. Consider re-enabling the evening-snr
scheduled task after today's A1 is done.

#morning-focus #focusos #tracy #snr
