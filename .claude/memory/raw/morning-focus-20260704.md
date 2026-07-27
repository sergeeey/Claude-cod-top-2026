# Morning Focus - 2026-07-04

## 🐸 A1 Task (eat the frog first)
**Run `pytest --cov --cov-report=term-missing` and close the coverage gap to ≥86%.**
This A1 has been on the list since 2026-06-10 (24 days) and has been skipped every single day. The Scope Fence "Done when" criterion cannot be declared met without it. CI measured 75% on Linux as of 2026-07-01 — but ~43 new test files landed since then (PRs #159–#162 + test_log_rotation, test_pretooluse_output_schema, test_input_guard_pretooluse_schema, test_redact_mcp_behavior, test_post_commit_memory). First: measure the real number. If <86%: `pytest --cov-report=term-missing | grep MISS`, find top uncovered modules, write targeted tests, push until CI gate clears. If ≥86%: immediately pivot to install.sh 2nd machine.

## Top-3 Priority
1. **Coverage gate: measure → test → CI green at ≥86%** — SIGNAL: direct Scope Fence "done when" criterion. 24-day deferral means this is structural avoidance, not legitimate deprioritization. The only remaining blocker to calling this project "done" is this number.
2. **Confirm + merge PR #163** (input-guard-transcript-escalation fix) — SIGNAL: real UX regression — users sending text quoting `"Human: ... Assistant: ..."` get hard-blocked by input_guard. 1720 tests passing, fix is narrow (cap role_injection escalation contribution to 1). Needs explicit user confirmation to merge.
3. **Install.sh validation on 2nd machine** — SIGNAL: second of three required Scope Fence machines. First (live ~/.claude) confirmed 2026-07-01. Cannot be done autonomously — requires user to spin up a clean container and run `bash install.sh --profile=standard --non-interactive`.

## Ignore Today
- **PR #164** (global vs project overlay docs) — valid content, zero urgency. Merge after coverage gate.
- **PR #136** (research-audit-skill, open since June 27) — base is 50 commits behind. Needs rebase before review. Wrong day.
- **PR #117** (family-pack-agents, open since June 1) — stale. Needs rebase or close.
- **PR #132** (evening SNR June 11, draft) — stale FocusOS artifact, close it.
- **New features / skills / hooks** — Scope Fence: "NOT NOW." Same applies while coverage gate is open.
- **Distribution sprint / Show HN** — Scope Fence criteria not fully met. Don't promote yet.
- **Ruff version pinning** — DONE via PR #160 ("pin toolchain versions"). Cross off permanently.

## SNR Score yesterday: 4/10
Source: evening-snr-20260702.md — "real work shipped, quality positive, but reactive not planned." A1 (coverage gate) NOT completed. PRs #161/#162 landed as reactive bug fixes, not planned coverage work. 22-day gap since last morning focus was set. Pattern: reactive bug discovery crowds out the planned "move the number" work.

## Blocked items (flag for user)
- **PR #163 merge** requires explicit user confirmation (PR body says so). Recommend reviewing and confirming merge today.
- **Install.sh 2nd machine** requires a fresh container. Recommend scheduling a 30-min block.

#morning-focus #focusos #tracy #snr
