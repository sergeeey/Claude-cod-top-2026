# decision.md — 20260824-quote-splitting-sweep

**STATUS: RESOLVED**

## Claim

After closing the shell quote-splitting bypass in `hooks/permission_policy.py`
(PR #263), check whether the same vulnerability class (a security-relevant
substring/pattern scan over Bash command text, defeatable by splitting a
sensitive substring across a shell quote boundary) exists in other hooks that
read `tool_input.get("command")`.

## Method

Spawned `Agent(security-audit)` to inspect the 14 hooks that read Bash command
text or check `tool_name == "Bash"`. Instructed to be adversarial per file:
distinguish hooks with a real block/deny/ask consequence from purely
observational/logging hooks (no security finding possible), and to actually
run/trace any candidate bypass rather than theorize.

**Every non-trivial finding independently reproduced myself before fixing**
(`audit-verification-gate.md` protocol — agent's [VERIFIED] is my [INFERRED]
until I run it).

## Findings

| File | Vulnerable? | Verified independently | Fixed |
|---|---|---|---|
| `hooks/agent_tool_scope_guard.py` | **Yes** — `_bash_looks_like_write()` missed `t'e'e`, `c'p'`, `m'v'`, `sed -'i'`, causing `main()` to `emit_permission_decision(decision="allow")` immediately with **zero scope check** — full bypass, same shape as the permission_policy.py reference finding | Yes — reproduced all 4 patterns returning `False` pre-fix | Yes |
| `hooks/security_verify.py` | **Yes** — two distinct issues: (1) `_strip_quotes()` only unwrapped a token fully wrapped in one matching quote pair, missing an embedded quote (`.e'n'v` stayed as-is, `is_sensitive_file` returned False); (2) `_TEE_TARGET_RE`'s literal `\btee\b` never matched `t'e'e` at all, extracting zero targets | Yes — reproduced both, plus confirmed permission_policy.py's own chain-operator/default-ask still fires for these exact strings (mitigates but doesn't excuse the miss) | Yes |
| `hooks/pre_commit_guard.py` | No — uses real `shlex.split(posix=True)` tokenization, which handles quote-splitting correctly by construction | Verified by the audit agent (not independently re-checked by me — LOW priority, negative result, no fix needed) | N/A |
| 6 files (`pattern_extractor.py`, `gitnexus_reindex.py`, `learning_tracker.py`, `auto_capture.py`, `post_commit_memory.py`, `memory_guard.py`) | No — substring checks gate only observational logging/indexing, zero block/deny/ask consequence | Not independently re-checked (correctly out of scope — a missed log entry is not a security finding) | N/A |
| `hooks/skeptic_auto_trigger.py`, `hooks/validation_theater_guard.py` | No — scan tool **output**, not the Bash **command** string; quote-splitting doesn't apply, and both are explicitly advisory-only (cannot block) | N/A | N/A |
| `hooks/commit_test_gate.py`, `hooks/checkpoint_guard.py` | Technically same bypass class, but both are soft-nudge-only (no permission decision at all) — rated LOW, not a security finding | Not fixed (explicitly out of scope: the genuinely dangerous patterns in `checkpoint_guard.py`'s list are independently deny-gated by permission_policy.py's already-fixed `DANGEROUS_PATTERNS`) | No — deliberately left as-is |

## Fixes applied

**`agent_tool_scope_guard.py`**: `_bash_looks_like_write()` now scans a
quote-stripped copy of the command (`command.replace("'", "").replace('"',
"")`) — pure boolean detection, no target-extraction tradeoff to worry about.

**`security_verify.py`**:
- `_strip_quotes()` changed from positional unwrap to blanket removal
  (`token.replace('"', "").replace("'", "")`) — safe because it runs AFTER
  token-boundary extraction, so a legitimately quoted spaced path
  (`"safe dir/.env"`) collapses to the identical result either way.
- Added `_dequote_for_tee_detection()` + a conditional fallback pass in
  `_bash_redirect_targets()`: only runs the `tee` regex against a fully
  dequoted copy when the ORIGINAL command didn't already match `tee`
  literally — avoids mangling a legitimate spaced `tee` target by only
  taking the degraded (no-spaces) extraction path when quote-splitting
  evasion is actually suspected.

## Verification

`pytest tests/test_security_verify.py tests/test_agent_tool_scope_guard.py -q`
→ **58 passed** (54 existing + 4 new regression tests — 2 in each file).
`ruff check` / `mypy --ignore-missing-imports` → clean on both changed files.
Full repo suite (`pytest tests/ -q`) run after these fixes — see this
session's activeContext.md auto-log for the confirmed count.

Every fix in this experiment preserves the legitimate cases already covered
by each file's own existing test suite — confirmed by re-running those suites
unchanged, not just the new regression tests.

## Kill Analysis

- **Killed:** the implicit claim that permission_policy.py's Round-4
  `_dequote()` fix was a one-off, isolated to that single file — false; the
  same literal-substring-scan pattern was copy-pasted (in spirit, not code)
  into at least two other security-relevant gates.
- **Not killed:** `pre_commit_guard.py`'s `shlex`-based approach — confirmed
  robust against the same class, no fix needed. Its pattern (real
  tokenization, not a "strip these two characters" patch) is arguably the
  more durable fix for any FUTURE hook of this kind, and is flagged as such
  below.

## Forbidden claims

1. Does NOT claim every hook in this repo is now free of shell-obfuscation
   bypasses — only the 14 files that read Bash command text were in scope;
   hooks reading other adversarial input (file content, tool output, MCP
   responses) were not audited for their own analogous issues.
2. Does NOT claim `$IFS`-based whitespace substitution, ANSI-C `$'...'`
   quoting, or brace expansion are covered by either fix in this experiment
   — same scope boundary already documented in the permission_policy.py
   Round-4 decision.md, inherited here.
3. Does NOT claim `commit_test_gate.py`'s or `checkpoint_guard.py`'s
   quote-split misses are safe in some absolute sense — only that their
   consequence (a missed soft nudge / reminder) is bounded by
   permission_policy.py's independent, already-fixed enforcement of the
   genuinely dangerous commands, and is not itself a permission decision.

## Next action

None required for this sweep. If a new hook is added that reads Bash command
text for a security decision, prefer `shlex.split(posix=True)` tokenization
(proven in `pre_commit_guard.py`) over a raw substring scan + manual
`_dequote()` — the latter is a narrower patch that has now needed applying
three times in one day (`permission_policy.py`, `agent_tool_scope_guard.py`,
`security_verify.py`).
