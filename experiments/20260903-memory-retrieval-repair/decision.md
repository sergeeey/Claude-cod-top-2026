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
| Stress tests | 6/6 PASS (2 added after reviewer finding, see below) |
| Substrate gate (2a) | READY |
| Full test suite | 3034 passed, 1 pre-existing unrelated failure, 3 skipped, 2 xfailed |
| ruff / mypy / architecture gates | clean |
| External reconstruction | [VERIFIED-REAL], see result_summary.md |

## Skeptic Concerns (Step 8a)

This PROMOTE is for PR-1 only — a narrow, mechanically verifiable file-discovery
and no-op-skip fix. Per the TZ's cost-discipline note (falsification-ladder.md
§8a), a full adversarial skeptic dispatch is reserved for the PR that carries
real risk of a wrong PROMOTE (PR-4's whole-corpus IDF reweight, PR-5's HOT-tier
scoring change gated by §5.3). Substituting: an isolated-worktree `reviewer`
agent (context-blind to this decision.md, working only from the diff and the
commit message) was dispatched against PR-1's own pull request BEFORE merge.

**Finding, verified and fixed (not dismissed):** the reviewer reproduced, with
a tool (monkeypatching `index_wiki_entry()` to its own documented fail-open
contract), that `rebuild_index()`'s `except Exception: failed += 1` could
never observe an internal indexing failure — `index_wiki_entry()` already
swallows its own exceptions two frames down, so every such failure was
counted as `indexed`, contradicting `RebuildReport`'s stated purpose. The
reviewer additionally showed this compounds with the fingerprint gate: a
permanently-failing file's stat still gets fingerprinted, so the failure
becomes permanently invisible to any later `rebuild_index()` call.

- Concern: internal indexing failures counted as success → **Fixed**:
  `index_wiki_entry()` and `_save_tfidf_index()` now return `bool`;
  `rebuild_index()`'s loop checks the return value instead of relying only
  on an exception crossing two function boundaries. See stress_tests.md Case 5.
- Concern: a failed rebuild's fingerprint permanently hides the failure →
  **Fixed**: the fingerprint is now saved only `if failed == 0`, forcing a
  retry of the whole corpus on the next call after any failure. See
  stress_tests.md Case 6.
- Concern (P2, same review): `_save_fingerprint()` used a non-atomic
  `write_text()` unlike its sibling `_save_tfidf_index()` → **Fixed**: matched
  the existing tmp-file + `os.replace()` pattern already used in this file.

Separately, the GitHub Codex bot review that ran on the TZ doc itself
(PR #332) caught and corrected the fingerprint-storage design risk this PR-1
code already avoided independently (sidecar file, not embedded in
`tf_index.json`) — recorded as additional external verification. A Codex bot
pass also runs on PR-1's own pull request before merge, per this session's
standing process.

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
