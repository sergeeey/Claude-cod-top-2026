# decision.md — 20260824-permission-policy-skeptic-pilot

## Verdict: REJECT (claim as originally worded) → PARTIALLY FIXED, one gap remains open by decision

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

## Verification

`pytest tests/test_permission_policy.py -q` → **83 passed** (75 existing + 5 Round-1
regression tests + 3 Round-2 regression tests, one of which documents the known gap
rather than asserting safety).
`ruff check` / `mypy --ignore-missing-imports` → clean.

## Kill Analysis

- **Killed:** the original claim ("no auto-allow bypass exists") — false, two
  distinct bypass classes found and independently reproduced.
- **Partially killed / open by decision:** the *narrower* re-stated claim ("no
  auto-allow bypass exists for git show/log with unrestricted patch output") —
  fixed for `git show`/`git log`; explicitly NOT claimed for `git diff` pending a
  human tradeoff decision (see "Next action").
- **Not killed:** the core check-ordering design (dangerous-pattern → eval →
  chain-operator → sensitive-path → safe-prefix, in that order) — both skeptic
  variants and the security-audit agent all traced it as monotonic and correctly
  ordered; the defect was in an incomplete *enumeration* of content-dumping
  prefixes, not in the ordering logic itself.

## Forbidden claims (Perelman-audit discipline — what this fix does NOT establish)

1. Does NOT claim `permission_policy.py` now catches every way secret content could
   reach Claude's context via Bash — the quote-splitting bypass and the `git diff`
   gap are both known and unfixed.
2. Does NOT claim shell-command safety gates in general are now provably complete —
   this is one hook, reviewed for one command family (git), not a formal proof.
3. Does NOT claim the `git diff` gap is low-risk — it was reproduced with a real
   leaked secret; it is left open by an explicit human-tradeoff decision, not because
   it was judged safe.

## Next action — requires a human decision

**Should `git diff <ref1> <ref2>` (no path restriction) be changed from `allow` to
`ask`?** This breaks two existing tests (`test_permission_policy.py:177`, `:328`) and
adds confirmation friction to an extremely common command
(`git diff HEAD`/`git diff HEAD~1 HEAD`), in exchange for closing a demonstrated
secret-leak path. Flagged to the user in the same conversation this pilot ran in;
not decided here.
