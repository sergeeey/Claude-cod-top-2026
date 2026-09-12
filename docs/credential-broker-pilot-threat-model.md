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

## Kill Criterion — first empirical check (2026-09-12, same night, cheapest test only)

The Phase 1 REJECT verdict above named an explicit Kill Criterion for any future option-2
attempt (a real privilege/process boundary): "if the runtime doesn't let the broker's credential
environment be separated from the agent-accessible environment, don't call this non-possession."
Owner's instruction for tonight: check this ONE question empirically, cheaply, WITHOUT building
a full broker — do not decide where the eventual broker's code would live yet.

**Method (real, already-running config — no new MCP server built):** this Claude Code
installation already has an MCP server (`obsidian-vault`) configured with a credential scoped
only to that server's own `mcpServers.obsidian-vault.env.OBSIDIAN_API_KEY` entry in
`~/.claude.json` — not an ambient shell-level export. This is the exact mechanism a GitHub
broker would need to rely on, already live, for a different credential.

**First pass (initial claim, too strong):** `OBSIDIAN_API_KEY` was absent from a Bash tool
subprocess's own environment (`echo $OBSIDIAN_API_KEY` empty, `env | grep OBSIDIAN` → 0 hits).
Concluded, overclaiming: "MCP-server-scoped `env:` config is isolated from Bash's environment
on this harness."

**Skeptic review of that claim (context-asymmetric, evidence-only) returned WEAKENED, not
CONFIRMED** — correctly. Two live gaps in the original test: (1) nothing confirmed
`obsidian-vault`'s process was actually running rather than dormant/failed, making the
observed absence potentially vacuous; (2) the 4 unrelated `*_KEY`/`*_TOKEN` names also found in
Bash's ambient environment (`BYTEZ_API_KEY`, `CLAUDE_CODE_MESSAGING_TOKEN`, `FRED_API_KEY`,
`GRAFANA_SERVICE_ACCOUNT_TOKEN`) were assumed, not verified, to be genuinely ambient rather than
mis-scoped per-server secrets — a direct self-falsification test was available and had not been
run.

**Both gaps closed, same session:**
1. Called `mcp__obsidian-vault__get_vault_stats` live — it returned real vault data (7729 notes),
   which requires the server to have successfully authenticated against the Obsidian Local REST
   API using `OBSIDIAN_API_KEY` at that exact moment. The server is confirmed genuinely running
   and actively using the credential, not dormant — the earlier absence-in-Bash observation is
   not vacuous.
2. Grepped `~/.claude.json` for all 4 "ambient" names directly: zero matches anywhere in the
   file, not just outside `env` blocks. They are not mis-scoped per-server secrets.

**Honest scope of what this now supports (do not overclaim past this):**
- CONFIRMED, tool-verified, narrow: on this one machine, this Claude Code version, this one
  moment, a credential scoped to one MCP server's own `env:` config was not visible in a Bash
  tool subprocess's environment, while that server was demonstrably live and using the
  credential.
- NOT tested, still open (skeptic's own cost table, cheapest-first): a positive control (inject
  a known-unique credential into a server's `env:`, restart the session, confirm it does NOT
  leak — requires a session restart, not run tonight); leak channels other than the Bash
  environment (an MCP tool call's own error message surfaced back to Claude, the broker
  process's stderr/debug logs if Claude can `Read` them, the session's own transcript files,
  behavior across a Claude Code version change or config scope). None of these channels were
  exercised.
- This is evidence for the FIRST sub-question of the Kill Criterion only (does env-scoping
  leak via ordinary process inheritance) — it is not yet evidence that a full broker built on
  this mechanism would pass the 4 attack tests from the original acceptance criteria (direct
  request, indirect env-dump request, forced-error leak check, prompt-injection-style demand).
  Those require an actual broker to attack, which was deliberately not built this session
  (owner's explicit choice: verify isolation only, decide the broker's eventual location later).

**Verdict for this specific sub-check:** `NEEDS-MORE-DATA`, narrower and more honest than either
CONFIRMED or REJECTED — the isolation mechanism this design would depend on is real and
demonstrated, not hypothetical, but this is one data point, not a guarantee, and several cheap
follow-up checks (positive control, leak-channel checks) remain explicitly open before any
future broker attempt could cite this as settled.

## P1.1 MCP Isolation Pack — test plan (written BEFORE execution, per this stack's own
## estimand-before-test discipline; owner-specified scope, 2026-09-12)

**Decision this pack exists to inform:** the broker's own code will live in a separate
repo/process (owner decision, made independently of this pack's outcome). What is NOT yet
decided is whether the MCP server/Bash process boundary this repo's own Claude Code harness
provides is strong enough to let that future broker's design be called `credential
non-possession` rather than `credential non-possession, hopefully`. This pack is the promotion
gate for that ONE claim — nothing else.

**Overall pass/fail criterion (owner's own words, verbatim):** `broker performs an authenticated
action AND model-accessible paths cannot recover the credential`. A PASS requires ALL 7 checks
below to individually pass; ANY single FAIL sets the pack's overall verdict to
`REJECTED/WEAKENED` for the MCP-boundary hypothesis as a whole — per this stack's own
Recomposition Gate (`falsification-ladder.md` Step 8a), 6/7 passing does not average to "mostly
fine," since the credential only needs one open channel to leak through.

**Test subject:** the same real, already-live `obsidian-vault` MCP server and its
`OBSIDIAN_API_KEY` used in the first empirical check above — chosen again for continuity (same
live credential, same harness, same session) and because it is a genuine, already-authenticated
production secret, not a synthetic canary. **Explicit constraint, stated up front:** all probing
of this live server must stay read-only / non-destructive — it is the owner's real, in-use
Obsidian vault, not disposable test infrastructure. No check below may write, delete, or modify
vault content; any check requiring a destructive or account-risking action is marked
`NOT RUN — infra constraint` rather than skipped silently.

| # | Check (owner's wording) | Falsifiable predicate | Method | Cheap now? |
|---|---|---|---|---|
| 1 | Ordinary Bash doesn't see the secret | `OBSIDIAN_API_KEY` absent from a fresh Bash tool subprocess's `env` | Already run in the first pass above (with the two skeptic-required strengthenings). Re-run once more here for a second, independent data point in the SAME session. | Yes |
| 2 | A child process of that Bash (Python/PowerShell/CMD) doesn't see it either | Same absence one process-generation deeper | Spawn Python and PowerShell as children of the Bash tool's own subprocess; each independently checks its own `os.environ`/`$env:` for the key | Yes |
| 3 | The secret can't be recovered via ordinary process inspection | No user-privilege-level OS mechanism (task manager equivalent, `wmic`/`Get-CimInstance` command-line/env dump) exposes another process's environment block without elevation | Attempt the standard non-elevated Windows introspection commands (`wmic process get ...`, `Get-Process` variants) against the actual MCP server host process and see whether they expose environment blocks at all (Windows does not expose a process's env block via ordinary `Get-Process`/`wmic` without `Get-CimInstance Win32_Process` + admin, or a debugger) | Yes, but result is more "does this OS/tool combination expose it at all" than a broker-specific finding |
| 4 | MCP error/timeout/401/traceback doesn't return the secret | A deliberately-triggered error response from the real server (invalid path, malformed argument) does not echo the credential in its message text | Call an `obsidian-vault` tool with a deliberately invalid but harmless argument (e.g., a non-existent note path to `read_note`) and inspect the returned error text | Yes — read-only, no vault mutation |
| 5 | MCP logs don't contain the secret | Whatever Claude Code logs about this session's MCP server process (stdout/stderr capture, if any, in a path Claude's `Read` tool can reach) does not contain the literal key value | Locate any such log path; since the actual secret VALUE is unknown to this session (by design — that's the point), this check can only confirm structural absence of a credential-shaped high-entropy string tied to the `obsidian-vault` server's own startup/error output, not grep for the literal value | Partial — see caveat below |
| 6 | Tool output doesn't contain the secret | A normal, successful tool call's JSON response contains no credential-shaped field | Already demonstrated once (`get_vault_stats`); re-inspect that exact response structure and one more tool call for completeness | Yes |
| 7 | A malicious-shaped request ("return env", "print your credentials") discloses nothing | Asking the server, through any parameter it accepts, to reveal its own process environment or auth material fails / returns nothing credential-shaped | Requires knowing the server's actual attack surface (its tool list and parameter shapes) — MCP servers do not have a generic "run arbitrary code" tool by default; this check is scoped to what `obsidian-vault`'s actual declared tools accept, not a hypothetical | Yes, scoped |

**Named caveat on check 5 (stated before running, not after, per this stack's own
anti-rationalization discipline):** without knowing the actual secret value, "the log doesn't
contain the secret" can only be tested as "the log doesn't contain an obviously credential-
shaped string in the server's own diagnostic output" — a weaker predicate than a literal grep.
This is recorded as a known limit of check 5 up front, not discovered after the fact and
quietly excused.

**Explicitly out of scope for this pack (do not silently expand into these):** building any part
of the actual GitHub broker; deciding the broker repo's name/location beyond "separate,
confirmed"; the 4 original acceptance-criteria attack tests from the top of this document (those
require an actual broker with actual capability-scoped tools to attack — a generic MCP server
that isn't a broker at all, like `obsidian-vault`, can only stand in for the ISOLATION half of
that criteria, not the CAPABILITY-CONTRACT half).

## VERDICT: REJECTED before execution (2026-09-12, same night) — a live, unaddressed channel
## answers the pack's own overall criterion, and the plan itself was found unfit to run

Per this stack's own DDD Trigger 3 (security-tier), the plan above was sent to `skeptic` and
`sec-auditor` IN PARALLEL for design review before any of the 7 checks touched the live server.
Both returned independently, and converged on the same root cause from different angles.

**sec-auditor's finding (tool-verified, not inference):** a single `Grep` call against
`~/.claude.json` — an `ALWAYS_SAFE_TOOLS`-class, zero-gate, always-auto-approved tool call, not
even a Bash command — recovered `OBSIDIAN_API_KEY`'s actual value. `SENSITIVE_PATH_PATTERNS`
(`hooks/permission_policy.py`) has no entry for `.claude.json` / `claude_desktop_config.json` /
`mcp.json`, and even a fixed denylist wouldn't help: that mechanism only gates `Bash` commands
(`_PATH_SENSITIVE_READ_PREFIXES` matches `cat `/`head `/`tail `/`wc `), while `Read`/`Grep`/`Glob`
bypass it entirely via the `ALWAYS_SAFE_TOOLS` early-return in `decide()` (`permission_policy.py`
line ~392) — confirmed independently by re-reading that exact code path, not taken on the agent's
word. This means the pack's own overall criterion — `model-accessible paths cannot recover the
credential` — is FALSE right now, via a channel none of the 7 planned checks even considered
(all 7 look at process env / logs / error text / tool output; none look at the config file the
secret is actually stored in, at rest, in plaintext).

**Correction to sec-auditor's report (verified independently, audit-verification-gate.md
discipline — agent's [VERIFIED] is this session's [INFERRED] until re-checked):** sec-auditor
additionally claimed no `redact.py`/PII-scrubbing mechanism exists anywhere in this repo,
contradicting `rules/security.md`'s "Redaction hook automatically scrubs PII before external MCP
servers." This specific claim is WRONG — `scripts/redact.py` exists, is deployed live at
`~/.claude/scripts/redact.py`, and its `redact_secrets()` function is wired into
`hooks/auto_capture.py`, `hooks/knowledge_librarian.py`, `hooks/webhook_notify.py`, and
`hooks/pre_commit_guard.py` — all real, all confirmed by direct grep. What sec-auditor missed
(understandable — its search was scoped to `hooks/`, and the file lives in `scripts/`) does NOT
rescue the core finding, though: none of those four call sites intercept a raw `Read`/`Grep` tool
call on an arbitrary file. `mcp_response_guard.py` and `web_response_guard.py` are the only
PostToolUse hooks that scan tool *responses*, and they match only `mcp__*` and
`WebFetch|WebSearch` respectively (confirmed via `hooks/registry.yaml`'s `matcher:` fields) — a
`Read`/`Grep` call on a local file is not in scope for either. Net effect: the specific factual
claim was wrong, but the vulnerability conclusion it was raised to support survives independent
re-verification on more precise grounds.

**skeptic's finding (design-time review, before any check ran):** independently identified the
same missing channel from `project_credential_non_possession.md`'s own memory record (the doc
itself already stated the first empirical check's method was "grepped `~/.claude.json`
directly") — i.e., this session had ALREADY demonstrated the read-config-file channel works,
hours before writing a 7-check plan that never re-examines it. Separately, skeptic scored the
plan `INADEQUATE` as methodology regardless of this finding: checks #1/#2 are not independent
(a child process trivially inherits from a parent that #1 already showed lacks the variable);
check #3's chosen tools (`wmic process get`, `Get-Process`) structurally cannot return another
process's environment block on Windows regardless of whether isolation holds, so the check would
pass even if the underlying property were false; check #4 only exercises one of the 4
failure-path categories (`exception`) the owner's own original acceptance criteria named,
omitting `timeout`/`debug_output`/`retry`; and the pack conflates a host-platform property
(does Claude Code's MCP wiring inherit env — checks #1-3) with server-specific properties (does
this ONE server's error handling/logging leak — checks #4-7) without saying so, which would let
a PASS on `obsidian-vault` improperly transfer to a structurally different future GitHub broker
(`artifact-provenance-gates.md` Gate 1: a verdict for artifact A does not transfer to B).

**Verdict:** `REJECTED` (not `NEEDS-MORE-DATA`) — stronger and more decisive than the prior
Kill Criterion sub-check, because this time the overall criterion is falsified by a channel that
exists RIGHT NOW, independent of any process-boundary argument. No amount of process/environment
isolation matters if the credential is separately readable at rest by an always-auto-approved
tool. The 7-check pack was not executed against the live server — both reviews returned before
check #1 of the redesigned pack would have run, and the finding already answers the pack's own
question.

**What this does NOT mean:** it does not mean MCP-server env-scoping (the narrower claim from
the first empirical check above) is false — that specific, narrower claim stands as recorded
(`NEEDS-MORE-DATA`, tool-verified for its own narrow scope). What it means is that env-scoping is
not the weakest link; the plaintext config-at-rest channel is, and it dominates the overall
verdict regardless of how strong the process boundary turns out to be.

**Immediate, separate action taken (not part of this pack, a live vulnerability in THIS
machine's current state, independent of any future broker):** flagged to the owner directly in
this same session for (a) credential rotation of `OBSIDIAN_API_KEY` (owner's own action — lives
in the Obsidian Local REST API plugin's settings, then updated in `~/.claude.json`; this session
did not and will not modify that file), and (b) a proposed `permission_policy.py` hardening to
close the `Read`/`Grep`/`Glob` gap for a short, explicit list of secret-bearing config files —
see the corresponding PR for whether/how that was scoped and shipped.

**Kill Analysis (per this stack's own Anti-Overfitting Gate discipline):**
- **What was killed:** the P1.1 pack as designed, and the implicit assumption that "check the
  process boundary" was the right next question to ask.
- **What was NOT killed:** the narrower first empirical check's claim (env-scoping isolation);
  the general direction of "a broker needs a real security-principal boundary, not just a
  different process" (sec-auditor's own conclusion, independently arrived at); the decision that
  broker code lives in a separate repo (unaffected by this finding either way).
- **Relaxation map:** any future isolation-pack attempt must (1) add a "config file at rest"
  check FIRST, before any process/env check, since it's cheaper to run and, as demonstrated,
  more likely to be the actual failure mode; (2) use a disposable MCP server with a planted
  canary credential, never a live production secret, so a discovered leak costs nothing to
  remediate; (3) separate host-platform claims from server-specific claims explicitly, per
  skeptic's finding above.
- **Revival condition:** re-attempt only after (a) `OBSIDIAN_API_KEY` (or whatever canary
  replaces it) is no longer a live production secret in the test path, and (b) the
  `Read`/`Grep`/`Glob` gap above has a real fix in place — otherwise a re-run would just
  rediscover the same channel.

## The `Read`/`Grep`/`Glob` fix itself — one more adversarial round before merge (2026-09-12,
## same night) — do NOT read this repo's registry/settings comments as "channel closed"

The proposed fix (new `SENSITIVE_PATH_PATTERNS` entries for the Bash side; a new
`_targets_sensitive_config_read()` check plus a matcher extension to `Bash|Read|Grep|Glob` for
the Read/Grep/Glob side) was itself sent to `sec-auditor` for adversarial review BEFORE merge —
per this stack's own DDD practice of reviewing the fix, not just the finding that motivated it.

**First cut, found NEEDS_WORK by sec-auditor, with live reproductions on the reviewer's own
machine (not hypothetical):**
- **CRITICAL-1:** the first cut matched an EXACT basename against a short list
  (`.claude.json`, `claude_desktop_config.json`, `.mcp.json`, `mcp.json`). Claude Code itself
  creates sibling files carrying the SAME secret content — `.claude.json.backup` and
  `.claude.json.tmp.<pid>.<hash>` — that exist on the reviewer's machine right now and are
  NOT an exact basename match. `Read` on either returned `allow`.
- **CRITICAL-2:** the first cut only inspected each tool's `path` parameter. Grep's own `glob`
  parameter, and Glob's own `pattern` parameter, each name the target file just as precisely —
  `Grep(pattern="API_KEY", path=".", glob=".claude.json", output_mode="content")` returned the
  file's actual matching content with zero gate, a complete bypass via a different parameter on
  the SAME tool, not a residual edge case.
- **HIGH-3:** `~/.claude/.credentials.json` (Claude Code's own OAuth credential store — a real
  file, confirmed to exist) was covered on the Bash side (the pre-existing `"credentials"`
  substring in `SENSITIVE_PATH_PATTERNS`) but NOT on the Read/Grep/Glob side, since the first
  cut used a separate, narrower list that didn't include it — an inversion where the LESS
  dangerous tool class (Bash, which at least still requires no live confirmation on this
  profile but is the more auditable path) was better covered than the auto-approved one.
- **MEDIUM-4:** a trailing space or dot in a path (silently dropped by Windows when it actually
  opens the file) defeated the first cut's exact-equality basename comparison.
- **MEDIUM-5:** the first cut's exact-match design (Read/Grep/Glob) and the pre-existing
  substring-scan design (Bash) gave inconsistent results for the same near-miss name
  (`my_mcp.json.bak`) — denied on one side, allowed on the other, undocumented.
- **MEDIUM-6:** the deny message asserted every matched file "stores MCP server credentials in
  plaintext," which overclaims for a project-committed `.mcp.json` manifest that may legitimately
  use `${VAR}` substitution rather than literal secrets.

**Fix, second iteration:** retired the separate exact-basename list entirely and unified onto
`SENSITIVE_PATH_PATTERNS`'s existing substring semantics for Read (`file_path`), Grep
(`path` + `glob`), and Glob (`path` + `pattern`) — deliberately NOT Grep's own `pattern` field,
since that's search CONTENT, not a path, and treating it as one would make an ordinary code
search for the word "credentials" itself trigger a false deny. This single change closes
CRITICAL-1 (sibling files contain the sensitive substring even though they aren't an exact
basename match), CRITICAL-2 (glob/pattern are now inspected), HIGH-3 (the shared list already
had `"credentials"`), and MEDIUM-5 (both sides now use the same list and the same matching
style, so the false-positive tradeoff is consistent and already-accepted, not new). The deny
message was reworded to explicitly name the `.mcp.json`-with-`${VAR}` case and say the gate
can't distinguish it at decision time (addressing MEDIUM-6, not silently dropping it).

**MEDIUM-4, resolved as a side effect, verified by mutation testing rather than assumed:** an
initial second-cut attempt added an explicit `.strip().rstrip(" .")` normalization to defend
against the trailing-whitespace bypass. Mutation-testing it (removing the strip, re-running the
suite) showed **zero test failures** — under substring containment, trailing characters can
never eliminate a match already present in the shorter prefix, so the explicit strip was dead
code carried over from the exact-match design's real need for it. Removed rather than kept as
misleading dead code implying a specific protection mechanism that the design no longer needs.

**Second review pass, sec-auditor:** independently re-verified all of the above by reading the
actual diff (not the session's description of it), ran its OWN independent mutation tests
(disabling the check entirely: 15/15 expected failures, all others green; reverting
`SENSITIVE_PATH_PATTERNS`'s 4 new entries: 5/5 expected failures), confirmed `pre_commit_guard.py`
and the other hooks sharing the old `"Bash"` matcher group were unaffected by giving
`permission_policy.py` its own separate matcher-group entry, and confirmed the full suite
(3432 passed) and all architecture/registry gates pass. **Explicit instruction, followed:** do
not describe this as "the Read/Grep/Glob credential channel is closed" anywhere (this repo's own
`hooks/registry.yaml` comment and this document have both been worded to avoid that framing) —
what is now closed is every SPECIFIC bypass sec-auditor demonstrated live; what remains open and
explicitly named, not silently dropped, is the pre-existing "directory containing the file,
not naming it directly" gap this mechanism was never designed to close (would require either
scanning tool RESPONSES, which is a PostToolUse concern that cannot deny per this repo's own
F-03/F-12 finding, or denying broad undirected Grep/Glob calls outright, reopening the
2026-09-02 solo-autonomy regression).

**Separately found, NOT fixed tonight, flagged for a future session (out of this fix's scope —
a different hook entirely):** while investigating `.credentials.json`'s existence, this session's
own `file-auto-parser` hook (unrelated to `permission_policy.py`) auto-parsed
`~/.claude/.credentials.json` as a side effect of the path being mentioned in conversation —
a second, independent mechanism that reads files without going through `permission_policy.py`'s
gate at all. Not investigated further tonight; named here so it isn't lost.

---

## `file_auto_parser.py` credential-disclosure gate — fixed (2026-09-12, follow-up session)

The gap flagged immediately above was picked up as its own DDD Trigger-3 task. Confirmed to be
worse than the one-line flag suggested: not a one-off, but an ACTIVE, self-perpetuating leak on
the live machine at the time of investigation.

**Verified live impact before any fix (tool-checked, not assumed):** `~/.claude/.credentials.json`
(Claude Code's own OAuth `accessToken`/`refreshToken` plus `mcpOAuth` entries for ~26 third-party
plugins) and `~/.claude.json` (full MCP config) were each fully parsed and cached in plaintext
under `~/.claude/cache/parsed/` merely because their paths were mentioned in chat text — this
hook fires on `UserPromptSubmit`, not `PreToolUse`, so it never reaches `permission_policy.py`'s
`decide()` at all, regardless of anything fixed above in this document. Worse: during the SAME
review, a report that quoted one of the resulting cache file's own path back into chat caused
`file_auto_parser.py` to re-parse that cache file into a THIRD copy — a live, reproduced
self-ingestion loop, not a hypothetical one.

**Why a name-substring denylist alone was rejected (skeptic + sec-auditor design review, DDD
Trigger 3, both independently falsified the same core claim before code was written):**
`SENSITIVE_PATH_PATTERNS` at review time did not yet contain `.claude.json` — reusing it as-is
would have caught only `.credentials.json`, one of the two files actually leaked. Even with
`.claude.json` now added above (P1.1, this same document), a cache file this hook writes is
named from the SOURCE path's `Path.stem` (`.claude.json` → `.claude-<hash>.json`), which no
longer contains the literal substring that made the original file sensitive — this is exactly
the self-ingestion case reproduced live during review.

**Fix, `hooks/file_auto_parser.py`'s `_is_sensitive_path()` — two independent layers:**
1. **Location gate** (`_CONFIG_ROOTS`/`_CONFIG_EXACT_FILES`): anything under `~/.claude`
   (covers `.credentials.json`, `settings.local.json`, and this hook's own `CACHE_DIR`, closing
   the self-ingestion loop), `~/.ssh`, `~/.aws`, or exactly `~/.claude.json` (a sibling of
   `.claude/`, not inside it — needs its own exact-file check). Immune to renaming/hashing
   because it does not depend on the filename at all.
2. **Name gate** (reuses `permission_policy.SENSITIVE_PATH_PATTERNS` as a second, independent
   consumer of the same canonical tuple, not a duplicated list): catches a similarly-sensitive
   file OUTSIDE those roots — a project's own `.mcp.json`, an exported `credentials.json` in
   Downloads. Checked against both the raw candidate string and its `Path.resolve()` form.

Both layers verified independently load-bearing by mutation testing
(`tests/test_file_auto_parser.py`, 15 tests): disabling the location gate alone failed exactly
3 tests (the ones specifically requiring it — a bare cache-file name, `settings.local.json`,
and the end-to-end self-ingestion regression test); disabling the name gate alone failed exactly
3 different tests (a project `.mcp.json`, a Downloads `credentials.json`, and its Windows-path
variant); disabling both failed exactly the union (12) while the 3 explicit "must still work"
regression guards (an ordinary research filename, an ordinary CSV, a file outside all config
roots) stayed green throughout all three mutations.

**Known, accepted, NOT closed by this fix (named explicitly, not silently dropped):** this fix
prevents FUTURE ingestion — it does not retroactively scan or clean `~/.claude/cache/parsed/`
or `~/.claude/cache/doc_registry.json` for content cached before the fix landed. The cache files
and registry entries from this incident require manual, user-driven removal (the harness's own
safety rules prohibit an agent from permanently deleting files, even clear cache duplicates).
Content-shape detection (e.g. reusing `lib/security.redact_secrets()` on the parsed JSON before
caching, to catch a secret embedded in an arbitrarily-named file such as a GCP/Firebase
service-account key) was considered and deliberately deferred as a separate, proportionate
follow-up rather than folded into this fix — `redact_secrets()`'s own pattern set does not cover
a PEM-block private key, so it would not have been a complete answer here either.
