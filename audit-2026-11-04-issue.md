# Issue draft — not published

Title: audit: quality regression detected

Repository: sergeeey/Claude-cod-top-2026

Status: GitHub connector creation was blocked: `MCP tool call requires approval, but approval policy is never`.

---

Quality Audit — 2026-11-04

Reviewed PRs #540 and #541 in the exact range `c29067567aecd67096ef44ad5601e4622af73113..1792744c9f3b49f6aa5398f52dd6c86c9b0fb8dc`.

**Overall: 6.75/10. Would ship: NO (REWORK).**
The automation explicitly requires this issue when the overall score is below 7.

| PR | Architecture/correctness | Security/integrity | Trend alignment | Verification/automation | Mean |
|---|---:|---:|---:|---:|---:|
| #540 | 5 | 7 | 7 | 6 | 6.25 |
| #541 | 6 | 8 | 8 | 7 | 7.25 |

Scores are reviewer judgments, not calibrated measurements of Claude's ability.

### Required corrections

- [ ] **F1, MEDIUM, #540:** Prevent a false null when a measured beneficial subset is cancelled by another intervention. In `skills/extensions/boyko-constraint-engine/scripts/constraint_rank.py:295-325`, a complete A/B/C table with baseline and all rows 0.50 except AB=0.90 (noise=.005, repeats=4, MCID=.03, all guards=0) returns `NO_CONSTRAINT_DETECTED` while also returning `best_clean_subset=[A,B]`, value .90, and a complementary AB interaction .40. The trade-off branch requires positive solo gains, so it misses this case. Check measured subsets before issuing a null verdict; add this three-candidate regression.
- [ ] **F2, MEDIUM, #541:** Avoid treating metadata as a verdict in `scripts/build_research_catalog.py:114-118`. `## Result\n\n**EXP_2026_11_04** was inspected; no verdict was reached.` changes from base `UNKNOWN` to `EXP_2026_11_04`; `## Result\n\n**DRAFT_PENDING_REVIEW**` becomes a verdict too. Require explicit verdict semantics or preserve ambiguity; add underscore-ID/status negative controls while retaining long-token and same-line-heading positive controls.
- [ ] **F3, MEDIUM guidance gap, #540:** Clarify `references/system-card.md:38-41`: a worktree/copy and Python `-I` do not constrain untrusted code's OS access. A harmless synthetic canary confirms `python -I` can read an explicitly supplied file outside the script directory. Require an existing restricted execution boundary or keep probes to inspection when unavailable. No secret access, sandbox escape or destructive action was demonstrated.
- [ ] **F4, LOW, #540:** Validate finite positive costs, finite nonnegative MCID and actual boolean direction. Currently an infinite cost is emitted as `Infinity`; NaN MCID bypasses comparisons; `higher_is_better="false"` silently selects higher-is-better.
- [ ] **F5, LOW, #540:** Make type-check scope explicit and fix the ranker's errors. With Python 3.11.13/mypy 1.20.0, explicitly checking the catalog parser plus ranker reports 34 errors in the ranker. CI's mypy command covers `hooks/ scripts/`, not skill-local scripts. This does not prove the author's exact earlier command failed; it exposes missing coverage of the new file.

Sources for F3/F4: [Python -I](https://docs.python.org/3.11/using/cmdline.html#cmdoption-I), [Python JSON nonfinite values](https://docs.python.org/3/library/json.html#infinite-and-nan-number-values).

### Verification

- Reviewed all 22 changed files under all four review modes; exact target archive isolated from the dirty working tree.
- 79 tests passed; two randomized/modeling tests deliberately deselected under project rules, without changing tests.
- Ruff, doc-count sync and architecture checks passed. Explicit mypy failed as noted.
- Bounded synthetic probes reproduced F1/F2/F4 and F3's canary behavior. No real-world prevalence or production validation claim.
- No new credential, injection execution sink or async race was found in the reviewed additions; this is a scoped review, not a repository-wide security certification.
- Prior range audit: 7.75; this batch: 6.75. The drop is descriptive, not statistically established model regression.

Full report saved locally as `audit-2026-11-04.md`. Requested `.codex/reports/audit-2026-11-04.md` was blocked by the environment's read-only `.codex` permissions (Access denied). Local replay artifacts: `tmp/audit-20261104-1792744/probes.py`, `probe-results.json`, `full.diff`, `integrity.json`.

The private calibration gold/holdout was not replayed. Do not treat its reported effectiveness as independently validated by this audit.
