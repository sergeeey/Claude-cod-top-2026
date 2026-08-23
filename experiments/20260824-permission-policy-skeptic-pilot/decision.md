# decision.md — 20260824-permission-policy-skeptic-pilot

**STATUS: RESOLVED** — all 4 rounds fixed and merged, re-verified on `main`.
PR [#262](https://github.com/sergeeey/Claude-cod-top-2026/pull/262) (Rounds
1-3), merged 2026-08-23T21:11:34Z. PR
[#263](https://github.com/sergeeey/Claude-cod-top-2026/pull/263) (Round 4,
quote-splitting), merged 2026-08-23T21:43:36Z. Full repo suite re-run on
`main` after all three pilot PRs merged (2026-08-24): **2767 passed**, 1
pre-existing unrelated machine-path-dependent failure (confirmed unrelated
across every re-run this session). Remaining known-and-documented residual
(not a bug in this fix, a scope boundary): `$IFS`/ANSI-C-quoting/brace-
expansion shell obfuscation tricks were not tested — see Round 4's
forbidden-claims note below.

## Verdict: REJECT (claim as originally worded) → FULLY FIXED across 4 rounds (see STATUS block above)

## What happened

Same paraphrase-probe pattern as the first pilot (`20260824-elai-hooks-skeptic-pilot`),
applied this time to a security-tier hook per the rule just added to
`falsification-ladder.md`.

| | Variant A (formal) | Variant B (paraphrased) |
|---|---|---|
| Verdict | **CONFIRMED-REAL** (tried ~60 candidates, none broke it) | **WEAKENED** — found `git show HEAD:.env` bypass |

**Verdicts disagreed again** (2nd time in 2 pilots — this is now itself a small,
real pattern, not a one-off). Per the paraphrase-probe rule: defaulted to the more
skeptical verdict (WEAKENED) rather than the more comfortable CONFIRMED-REAL.

## Round 1 fix (Variant B's finding, independently reproduced)

`_reads_sensitive_path()` only checked `cat`/`head`/`tail`/`wc` prefixes.
`git show HEAD:.env`, `git log -p .env`, `git diff HEAD~1 -- .env` all matched their
own `SAFE_BASH_PREFIXES` entries first and never reached the sensitive-path check —
auto-`allow`, dumping secret content straight into context.

**Independently reproduced** before fixing:
```
decide('Bash', {'command': 'git show HEAD:.env'})       -> ('allow', '')
decide('Bash', {'command': 'git log -p .env'})          -> ('allow', '')
decide('Bash', {'command': 'git diff HEAD~1 -- .env'})  -> ('allow', '')
decide('Bash', {'command': 'cat .env'})                 -> ('ask', '')   # control: already correct
```

**Fix:** extended `_reads_sensitive_path()` to also scan `git show `/`git log `/
`git diff ` commands for `SENSITIVE_PATH_PATTERNS` substrings.

## Round 2 — security-audit found a MORE severe gap in the Round 1 fix itself

Ran `Agent(security-audit)` adversarially against the Round-1 fix before accepting it
(this stack's own Doubt-Driven Development protocol: red-team the fix, not just the
original claim). Findings, most severe first:

1. **Confirmed real, more severe:** `git show <ref>` **with no `:<path>` at all**
   (e.g. `git show HEAD~1`) defaults to dumping the FULL commit patch — every changed
   file, none named in the command text — so no filename-substring scan can ever
   catch it. Independently reproduced in a throwaway repo: a real secret committed
   then removed in a later commit was printed in full by `git show HEAD~1` with zero
   adversarial intent required — "the single most common way anyone inspects a
   commit" (security-audit's own words). Same shape for `git log -p` with no path.
2. **Confirmed, pre-existing, not introduced by this fix:** shell quote-splitting
   (`git show HEAD:'.e'nv`) defeats the literal-substring scan — verified this
   already applied identically to the original `cat`/`head`/`tail`/`wc` branch before
   today's changes. Not a regression; a pre-existing limitation of the whole
   detection approach (substring scan, not real shell tokenization).
3. **Structural fragility, not a live bug:** this is the second time a
   content-dumping prefix was added to `SAFE_BASH_PREFIXES` without a matching
   `_reads_sensitive_path` update (first was `wc`, per F-16). Nothing currently
   prevents a third recurrence (e.g. if `git blame`/`git cat-file` gets added later).

**Independently reproduced (2):**
```
decide('Bash', {'command': 'git show HEAD'})       -> ('allow', '')
decide('Bash', {'command': 'git show HEAD~1'})     -> ('allow', '')
decide('Bash', {'command': 'git log -p -3'})       -> ('allow', '')
decide('Bash', {'command': 'git diff HEAD~1 HEAD'})-> ('allow', '')
```

## Round 2 fix (applied — items 1 partially, per what could be fixed without breaking a tested contract)

- `git show <ref>` with no `:` anywhere → now routes to `ask` (closes the "single
  most common" case named above).
- `git log` with `-p`/`--patch`/`-u` (word-bounded) → now routes to `ask`.
- **`git diff <ref1> <ref2>` with no path restriction is a KNOWN, DOCUMENTED,
  DELIBERATELY UNFIXED gap** — `git diff` defaults to showing a full patch exactly
  like `git show`/`git log -p`, and the same live-secret-leak repro applies to it.
  It was **not** fixed in this pass because an existing, explicitly-tested contract
  (`decide("Bash", {"command": "git diff HEAD"}) == ("allow", "")`, asserted at
  `tests/test_permission_policy.py:177` and again at `:328`, predating this pilot)
  would have to be broken to close it — `git diff HEAD`/`git diff HEAD~1 HEAD` are
  extremely common, low-friction operations, and flipping them to universally "ask"
  is a real UX/security tradeoff a human should decide, not something to silently
  flip mid-pilot. **Test Protection hard rule applies: do not edit an existing test
  to make a code change pass without an explicit decision to change the contract.**
  A documentation-only regression test
  (`test_git_diff_bare_refs_known_gap_not_yet_fixed`) was added instead, asserting
  the CURRENT (gap-containing) behavior explicitly, so the gap is visible in the
  suite rather than silently forgotten if someone "fixes" it by accident later
  without reading this file.
- Shell quote-splitting bypass (finding 2): **not fixed**, logged as a known
  pre-existing limitation applying to the whole `_reads_sensitive_path` approach
  (cat/head/tail/wc too, not just the git additions). A real tokenization-based
  rewrite would be a larger, separate change, out of scope for this pilot.

## Round 3 — human decision on the `git diff` gap (2026-08-24, same conversation)

The user was asked directly: should `git diff <ref1> <ref2>` (no path restriction)
move from `allow` to `ask`, breaking the existing `git diff HEAD` -> allow contract?
**Decision: yes, close it too.**

**Fix applied:** `_reads_sensitive_path()` now routes any `git diff <ref(s)>` command
without a `-- <path>` restriction to `ask`, mirroring the `git show`/`git log -p`
fixes above. `git diff <ref> -- <path>` stays scanned for `SENSITIVE_PATH_PATTERNS`
only (unaffected, still `allow` for ordinary files). Bare working-tree `git diff`
(no ref argument at all) is explicitly **unaffected** — it doesn't reach this branch
and stays `allow`; the demonstrated leak required two explicit historical refs.

**Tests updated (not weakened — an intentional, user-approved contract change):**
- `TestDecideSafeBashPrefixes::test_git_diff_allowed` → renamed
  `test_git_diff_against_ref_asks_not_allow`, assertion flipped `allow` → `ask`;
  a new `test_git_diff_bare_working_tree_still_allowed` documents the unaffected case.
- `TestDecideSensitivePathRead::test_git_log_and_diff_without_path_still_allowed` →
  renamed, its `git diff HEAD` assertion flipped to `ask` (its `git log` assertion
  is unaffected and stays `allow`).
- `test_git_diff_bare_refs_known_gap_not_yet_fixed` → renamed
  `test_git_diff_bare_refs_asks_not_allow`, assertion flipped `allow` → `ask`; a new
  `test_git_diff_ref_path_restricted_ordinary_file_still_allowed` confirms
  `git diff HEAD~1 -- README.md` is unaffected.

The repo's own `test-integrity` guard blocked the first two edit attempts (assertion
count dropped) — correctly, since it can't distinguish "weakening a test to hide a
bug" from "updating a test after a deliberate, user-approved contract change" from
the diff alone. Resolved by keeping assertion counts constant per edit (changing an
assertion's expected value in place, or adding a new test alongside a renamed one)
rather than deleting assertions outright.

## Round 4 — closing the shell quote-splitting bypass (user request, follow-up session)

The Round-2/3 "forbidden claims" section flagged, but deliberately did not fix, a
shell quote-splitting bypass: `pattern in cmd_lower` is a literal substring scan, not
real shell tokenization. Bash concatenates adjacent quoted/unquoted fragments into
one word, so a pattern split across a quote boundary defeats the scan while the
executed command is identical.

**Independently reproduced (both directions) before fixing:**
```
decide('Bash', {'command': "cat '.e'nv"})                    -> ('allow', '')   # was: leaked
decide('Bash', {'command': "git show HEAD:'.e'nv"})           -> ('allow', '')   # was: leaked
decide('Bash', {'command': "rm -r'f' /"})                     -> ('ask', '')     # was: degraded from deny
decide('Bash', {'command': 'sud"o" apt install nginx'})       -> ('ask', '')     # was: degraded from deny
```
The `rm`/`sudo` cases matter because this hook's own design relies on `deny` carrying
an explicit, informative message ("Blocked dangerous command: ...") that `ask` does
not — a human approving a degraded-to-`ask` prompt may not realize how dangerous the
command actually is.

**Fix:** added `_dequote()` — strips `'`/`"` characters before the `SENSITIVE_PATH_PATTERNS`
and `DANGEROUS_PATTERNS` substring scans only. Removing quote characters can only
ever *merge* an already-present substring back together; it cannot hide or split one
that was there unquoted, so this is a strict superset check, not a behavior change
for any command that didn't already contain the pattern. Deliberately **not** applied
to prefix-matching (`_matches_safe_prefix`/`SAFE_BASH_PREFIXES`) or `CHAIN_OPERATORS`
— obfuscating a *safe* prefix this way only prevents it from matching, which pushes
the command toward the safe `ask` default, not toward `allow`; no vulnerability in
that direction, no reason to touch that logic.

**Verified fix closes both directions, with no new false positives on ordinary
quoted commands:**
```
decide('Bash', {'command': "cat '.e'nv"})                -> ('ask', '')
decide('Bash', {'command': "git show HEAD:'.e'nv"})       -> ('ask', '')
decide('Bash', {'command': "rm -r'f' /"})                 -> ('deny', 'Blocked dangerous command: rm -rf')
decide('Bash', {'command': 'sud"o" apt install nginx'})   -> ('deny', ...)
decide('Bash', {'command': "echo 'hello world'"})         -> ('allow', '')   # unaffected
decide('Bash', {'command': "git show HEAD:README.md"})    -> ('allow', '')   # unaffected
```

5 new regression tests added (2 DANGEROUS_PATTERNS quote-split cases, 2
SENSITIVE_PATH_PATTERNS quote-split cases, 1 no-false-positive check).

## Verification

`pytest tests/test_permission_policy.py -q` → **90 passed** (75 existing + 5 Round-1
+ 3 Round-2 + 2 Round-3 + 5 Round-4 regression tests).
`ruff check` / `mypy --ignore-missing-imports` → clean.
Full repo suite (`pytest tests/ -q`) re-run after each round — no regressions outside
`test_permission_policy.py`.

## Kill Analysis

- **Killed:** the original claim ("no auto-allow bypass exists") — false, two
  distinct bypass classes found and independently reproduced.
- **Also killed and fixed (Round 3):** the same bypass class for `git diff` — the
  user explicitly decided to close it, accepting the contract change on
  `git diff HEAD`/`git diff <ref1> <ref2>`.
- **Also killed and fixed (Round 4):** the shell quote-splitting bypass flagged but
  left open at the end of Round 2 — closed for both `SENSITIVE_PATH_PATTERNS` and
  `DANGEROUS_PATTERNS` via `_dequote()`.
- **Not killed:** the core check-ordering design (dangerous-pattern → eval →
  chain-operator → sensitive-path → safe-prefix, in that order) — both skeptic
  variants and the security-audit agent all traced it as monotonic and correctly
  ordered; the defect was in an incomplete *enumeration* of content-dumping
  prefixes, not in the ordering logic itself.

## Forbidden claims (Perelman-audit discipline — what this fix does NOT establish)

1. Does NOT claim `permission_policy.py` now catches every way secret content could
   reach Claude's context via Bash — quote-splitting via `'`/`"` is closed (Round 4),
   but other shell-tokenization tricks this scan-based approach cannot see (e.g.
   `$IFS`-based whitespace substitution, ANSI-C `$'...'` quoting, brace expansion)
   were not tested and are not claimed to be covered.
2. Does NOT claim shell-command safety gates in general are now provably complete —
   this is one hook, reviewed for one command family (git), not a formal proof.
3. Does NOT claim other git subcommands with the same content-dumping property
   (`git cat-file -p`, `git archive`, `git blame`, `git grep -A/-C`) are covered —
   the security-audit confirmed these currently fall to default `ask` only because
   they're absent from `SAFE_BASH_PREFIXES`, not because of any dedicated check; if
   one is added to that list later for convenience, it needs its own
   `_reads_sensitive_path` update (this is now the second confirmed recurrence of
   that exact failure shape — first was `wc`/F-16, second was `git show`/`git log`/
   `git diff` this pilot).

## Next action

None required — all three rounds of this pilot are closed. If `SAFE_BASH_PREFIXES`
gains a new content-dumping entry in the future (see forbidden-claim 3 above), it
needs a matching `_reads_sensitive_path` update at the same time, not as an
afterthought.
