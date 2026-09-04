# Session history — 2026-08-29 to 2026-09-01

Moved out of `activeContext.md`'s CURRENT STATE table per this repo's own
hygiene rule (a single cell had grown to 52K characters once before, breaking
the Read tool — see the top-of-file warning comment). This file holds the
detailed narrative; CURRENT STATE keeps only the current pointer.

## 2026-08-29 — gate-kit harvest finding (boyko-benchmark / BILUH)

A `/harvest` run on the unrelated `boyko-benchmark` (BILUH) project flagged
its "Verdict Machine" — tiered G1-G6 gates, an Operator-Independence
diagnostic, an Oracle Adequacy check, and a Kill Analysis template, all
implemented as executable code, not just rules-text — as a reusable
cross-project pattern.

Verified against this repo before accepting the finding:
`grep -rli "operator.independence|oracle.adequacy" --include="*.py"` returned
0 hits, and `templates/oracle_audit.yaml` exists only as a hand-filled
template with no computational engine behind it. Confirmed: this repo has
the exact same gap the harvest finding named — `falsification-ladder.md`,
`estimand-ops.md`, `perelman-audit.md`, and `audit-verification-gate.md`
describe the Oracle Adequacy Gate and Skeptic Response Matrix as LLM
instructions, with no code that computes a tiered verdict from data.

Candidate: extract BILUH's harness into a project-agnostic `gate-kit`
(`Observable`/`Gate`/`Arm` abstractions) — but pilot it on ONE other active
physics project first (N-7-GeoSpectra-Lab or Buckholtz), not in this repo
first. Kill condition from the harvest finding itself: if porting to a
second project needs rewriting more than half the harness, the abstraction
isn't general enough — archive as reference only. Only after a pilot
survives that gate does it become a `skills/registry.yaml` entry here,
formalizing `audit-verification-gate.md` as code.

## 2026-08-30 — Distill-Yourself evaluated, installed, patched, tested

`Distill-Yourself` (github.com/QuantaAlpha/Distill-Yourself) was proposed as
a tool for searching/distilling past Claude Code session history. Read the
full source (4100+ lines across key modules) before trusting its README
claims — all three headline mechanisms (L1/L2/L3 distillation layers,
preview-before-write gate, explicit truncation marker) verified accurate in
the code, not just the docs.

Installed to `C:/Users/serge/tools/Distill-Yourself` (`uv venv` + `uv pip
install -e .`). Found and fixed a real bug blocking Windows use entirely: an
unconditional `import fcntl` (POSIX-only) in `chatview/index.py` and
`chatview/utils/sync.py` crashed 16 of ~40 test files at collection and the
CLI itself. Patched with a `sys.platform == "win32"` branch to
`msvcrt.locking()` (byte-range lock + retry loop, since msvcrt has no
infinite-block primitive).

Verified end-to-end on real `~/.claude/projects/` data post-fix: `distill
refresh` indexed 270 sessions across 76 projects; `distill search`/`distill
read-window` returned real, correct hits from this very session, and
`read-window` self-reported `outputTruncated=false` plus an `indexState=stale`
warning exactly as designed. Test suite: 0 of ~40 files collectable before
the fix → 653 passed / 32 failed / 6 skipped after. The remaining 32 are
unrelated, pre-existing Windows path-handling gaps (e.g. `project_identity.py`
assumes POSIX-relative paths and breaks on Windows temp/drive-letter paths)
— confirmed out of scope for this fix and left untouched.

Two patterns ported into `rules/memory-protocol.md` as new sections:
**Preview-Before-Write Gate** and **Explicit Truncation Marker**.

Open question, not yet decided: whether to upstream the fcntl fix to
QuantaAlpha as a PR — publishing to a third-party public repo requires the
user's own explicit go-ahead, not assumed.

## 2026-09-01 — oncall-kit corroboration + PR #293/#294 saga

An `anthropics/oncall-kit` scan (verified: real repo, 76 stars, quoted
phrases confirmed verbatim against the raw README) independently converged
on the same holdout/promotion-gate/provenance-tag primitives as the gate-kit
harvest finding above — recorded as `knowledge/research/repo-intel/repos/Repo
Intel — Oncall Kit.md` in the Obsidian vault, a second, independent
real-world reference point for the still-unscheduled gate-kit pilot.

Same day, a `/tracy` strategic pass named the Stop-hook branch
(`feat/commit-test-gate-stop-hook`, done and tested since 2026-08-28 but
never pushed) as the session's A1/frog. Pushed and opened as PR #293.

CI caught a real, legitimate issue on PR #293's first run: the README's
test-count badge was stale relative to the branch's own new tests. Fixing it
took three iterations because `main` kept moving underneath the branch
during the fix cycle (test count churned 2854 → 2873 → 2882 across
concurrent merges from other sessions), and the first fix attempt used a
local Windows pytest count (2888) instead of the CI-measured Linux count
(2882) — exactly the trap this repo's own CLAUDE.md documents. Resolved by
reading the number directly from the PR's own failing CI log each time,
per convention, instead of trusting a local count. PR #293 merged clean
after that.

A second, independently-improved uncommitted version of
`commit_test_gate.py` was found sitting in `main`'s working tree after the
merge (a `hook_main()` crash-safety wrap on the hook's non-Stop paths, plus a
trimmed `registry.yaml` comment) — not lost, not overwritten: stashed,
reapplied after syncing with the merged PR #293 content, one small merge
conflict in `registry.yaml` resolved by keeping the less-redundant comment
(the fuller version's reasoning is otherwise duplicated in the hook's own
module docstring). Verified the wrap's safety precondition first — that
`hook_main()` actually propagates a wrapped function's own `SystemExit` code
instead of discarding it (fixed 2026-08-29, confirmed still true in
`hooks/lib/runtime.py`) — before committing. Shipped as PR #294, merged
clean.

Branch backlog triaged from 9 to 4: `docs/memory-split-activecontext-consolidation`,
`feat/session-save-split-raw-to-wiki`, and `fix/ci-registry-schema-repair`
were already merged via earlier PRs but never had their remote branch
deleted (verified zero unmerged commits before deleting).
`docs/sync-readme-test-count-and-activecontext-merge-status` was 0 commits
ahead of `main` — fully stale, deleted. `feat/elai-independence-mdr` showed
6 commits ahead by SHA, but the actual files (`independence_scorer.py`,
`mutation_tracker.py`, registry entries) were confirmed already present on
`main` via PR #260's squash-merge (different SHAs, same content) — deleted
once content presence was verified, not just PR state.

The remaining 4 branches were left untouched on purpose — each needs a
decision only the user can make: `chore/focusos-evening-snr-{20260731,20260801}`
(draft PRs #249/#250), `docs/skill-disambiguation-deep-research-tracy-fix`
(the user's own planned `git branch -D`), and
`fix/backport-null-retroscan-identifier-scan` (an intentionally-preserved
unmerged skill).

## 2026-09-04 — knowledge_librarian.py `## Current Focus` header bug (PR #361)

Owner pasted an external analysis of a cross-project incident: a different
project sharing this same global hook (GeoScan) uses suffixed
`## Current Focus (date, topic) [WS:branch]` headers. `_read_current_focus()`'s
exact `line.strip() == "## Current Focus"` check silently matched nothing
against them, and `main()`'s `if not focus.strip(): sys.exit(0)` meant the
hook injected ZERO knowledge for that project's sessions — not a degraded
fallback, a complete no-op. Verified both parts of the claim with tools
before acting (audit-verification-gate.md discipline) rather than trusting
the pasted analysis at face value: read the exact line, confirmed the
exit-on-empty behavior in `main()`.

This repo's own `activeContext.md` doesn't use a `## Current Focus` header
any more (replaced by `## CURRENT STATE` in the 2026-08-28 split), so the
bug was latent here but real for other installations — fixed at the
canonical source anyway, same pattern as the #354 `post_commit_memory.py`
fix (fix generically, not just for this repo's own current usage).

Fix: `_CURRENT_FOCUS_RE = re.compile(r"^## Current Focus(?:\s*\([^)]*\))?(?:\s*\[WS:[^\]]*\])?\s*$")`
matches the exact header plus the two supported suffix forms — a trailing
`(...)` date/topic parenthetical and/or a `[WS:...]` workstream tag — while
rejecting anything else. 8 tests in `tests/test_knowledge_librarian_current_focus.py`;
verified 4 of the original set genuinely FAIL against the pre-fix code
(`git stash` the hook file, re-run, confirm red, `stash pop`) — not a
tautology.

**Codex review, PR #361, 3 findings, all verified before acting — 2 real
code/doc bugs, 1 real hygiene issue:**

1. The first draft's regex (`^## Current Focus(\s|$)`) accepted ANY
   whitespace-delimited text after the header, not just the two supported
   suffix forms — verified directly with a standalone regex script that
   `"## Current Focus Archive"` matched and would have returned a stale
   section's body as if it were the live focus. Tightened to the grammar
   above; added `test_unsupported_trailing_text_is_rejected`.
2. This file's own transcription of the fix (in `activeContext.md`'s
   CURRENT STATE row before this trim) wrote `r"^## Current Focus(\s|\$)"`
   with a stray backslash before `$` — a literal-dollar-sign regex that
   would NOT match even the plain exact header, contradicting both the
   real source code and the passing exact-header test. A transcription
   error, not a code bug, but exactly the kind of drift that could mislead
   a future agent reconstructing the change from memory alone.
3. The CURRENT STATE row itself had grown into ~2.1KB of incident
   narrative, test methodology, and session commentary — directly against
   this file's own stated rule (see its top-of-file warning comment) that
   CURRENT STATE stay short and narrative/dated material live in
   `history/`. This section is the fix for that: the narrative lives here,
   CURRENT STATE keeps a short pointer.

Deliberately NOT acted on from the same pasted external analysis (out of
this repo's scope, belongs to the other project): SEDAR/НГС claims left
`UNVERIFIED`, the old `_auto/patterns.md` duplicate left alone, the other
project's own 2805-line `activeContext.md` archival left alone.

**Session note (`/tracy` invoked mid-fix, before this PR's Codex round):**
flagged a real risk that the autonomous small-fix queue this session (test-
count sync, hash annotations, doc-completeness, and now a cross-project bug
import) may have quietly substituted for the owner's own 2026-09-02 Default
Focus Bias decision ("§8 work NOW, not more §7 hardening" — see this file's
CURRENT STATE row of that name). Plan: finish this fix (it was real, cheap,
half-done), then check in with the owner before opening the next PR rather
than continuing on inertia.
