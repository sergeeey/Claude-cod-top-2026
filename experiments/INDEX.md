# Experiments Index

All experiments in this project, sorted by date (newest first).

| ID | Date | Claim (slug) | Tier | Verdict |
|---|---|---|---|---|
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
