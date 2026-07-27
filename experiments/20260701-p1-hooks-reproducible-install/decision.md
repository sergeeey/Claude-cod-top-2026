# decision.md — 20260701-p1-hooks-reproducible-install

## Verdict

- [x] **PROMOTE** — claim holds; landed in this repo as commit `3462c2b`
      ("Backport PR #157 + #158"), verifiable at `install.sh:408` (`install_commands()`,
      wired into the standard+full profiles at :874 and :885).

> **Provenance note (added 2026-07-16 on import).** This run was performed in a
> parallel audit clone (`repo-clean-test`) and originally recorded its verdict
> against that clone's local commit `1d787bb`, which was never pushed and does not
> resolve in this repository. The artifact was imported here unmodified apart from
> this note and the SHA above. The *work* it validates did land — that was
> re-verified at import time by locating `install_commands()` in `install.sh`, not
> by trusting the artifact's own claim. Cite `3462c2b`, not `1d787bb`.

## Evidence Gate (Stage 6)

| Requirement | Status |
|---|---|
| Baseline | ✅ measured: 5 findings (2 HIGH, 1 MEDIUM, 2 LOW) on pre-fix install |
| Positive control passes | ✅ `test-install-target-2`: commands+redact.py present, 0 backups |
| Negative control fails-as-expected | ✅ `test-install-target-3`: real diff → backup+replace, not silent skip |
| Real-data measurement | ✅ actual `install.sh` subprocess runs, actual filesystem, actual hook stdin/stdout — not mocked |
| Evidence marker | **[VERIFIED-REAL]** for all 5 fixes; [VERIFIED-REAL] (not [INFERRED]) after re-running the negative control live in this turn |

Synthetic inputs used: fake PII/injection strings fed to `redact.py`/`input_guard.py`.
These are appropriately capped — the CLAIM about hook logic correctness is
[VERIFIED-REAL] (real subprocess, real regex engine), but a live-Claude-Code-session
verification of `/evolve-solution` actually loading was NOT performed (documented
blind spot in oracle_audit.yaml) — that piece stays [UNKNOWN] until an actual new
session is started against this install.

## Result Classification (End-of-run diamond scan)

- [x] 🥈 **Silver** — the methodology itself (Stage 0-7) is transferable: applying it
      retrospectively to an already-completed fix (rather than only prospectively)
      is a technique worth reusing to validate past judgment calls, not just future ones.
- [ ] 🥇 Gold / 💎 Diamond / 🪨 Stone — n/a

**Silver finding → worth carrying forward:** the Oracle-Adequacy Gate's own "was the
oracle already gameable/theater" question is answerable by pointing at a REAL prior
negative-control firing (ruff+pytest both green on broken code) rather than a
hypothetical — this is a stronger form of oracle evidence than most audits get,
because the failure already happened once in the SAME session before the fix.

## What this run added beyond the ad-hoc PR #157 process

1. Made explicit that Variant B (an equally-plausible "simpler" fix) has a real
   correctness gap the ad-hoc process never explicitly considered — the shipped fix
   was right, but this run supplies the FIRST written argument for why, beyond
   "it passed the tests."
2. Surfaced one new LOW finding (silent identical-skip vs. bannered interactive-skip)
   that the original acceptance audit did not catch, because it wasn't a
   file-presence/correctness question — it only surfaces when you deliberately
   red-team the fix's UX, not just its safety.
3. Surfaced a scope gap in the original intent framing: Variant C (restructuring
   install_minimal/install_rules) was never explicitly considered-and-rejected in
   PR #157 — it's now on record as a deferred, not forgotten, alternative.
