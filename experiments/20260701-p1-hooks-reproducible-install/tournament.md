# Variant Tournament — install.sh duplicate-backup fix

Oracle: real `install.sh --profile=standard --target=<fresh dir>` run + `find *.backup.*` +
targeted negative-control re-seed (see oracle_audit.yaml, falsification_contract.yaml).
Success metric (from intent_card.yaml): `clean_install_acceptance_pass_rate`, MCID = all 5
findings resolved + 0 new findings.

## Variant A — Content-identity check inside `handle_conflict()` (SHIPPED, commit 1d787bb)

Compare candidate content against existing `$dst` via `cmp -s`; short-circuit to `"skip"`
(no prompt, no backup) only on byte-identical content. Applied uniformly to `safe_copy()`
(compares raw `$src`) and `safe_copy_template()` (compares the *rendered* tmp file, since
template substitution happens before the comparison would be meaningful).

- Positive control: **PASS** (0 backups, `test-install-target-2`)
- Negative control: **PASS** (real diff → prompt + backup + replace, `test-install-target-3`)
- Blast radius: touches 1 shared function (`handle_conflict`) + 2 call sites — every other
  `safe_copy*` caller benefits automatically, including future ones.
- Matches existing conventions: yes — `backup_file()`/`handle_conflict()` are already the
  single chokepoint for all file-conflict decisions in this installer; extending that
  chokepoint is the smallest correct diff.
- New blind spots: symlink targets (`safe_link`) are not covered by this check — a
  symlink-mode re-install could still churn unnecessarily. Documented as a known limitation
  in falsification_contract.yaml, not silently dropped.

## Variant B — Per-run "already written" tracking set

Maintain a bash associative array of dst paths written earlier in the SAME run; if a dst is
already in the set, skip the second write outright (no `cmp`, no `handle_conflict` call at
all for the duplicate).

- Would pass the positive control (0 backups) — the intra-run duplicate is what's
  happening here.
- Would presumably pass the negative control TOO, but for the wrong reason: it wouldn't
  even look at content, just "have I already touched this path this run" — so if
  `install_minimal` wrote a DIFFERENT (buggy) version of integrity.md than `install_rules`
  would have written from the canonical source, Variant B would silently keep the first
  (possibly wrong) one instead of ever comparing. This is a real correctness gap: it treats
  "already handled" as equivalent to "correct", which isn't true in general (only true for
  the CURRENT bug where both writes originate from the same source file).
- Simpler code, narrower fix, but encodes an assumption ("both writes are always meant to
  produce the same content") that Variant A doesn't need to make.

**Verdict: weaker than A — passes today's specific bug but is falsifiable by a hypothetical
future case where install_minimal and install_rules diverge in intent.** Not chosen.

## Variant C — Remove the duplication at the source (restructure install_minimal/install_rules)

Change `standard`/`full` profile dispatch to call ONLY `install_rules` (which already covers
`integrity.md`+`security.md` as part of "all rules"), and reserve `install_minimal`'s
selective 2-file copy for when `minimal` is the ONLY layer run (i.e. move the CLAUDE.md
templating into its own step, and drop the redundant rules copy from `install_minimal`
entirely when a fuller profile will run afterward).

- Would eliminate the duplicate write entirely rather than papering over it with a
  comparison — arguably the more "correct" fix in a vacuum.
- Rejected for THIS PR on scope grounds (matches the user's own instruction not to touch
  `sync_global_skills()`'s design for similar reasons): restructuring the Layer 1/Layer 2
  boundary changes what `minimal` profile users get if they later upgrade to `standard` via
  a second `install.sh` run (not tested in this session), and risks a second-order
  regression in a code path this audit did not exercise (Layer 1 → Layer 2 upgrade path).
  Variant A fixes the observed symptom with a small, local, low-blast-radius change; Variant
  C is a legitimate future refactor but is out of scope for "fix clean install
  reproducibility" as scoped in intent_card.yaml (`out_of_scope` did not list this
  explicitly — documented here as a **scope gap in the intent card**, corrected for next run).

**Verdict: more thorough, deferred.** Flagging as a candidate for a follow-up PR, not
rejecting the idea — this is different from Variant B, which is rejected on correctness
grounds, not scope grounds.

## Ranking

1. **Variant A (shipped)** — passes both controls as [VERIFIED-REAL], smallest correct
   blast radius, matches existing chokepoint convention.
2. Variant C — arguably more correct long-term, deferred as a scope decision, not a defeat.
3. Variant B — rejected: encodes a false-in-general assumption, only "works" because
   today's specific two writers happen to agree.

## Stage 5 — Red-Team (context-blind, independent agent, code+claim only)

**Verdict: CONFIRMED.** Given ONLY the claim + the raw functions (no session history, no
reasoning chain — per Context Asymmetry Rule), the red-team agent tried 4 falsification
angles (spurious skip on fresh install, silent skip of a genuine conflict, TOCTOU race,
crash/wrong-file) and could not break the claim on any data-loss/safety axis.

One real, non-data-loss gap surfaced: the `cmp`-triggered `skip` path is silent (no
`info`/`warn` line), unlike the interactive skip which shows `warn "File exists:"` first.
Both increment the same `SKIPPED_FILES` counter, so the final summary can't distinguish
"skipped because identical" from "skipped because user chose keep-existing." Logged as a
LOW-severity follow-up, not blocking this PR.

Notable refinement from the red-team (not a contradiction of the shipped fix, but a
correction to my own framing above): a genuinely fresh install NEVER reaches the `cmp`
branch at all — `[ ! -f "$file" ]` returns `"replace"` before the identity check runs. The
guard's real target is the INTRA-RUN duplicate write (install_minimal writing
integrity.md, then install_rules writing the same path again in the same run), not
"spurious backups on fresh install" as a category. This matches what was actually observed
(0 backups on `test-install-target-2` because the *second* write in the same run hit the
new `cmp` guard, not because the first write was suppressed).
