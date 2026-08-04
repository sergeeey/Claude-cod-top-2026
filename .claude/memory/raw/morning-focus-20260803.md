# Morning Focus - 2026-08-03

## 🐸 A1 Task (eat the frog first)
Dogfood `universal-atomizer` on a genuinely new domain object (code/contract — NOT a methodology doc, which was the prior run's domain). Write a citable artifact to `skills/extensions/universal-atomizer/dogfood-runs/`, update `registry.yaml` maturity to `dogfooded`. This closes P2 item 16 (4→5 dogfooded skills, plan's minimum target). Do this BEFORE opening GitHub, email, or any reactive thread.

## Top-3 Priority
1. **Dogfood universal-atomizer on a new domain** — Signal: directly closes the only remaining gap between current state (4/129 dogfooded) and plan's minimum target (5-10). Has a concrete deliverable: citable artifact + single YAML line edit. Every day this is deferred, P2 item 16 stays open with no excuse. activeContext.md "next action" has named this explicitly since 2026-07-24.
2. **Verify install.sh seeds canonical paths correctly** — Signal: PRs #242–244 all fixed the same class of bug (hooks reading/writing at wrong canonical paths). If install.sh still seeds `_auto/` instead of canonical root, fresh installs on new machines reproduce the exact bugs just fixed. One grep + one dry-run is all it takes — low-cost, high-leverage prevention.
3. **Draft EstimandOps L0 estimand.md for P2 item 18 (profile benchmark)** — Signal: the user explicitly flagged this as needing their judgment call before benchmark execution starts. A draft estimand.md (population / comparator / MCID) prepared now means the user can approve in <5 min in their next session rather than re-reading the full plan. Unblocks without executing.

## Ignore Today
- **P3 items 19–22** — no consequence if deferred; P2 isn't fully closed yet. P3 before P2 = wrong order.
- **Security P0-D** (SEC-01/SEC-02/AI-01) — explicitly and knowingly accepted by the user: "сделай все риски Security я принимаю". Recorded as open accepted risk, not a gap.
- **New hooks/infra additions** — methodology ledger flagged this anti-pattern: adding more infrastructure before verifying the existing layer is stable. Last 3 PRs were all reactive path-fix work. Stop, verify, then extend.
- **Cohen's kappa benchmarked-vs-dogfooded decision for hypothesis-arbiter** — n=1 moderate kappa (0.565), no downstream blocker today.
- **README/badge/admin tasks** — reactive noise; crept in repeatedly per evening-snr-20260729 Noise Detected section.

## SNR Score yesterday: 2/10
(from raw/evening-snr-20260729.md — most recent evening SNR file available)
Pattern: A1 (coverage gate, then dogfood) not done for 25+ days. Reactive parallel streams dominate.
Root cause identified: no morning focus set on 2026-07-29, 2026-07-31, 2026-08-01, 2026-08-02 — missing accountability anchor.

#morning-focus #focusos #tracy #snr
