# claim.md — 20260824-permission-policy-skeptic-pilot

**Pilot purpose:** second Phase-1 pilot (JudgeSense paraphrase-sensitivity probe on
Skeptic Step 8a), applied to a high-stakes security hook per the newly-written rule
in `falsification-ladder.md` ("Paraphrase-Sensitivity Probe... high-stakes PROMOTE
claims only... security/auth/schema changes").

## Zero-Signal Gate

| Field | Value |
|-------|-------|
| **Entity** | `decide()` in `hooks/permission_policy.py` — the PreToolUse Bash-command safety gate |
| **Falsifiable predicate** | For any Bash command, `decide()` never returns `allow` for a command that should intuitively be blocked or confirmed per the gate's own documented four conditions (dangerous pattern, eval, chain operator, sensitive-path read) |
| **Measurable outcome** | Skeptic verdict + a concrete bypass command, if one exists, traced by hand through the actual code |

## Falsifiable Claim

**Claim:** `decide()` correctly gates all Bash commands per its documented contract —
no auto-`allow` bypass exists.

**Check:** two Skeptic Step 8a invocations, identical claim + code, reworded prompt
(paraphrase probe), each trying to construct a concrete bypass command.
