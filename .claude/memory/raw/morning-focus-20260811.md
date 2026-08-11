# Morning Focus - 2026-08-11

## 🐸 A1 Task (eat the frog first)
Push coverage from 85% → ≥86%: run `pytest --cov --cov-report=term-missing`, find the lowest-coverage module(s) from Wave 2's remaining gaps, write targeted tests, push, confirm CI green at ≥86%. This is ONE percentage point away after 30+ days of structural avoidance — close it today before anything else.

## Top-3 Priority
1. **Coverage gate 85% → ≥86%** — Signal: plan's "Done when" criterion; Wave 2 moved us from 83% to 85%, leaving exactly 1 point to close. Every day this stays open is a structural blocker on claiming the repo production-ready. No external dependency. The frog is measurable, closeable today.
2. **Dogfood universal-atomizer on a code-domain object** — Signal: directly closes P2 item 16 (4→5 dogfooded skills, plan minimum), which unblocks P2 item 18 benchmark approval. Has been named A1 since 2026-07-24 with no external blocker — pure avoidance. Write citable artifact to `skills/extensions/universal-atomizer/dogfood-runs/`, update `registry.yaml` maturity to `dogfooded`. Do after A1 coverage work, not instead of it.
3. **Draft estimand.md for P2 item 18 (profile benchmark)** — Signal: user flagged this needs their judgment call before execution. A draft (population / comparator / MCID) prepared now lets the user approve in <5 min in their next session. Unblocks without executing the expensive 30-session benchmark. Low cost, high unblocking leverage.

## Ignore Today
- **P3 items 19–22** — P2 item 16 isn't closed yet; P3 before P2 is wrong order, no consequence from deferral.
- **Security P0-D** (SEC-01/SEC-02/AI-01) — explicitly and knowingly accepted by the user. Recorded as open accepted risk in the plan doc.
- **New hooks/infra additions** — anti-pattern: methodology ledger showed adding ceremony before verifying existing layer underperforms. Stop, verify, extend — in that order.
- **README/badge/admin tasks** — reactive noise; Noise Detected in every recent evening-snr. If not in Top-3, it's Noise.
- **Boyko eval-suite expansion** — primary goal per user context, but cannot be the excuse for skipping the structural coverage gate that's been open 30+ days and is now 1 point away.

## SNR Score yesterday: 2/10
(from raw/evening-snr-20260729.md — most recent evening SNR file available; no evening-snr filed for 2026-07-30 through 2026-08-10, an 11-day accountability gap)
Notable since last morning focus (2026-08-04): Wave 2 coverage push landed (83%→85%), PR #253 gated Bash file-write by per-agent scope (security signal), PR #251 fixed skill-disambiguation docs. Coverage A1 was NOT closed despite wave 2 work. No morning focus set 2026-08-05 through 2026-08-10 — 6-day accountability gap itself represents structural avoidance of the focus ritual.

#morning-focus #focusos #tracy #snr
