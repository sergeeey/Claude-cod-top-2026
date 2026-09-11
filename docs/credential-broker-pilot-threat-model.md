# Credential Non-Possession Pilot — Threat Model (2026-09-12)

**Status:** DESIGN DRAFT, pre-implementation. Per `doubt-driven-development.md` Trigger 3
(High-Risk Changes: security changes → skeptic + sec-auditor, parallel, before code), this
document is the DDD design proposal — no implementation exists yet. Do not build against this
until skeptic + sec-auditor findings are addressed.

## Why this exists

Identified during the 2026-09-11/12 Muse-architecture comparison as the single most serious
verified gap in this stack: secret handling today is reactive regex-redaction, not
non-possession. Routing-floor telemetry P0 (PRs #431/#432) was explicitly kept separate from
this work per the user's own instruction — this is the next, independent cycle, starting now
that routing is frozen/observing.

## Verified current state (checked, not assumed, 2026-09-12)

- `scripts/redact.py` is wired in `hooks/settings.json` at `matcher: "mcp__*"` ONLY — it scrubs
  `tool_input` before an MCP call goes out, nothing else.
- `hooks/lib/security.py`'s `redact_secrets()` is called from exactly 5 places, all OUTBOUND
  sinks: `auto_capture.py`, `knowledge_librarian.py` (memory writes), `lib/state.py` (telemetry
  logging), `pre_commit_guard.py` (commit checks), `webhook_notify.py` (outbound webhooks).
- **No hook redacts anything on the INBOUND path** — Read tool output, Bash stdout/stderr,
  WebFetch content all reach Claude's context completely unfiltered.
- `.env*` files are Write/Edit-DENIED (`hooks/settings.json` deny list) but NOT Read-denied —
  nothing stops `Read(.env)` or `Bash(cat .env)`.
- Conclusion, stated precisely: **a secret does not need to be exfiltrated to leak — it only
  needs to be READ.** Once in context, `redact_secrets()` only cleans it for the 5 outbound
  sinks above; the raw value remains in the live conversation transcript/context indefinitely.

## Scope of this pilot — deliberately narrow

**In scope:** ONE credential class — a GitHub token used for this repo's own PR/CI workflow
operations (the ones this session already performs routinely: check PR status, read CI logs).
**Out of scope, explicitly:** a universal broker for arbitrary credential types; replacing
`gh` CLI's own auth storage; any change to Claude Code's own approval/permission UI; any
WRITE-shaped GitHub operation (comment, merge, push) performed autonomously by this pilot
against the real repo — those remain gated by the existing Black/Red-tier confirmation rules
regardless of whether a broker is involved.

## Threat actors / failure modes

1. Claude runs `gh auth token`, `echo $GITHUB_TOKEN`, or `cat .env` while debugging — raw
   secret lands in Bash stdout → Claude's context, unfiltered (verified gap above).
2. A hook/script Claude writes logs the token to a file or error message it later reads.
3. Claude constructs an MCP `tool_input` containing the raw token — `redact.py` cleans the
   OUTBOUND call, but the value was already in Claude's own context to build the call.
4. A malicious or buggy skill/prompt-injection tries to get Claude to print a secret it
   currently possesses (this pilot removes the *possession*, which removes this attack
   surface structurally rather than relying on Claude declining to comply).

## Design — "operation broker," not "secret vault"

Claude never receives the token. Instead, a small, fixed set of ALLOWED HIGH-LEVEL OPERATIONS
(e.g. `get_pr_status`, `list_pr_checks` — read-only for this pilot, see Scope) are exposed via
a narrow CLI (`scripts/credential_broker.py github <operation> [args]`), analogous to how `gh`
itself is already invoked via Bash today:

- The broker process resolves the credential itself (`gh auth token`, executed as a subprocess
  the broker spawns and whose output it captures — never printed by the broker).
- The broker performs the actual API call (via `gh` CLI or `requests`) internally.
- The broker sanitizes the result with `hooks/lib/security.redact_secrets()` as defense-in-depth
  BEFORE printing anything to its own stdout (what Claude/Bash actually sees).
- The broker's own audit log (separate JSONL, same pattern as `lib/state.py`'s telemetry)
  records the operation requested and its outcome — never the credential value.
- Every code path that could raise an exception is written so the credential variable is never
  interpolated into any string that could be printed or logged (defensive coding requirement,
  not just "remember not to log it").

## Falsifiable claim for this pilot (Zero-Signal Gate)

- **Entity:** `scripts/credential_broker.py`'s GitHub read-only operation set.
- **Falsifiable predicate:** for every allowed operation, including forced-error paths, the
  real credential value never appears in (a) the broker's own stdout/stderr, (b) any file the
  broker writes, (c) any exception message the broker can raise.
- **Measurable outcome:** an automated test suite using a CANARY value in place of a real
  token (no live GitHub credential needed for the leak-proof itself) that asserts the canary is
  ABSENT from every captured output across all operations and forced-error paths. A SEPARATE,
  manual, read-only smoke test against the real `gh auth token` confirms the pilot works
  end-to-end, run once, not part of the automated suite (to avoid any test depending on live
  network/auth state).

## What "promote" vs "reject" means for this pilot

- **PROMOTE:** all canary-leak tests pass, skeptic's and sec-auditor's concerns are each
  Fixed/Accepted/Dismissed with reasoning (per `falsification-ladder.md`'s Skeptic Response
  Matrix), and a real read-only operation demonstrably works end-to-end once, manually.
- **REJECT / PARK:** a leak is found that cannot be closed without disproportionate complexity
  for a pilot, or skeptic/sec-auditor find the "operation broker" shape itself is unsound
  (e.g., the subprocess boundary doesn't actually prevent the token from being visible to
  Claude for some reason not yet considered) — in which case the finding becomes the input to
  a redesigned Phase 1, not silently patched.

---

## VERDICT: REJECTED as scoped (2026-09-12, before any implementation)

Skeptic and sec-auditor reviewed this design in parallel (per DDD Trigger 3). Both
independently found — sec-auditor by direct inspection of `hooks/settings.json`, not by
deferring to skeptic's report — the same CRITICAL, structural flaw:

### Kill Analysis

**What was killed:** the specific shape "a CLI script Claude invokes via Bash, in the SAME
unrestricted Bash execution context Claude already has, resolves the credential internally and
returns a sanitized result" as a mechanism for non-possession.

**Why:** `hooks/settings.json` allows `Bash(*)` and `Read(*)` with zero deny-rules on
credential-read paths (`gh auth token`, `cat .env`, `printenv`, `Read(.env*)`, etc.). Introducing
a broker adds a PREFERRED path; it does not remove the EXISTING path. Non-possession is a
negative claim ("no path exists by which the secret reaches context") — a preferred alternative
path proves nothing about the paths left open. `claim_entropy` (Perelman-audit sense) does not
decrease: the state "credential resolvable by any Bash-capable actor" is unchanged by adding a
broker next to it.

**Second, independent kill vector (not just a variant of the first):** the design's own
"defense-in-depth" idea — scrub the broker's output with `redact_secrets()` before Claude sees
it — was checked against whether an equivalent mechanism already exists for the general inbound
path (`mcp_response_guard.py`, `web_response_guard.py`, both real, both wired). It does, and it
proves the mechanism class doesn't work here: both are **PostToolUse** hooks, and this repo
already learned and documented (F-03/F-12, `hooks/CLAUDE.md`) that **PostToolUse cannot deny —
the tool has already run, the secret is already in context by the time any scrubbing hook fires.**
Any design that leans on post-hoc output scrubbing (broker or not) inherits this same
impossibility. This closes off an entire class of alternative fixes before they'd be attempted.

**What survived, not killed by this verdict:**
- The threat model itself (4 failure modes) — accurate, independently confirmed.
- The verified-current-state grep findings about `redact.py`/`redact_secrets()` being
  outbound-only — accurate for those 5 call sites specifically (sec-auditor's correction:
  two INBOUND hooks do exist, but scan for prompt-injection, not secrets, and can't block
  even if they did — see above).
- The general idea that Claude should not need to possess a raw credential to perform a scoped
  operation — sound in principle, just not achievable via same-process/same-privilege CLI
  wrapping.

**Relaxation map (per Anti-Overfitting Gate, one assumption changed, not a bundle):** the
assumption that fails is "the broker can run in the same Bash-unrestricted execution context
Claude already has." A viable Phase 1 needs ONE of:
1. **Deny-list hardening** (immediate, low-risk, NOT a non-possession solution — an
   arms-race mitigation only, this repo already learned via the `$IFS`-obfuscation incident
   that Bash-string denies are gameable) — ships as a separate, honestly-scoped hardening PR,
   not as "the broker."
2. **A genuine privilege/process boundary** Claude's Bash session cannot cross at all (a
   separate OS user/service, a socket-based credential daemon that only accepts pre-approved
   operation requests) — this is a materially bigger project than a CLI script and needs its
   own DDD/skeptic cycle when picked up, not folded into tonight's scope.

**Revival condition:** re-attempt Phase 1 only with option 2 above as the starting design, or
if Claude Code's own harness ever exposes a genuine sandboxed-execution primitive this repo can
build on (worth checking for in a future session, not assumed to exist now).

**Process note:** one coordination mistake during this review — the sec-auditor sub-review was
first attempted via a fresh `Agent()` call instead of `SendMessage` to the same paused agent,
losing its partial context; corrected by resuming the same agent properly. The resumed agent
also could not locate this exact file path in its own working directory on the first pass
(a real process gap — the design doc's path should have been re-stated explicitly, not assumed
carried over) but reached the same conclusion independently by inspecting `hooks/settings.json`
directly, which is the stronger form of confirmation anyway (not dependent on trusting this
document's own claims).

---

## Option 1 (deny-list hardening) — shipped, same night, same DDD/skeptic discipline

Per the relaxation map above, option 1 was implemented as a narrow, honestly-labeled
"arms-race mitigation, not non-possession" hardening in `hooks/permission_policy.py` — reusing
the existing, already-audited `DANGEROUS_PATTERNS`/`SENSITIVE_PATH_PATTERNS`/
`_reads_sensitive_path()` machinery rather than a separate static deny list (a first cut used
`hooks/settings.json` static globs directly; reverted once it became clear the existing dynamic
policy engine already covered the same ground more robustly, just at the wrong emission tier
for this solo-autonomy profile).

Two changes, both skeptic-reviewed (implementation-level, not just design-level) with real bugs
found and fixed BEFORE merge, same discipline as the design phase:

1. `main()` escalates decide()'s "ask" to a hard, always-emitted "deny" specifically for a
   sensitive-path read — using a NEW, narrower helper `_names_a_sensitive_path()`, not the
   existing `_reads_sensitive_path()` directly. Skeptic found (by code trace) that the direct
   call would have silently hard-blocked `git show HEAD`/`git diff HEAD`/`git log -p` — ordinary,
   extremely common commands `_reads_sensitive_path()` also flags for an unrelated reason
   (unbounded blast radius, not "names a secret"). Fixed; regression tests added confirming
   these bare-ref commands are NOT escalated, while the actual sensitive-path cases still are.

2. A new `_GH_AUTH_TOKEN_RE`, position-anchored exactly like the existing `_EVAL_COMMAND_RE`,
   closes the `gh auth token`/`gh auth status --show-token` disclosure path (the design's
   original threat #1). Skeptic found (by direct execution) that a first cut using bare
   `DANGEROUS_PATTERNS` strings falsely denied `git commit -m "fix: block gh auth token
   disclosure"` — i.e., this very fix's own commit message. Fixed the same way `_EVAL_COMMAND_RE`
   already fixed the identical class of prose-collision false positive for "eval".

**Known, accepted, NOT closed by this hardening (named explicitly, not silently ignored):**
- An alternate reader outside `_PATH_SENSITIVE_READ_PREFIXES` (`less .env`, `bash -c "cat .env"`,
  `sed '' .env`, `xxd .env`) or a sensitive read placed after a chain operator that resolves
  before the sensitivity check (`echo x && cat .env`) is not caught by the escalation — these
  were ALREADY effectively allowed before this fix (silently-dropped "ask"), so shipping this
  hardening is not a regression, only a partial, narrowly-scoped improvement.
- `Read(".env")` remains completely unguarded (`Read` is in `ALWAYS_SAFE_TOOLS`) — the same gap
  the original threat model named and did not claim to close via a Bash-only mechanism.
- `SENSITIVE_PATH_PATTERNS` is a substring scan and can false-positive on legitimate names
  (`.env.example`, `secretsanta.txt`) — previously harmless at the silently-dropped "ask" tier,
  now a real (safe-direction) block with no in-session recourse. Revisit only if this is
  actually observed to cause real friction — per this session's own "wait for real signal,
  don't polish speculatively" discipline (see the routing-floor freeze-gate decision the same
  night), not preemptively.

This hardening does NOT reopen the Phase 1 verdict above — non-possession for a genuine
Phase 1 still requires a real privilege/process boundary. This is deny-list hardening of the
*current, pre-existing* gap, shipped honestly as exactly that.
