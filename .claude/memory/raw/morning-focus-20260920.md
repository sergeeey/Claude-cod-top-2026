# Morning Focus - 2026-09-20

## 🐸 A1 Task (eat the frog first)
Run `pytest --cov --cov-report=term-missing hooks/ scripts/`, identify the lowest-coverage
modules, write targeted tests for those gaps, push, confirm CI green at ≥86% coverage.
(Currently at 84%, target ≥86% — this is the Scope Fence "Done when" criterion.)

## Top-3 Priority
1. **Coverage gate: 84% → ≥86%** — SIGNAL: the literal Scope Fence "Done when" criterion;
   unblocks declaring the project production-ready; has been the frog since 2026-06-10;
   every day it stays open is a day the project is technically unshippable.
2. **§8 experimental pack: name and run a real hypothesis** — SIGNAL: the explicitly-chosen
   strategic direction (owner: "B now, A later", 2026-09-02); recent PRs (#465–#470) show
   evaluation infrastructure is ready; the blocker is naming a concrete hypothesis subject
   for hypothesis-arbiter/claim-pipeline — ask the owner for this one datum.
3. **PR the `fix/check-global-hooks-machine-dependent-test` branch** — SIGNAL (small):
   local branch with a fix committed but never PR'd; low cost to close; leaving it open
   creates drift risk (untracked, may conflict on next rebase).

## Ignore Today
- **Semantic search fusion investigation** — below-bar Δ (+0.062) is known but net-positive
  and no measured user impact; investigating without an owner decision is Default Focus Bias.
- **release-scout weekly scheduling** — admin/scheduling, no immediate consequence.
- **ANTHROPIC_API_KEY fix** — owner's credential, cannot act on it.
- **Any new feature or hook work not in the Top-3** — SNR filter: §8 eval infra already
  shipped (#465–#470); adding more infrastructure before running real hypotheses is noise.
- **README/badge updates** — triggered by CI, not a morning task; auto-closes when coverage
  hits target.

## SNR Score yesterday: 2/10
(Last recorded: evening-snr-20260729.md — 7+ weeks ago. A1 coverage gate still not done;
reaction mode dominated; parallel work streams instead of single-threaded A1 execution.)

#morning-focus #focusos #tracy #snr
