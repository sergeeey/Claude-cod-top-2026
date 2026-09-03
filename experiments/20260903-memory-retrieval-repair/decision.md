# decision.md — 20260903-memory-retrieval-repair (PR-1)

## Verdict

- [x] PROMOTE — claim holds; merge to main
- [ ] REPEAT
- [ ] REJECT
- [ ] ARCHIVE

## Result Classification

- [ ] 🥇 Gold
- [ ] 💎 Diamond
- [ ] 🥈 Silver
- [x] 🪨 Stone — a real, needed correctness fix, but not a transferable technique
      beyond this repo's own indexing pipeline. No cross_domain_insights.md entry.

## Evidence Summary

| Check | Result |
|-------|--------|
| Positive control | PASS |
| Negative control | PASS |
| No-collapse tests | 4/4 applicable PASS, 1 N/A documented (see controls.md) |
| Stress tests | 4/4 PASS |
| Substrate gate (2a) | READY |
| Full test suite | 3034 passed, 1 pre-existing unrelated failure, 3 skipped, 2 xfailed |
| ruff / mypy / architecture gates | clean |
| External reconstruction | [VERIFIED-REAL], see result_summary.md |

## Skeptic Concerns (Step 8a)

This PROMOTE is for PR-1 only — a narrow, mechanically verifiable file-discovery
and no-op-skip fix. Per the TZ's cost-discipline note (falsification-ladder.md
§8a), a full adversarial skeptic dispatch is reserved for the PR that carries
real risk of a wrong PROMOTE (PR-4's whole-corpus IDF reweight, PR-5's HOT-tier
scoring change gated by §5.3). Substituting: the GitHub Codex bot review that
already ran on the TZ doc itself (PR #332) caught and corrected the exact design
flaw this PR-1 code independently already avoided (fingerprint-in-sidecar, not
embedded in `tf_index.json`) — recorded as external verification, not a skipped
step. A dedicated isolated-worktree reviewer + Codex bot pass still runs on
PR-1's own pull request before merge, per this session's standing process.

## Caveats

1. The one pre-existing test failure
   (`tests/test_check_global_hooks.py::TestUnmockedImport::test_raises_filenotfounderror_on_a_machine_without_the_hardcoded_path`)
   is unrelated to this change — verified by reproducing it with PR-1's diff
   stashed out entirely (same failure, same message). It reflects the
   documented live-vs-repo hook drift on this machine (`CLAUDE.md`'s own
   "local Windows runs collect a handful more/fewer environment-dependent
   tests" note), not a regression from this PR.
2. This PR does not touch `knowledge_librarian.py`'s HOT/WARM/COLD scoring —
   PR-5 remains a separate, gated PR.
3. `RebuildReport` is a new return type replacing a bare `int`; every call
   site (`hooks/raw_to_wiki.py`) and every test asserting on the return value
   was updated in this same PR — verified via the full-suite run above
   (0 unexpected failures involving `rebuild_index`).

## Floor-Ceiling Interval (Step 4a)

Not applicable to PR-1: this claim is a binary correctness property (a file
either is or isn't discovered by `rglob`; the fingerprint gate either does or
doesn't skip re-indexing), not a continuous metric with room to move between a
null-model floor and a privileged-access ceiling. The floor-ceiling interval
is a real, load-bearing gate for PR-4 (real IDF weighting quality) and PR-5
(HOT-tier ranking score, already named as gated by TZ §5.3) — it is deferred
there explicitly, not skipped silently. Recording this here per the audit
gate's own third-outcome discipline: "not applicable" is a distinct, stated
outcome, not an omission.

## Next

Commit PR-1, push, open PR, dispatch isolated-worktree reviewer, wait CI +
Codex bot comments, merge. Then continue to PR-2 (rel_path as real join key)
per the corrected TZ ordering.
