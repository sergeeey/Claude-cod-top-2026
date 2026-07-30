# Morning Focus - 2026-07-30

## 🐸 A1 Task (eat the frog first)
Dogfood one more `wired`-maturity skill on a genuinely new domain object — move P2 item 16 from 4→5 dogfooded skills (minimum target), write a citable artifact to `skills/extensions/<name>/dogfood-runs/`, and update `registry.yaml` maturity field. Best candidate: `universal-atomizer` on a code/contract domain (the second, different-domain run the activeContext explicitly flagged as ready).

## Top-3 Priority
1. **Dogfood universal-atomizer on a new domain** — Signal: directly closes the only remaining gap between current state (4/128 dogfooded) and the plan's minimum target (5-10). Each dogfood run has a concrete output (citable artifact + YAML edit). Not doing this today means P2 item 16 stays open another cycle with no excuse.
2. **Verify install.sh seeds canonical paths correctly after PR #242–244** — Signal: three consecutive PRs (242, 243, 244) all fixed the same class of bug (hooks reading/writing at wrong canonical paths). If install.sh still seeds `_auto/` instead of the canonical root, fresh installs on new machines will reproduce the exact bugs just fixed. One grep + one dry-run confirms or clears this.
3. **Draft EstimandOps L0 estimand.md for P2 item 18 (profile benchmark)** — Signal: the activeContext explicitly says this needs a user judgment call before starting. Drafting the estimand.md now (population / comparator / MCID) means the user can approve the design in <5 min when they return rather than needing to re-read the whole plan. Unblocks the benchmark without executing it.

## Ignore Today
- **P3 items 19–22** — no consequence if deferred; P2 isn't fully closed yet, P3 before P2 = out-of-order.
- **Security P0-D risks** (SEC-01/SEC-02/AI-01) — explicitly and knowingly accepted by the user ("сделай все риски Security я принимаю"), recorded as open accepted risk, not a gap.
- **Cohen's kappa benchmarked-vs-dogfooded decision for hypothesis-arbiter** — nice-to-have, n=1 moderate kappa (0.565), no downstream blocker today.
- **New hooks/infra additions** — last 3 PRs were all path-fix reactive work; adding more infrastructure before verifying the existing layer is stable is the anti-pattern the methodology ledger flagged.

## SNR Score yesterday: 8/10
(from raw/evening-snr-20260723.md — most recent evening SNR file; no evening SNR found for 2026-07-28 or 2026-07-29)

#morning-focus #focusos #tracy #snr
