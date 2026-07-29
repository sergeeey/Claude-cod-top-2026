# Experiments Index

All experiments in this project, sorted by date (newest first).

| ID | Date | Claim (slug) | Tier | Verdict |
|---|---|---|---|---|
| 20260728-osa-fl-protocol-vs-standard-analysis | 2026-07-28 | full OSA/FL/Perelman protocol scores higher than standard analysis on blind-graded retrospective verdict quality, n=2 pilot | Full | REJECT (`null_results/20260728-osa-fl-protocol-vs-standard-analysis.md` — Arm A beat Arm B 9v5 and 9v7 on the 2 real null_results cases; Kill Analysis narrows this to 2 specific, fixable mechanisms, not a wholesale indictment; 2 Diamond findings filed to `pearl_registry/INDEX.md`) |
| 20260727-config-effectiveness-opportunistic | 2026-07-27 | standard config causes/predicts higher validation-catch rate than vanilla/minimal, on opportunistically accumulated real tasks | Full | ARCHIVE (`parked/20260727-config-effectiveness-opportunistic.md` — still BLOCKED-INFRASTRUCTURE per `substrate_gate.md`, real ongoing per-task manual-operator cost to unblock; user chose to park rather than accept that cost now, design/statistics layer untested and unfalsified) |
| 20260727-profile-comparison-validation-theater | 2026-07-27 | standard config causes higher validation-theater-catch rate than vanilla/minimal, on 10 constructed scenarios | Full | ARCHIVE (`parked/20260727-profile-comparison-validation-theater.md` — a cheap independent feasibility check confirmed the same `claude -p` auth blocker as `config-effectiveness-opportunistic`, at 30 runs instead of 3; parked for consistency, claim never tested) |
| 20260716-response-guard-fp-calibration | 2026-07-16 | composition scoring lowers guard FP without raising FN | Standard | BASELINE RECORDED (FP=8/13, FN=2/12; fix = next PR) |
| 20260701-p1-hooks-reproducible-install | 2026-07-01 | clean install deploys everything its config references | Standard | PROMOTE (landed as `3462c2b`) |
| 20260701-revive-session-save | 2026-07-01 | session_save.py is abandoned and needs revival | Standard | NEEDS-HUMAN (premise falsified — file is alive) |
| _template | — | template files | — | — |

---

## How to Start a New Experiment

1. Copy `experiments/_template/` to `experiments/<YYYYMMDD-slug>/`
2. Fill in `claim.md` first (falsifiable statement)
3. Check `null_results/INDEX.md` for related rejected hypotheses
4. Run: positive control → negative control → baseline → test → stress → caveats → decision
5. If REJECT/ARCHIVE: add to `null_results/INDEX.md`

## Tier Reference

- **Micro:** docs/style/typos → inline PR description only (claim + check + caveat)
- **Standard:** features/bugfixes → experiments folder, min: claim + controls + decision
- **Full:** auth/security/arch/research → all 11 steps + null_results on failure
