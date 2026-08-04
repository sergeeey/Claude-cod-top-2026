# Morning Focus - 2026-08-04

## 🐸 A1 Task (eat the frog first)
Dogfood `universal-atomizer` on a genuinely new domain object (a code file — e.g. `hooks/agent_tool_scope_guard.py` or `hooks/promotion_gate_guard.py` — NOT a methodology doc, which was the prior run's domain). Write a citable artifact to `skills/extensions/universal-atomizer/dogfood-runs/`, update `registry.yaml` maturity to `dogfooded`. This closes P2 item 16 (4→5 dogfooded skills, plan's minimum target). Do this BEFORE opening GitHub, email, or any reactive thread. This was also the A1 yesterday and was not done — the pattern of deferral must stop here.

## Top-3 Priority
1. **Dogfood universal-atomizer on a code-domain object** — Signal: directly and completely closes P2 item 16, the only gap between current state (4/129 dogfooded) and plan's stated minimum target. Deliverable is concrete (citable artifact + single `registry.yaml` line). Named "next action" in activeContext.md since 2026-07-24. Every deferred day is pure avoidance with no external blocker.
2. **Verify install.sh seeds canonical paths correctly** — Signal: PRs #242–244 all fixed the same class of bug (hooks reading/writing at wrong canonical paths). If install.sh still seeds `_auto/` instead of canonical root, every fresh install on a new machine silently reproduces the bugs just fixed. One grep + one dry-run, low-cost, high-leverage prevention. Not doing it is a ticking regression risk.
3. **Draft estimand.md for P2 item 18 (profile benchmark)** — Signal: user explicitly flagged this needs their judgment call before benchmark execution. A draft (population / comparator / MCID) prepared now lets the user approve in <5 min in their next session rather than re-reading the full plan doc. Unblocks without executing the expensive benchmark itself.

## Ignore Today
- **P3 items 19–22** — no consequence if deferred; P2 item 16 isn't even closed yet. P3 before P2 is wrong order.
- **Security P0-D** (SEC-01/SEC-02/AI-01) — explicitly and knowingly accepted by the user ("сделай все риски Security я принимаю"). Recorded as open accepted risk.
- **New hooks/infra additions** — methodology ledger flagged this anti-pattern: adding ceremony before verifying existing layer helps. Last batch of PRs were all reactive path-fix work. Stop, verify, extend — in that order.
- **Cohen's kappa / benchmarked-vs-dogfooded decision for hypothesis-arbiter** — n=1 moderate kappa (0.565), no downstream blocker today.
- **README/badge/admin tasks** — reactive noise; appeared in Noise Detected section of every recent evening-snr. If it's not in Top-3, it's Noise.
- **Coverage gate ≥86%** — structural A1 for 25+ days but displaced by dogfood which is more immediately closeable. Do not let the coverage gate displace dogfood again today — it has no external deadline; dogfood has a plan minimum that P2 item 18 is blocked behind.

## SNR Score yesterday: 2/10
(from raw/evening-snr-20260729.md — most recent evening SNR file; no evening-snr filed for 2026-07-30 through 2026-08-03, which itself signals accountability anchor was missing on those days)
Pattern: A1 (dogfood universal-atomizer) not done despite being named A1 in morning-focus-20260803. Reactive parallel streams dominated. Root cause: no morning focus set on 2026-07-30, 2026-07-31, 2026-08-01, 2026-08-02 — this file breaks that 4-day gap.

#morning-focus #focusos #tracy #snr
