# Decision — evidence-chain verifier prototype

## Skeptic verdict (Step 8a, context-asymmetric — claim + code + real results only)

**FALSIFIED.** Three independent breaks, none covered by the 5 pre-registered tests:

1. **Substring-collision** — `claimed_report_verdict_snippet not in result_text`
   accepts any generic/common phrase that happens to appear for unrelated
   reasons (boilerplate, echoed prompt text, a common verdict word). Cheap,
   mechanical, zero-cost to exploit.
2. **Local file ≠ tamper-evident (load-bearing)** — the transcript lives on
   local disk, owned by the same party being verified. Nothing prevents a
   post-hoc edit (`sed`, a script, a text editor) between when the real event
   happened and when someone checks it later. "Written by the harness, not
   the model" is true at write-time only; it says nothing about integrity at
   verify-time, which is the only time that matters.
3. **Layer confusion / scope overreach** — the verifier proves "a call
   happened and emitted exactly these bytes," never that those bytes are
   true. A sub-agent can confidently emit a wrong verdict and this verifier
   will correctly ACCEPT it per its own narrow job, while the parent report
   is still false.

## Kill Analysis (per Minimal Relaxation Rule / OSA)

**What was killed:** the claim as worded — "this verifier is a source of
truth for whether a sub-agent run happened AND said what a report claims" —
in its strong, unqualified form. Also killed: treating a clean 5/5 pass on a
self-authored test set as sufficient evidence (this repo's own
skeptic-triggers.md correctly flagged the 5/5 sweep before the independent
check even ran).

**What was NOT killed:**
- The core mechanism (searching a real transcript for genuine tool_use/
  tool_result content instead of trusting a self-supplied hash chain)
  correctly defeats the ONE attack it was designed for (test 4's fully
  offline fabricated hash chain) — confirmed both before and after the
  skeptic review found other gaps.
- The general two-layer framing (execution proof + independent judge) is
  still directionally right — this result narrows Layer 1's actual strength,
  it doesn't invalidate the need for it.
- The debugging finding mid-run (async agents return a launch ack, not the
  real result, as the immediate tool_result — real content arrives later as
  a harness-authored `<task-notification>`) is a real, reusable fact about
  how this harness's transcripts are structured, independent of the larger
  claim's fate.

**Relaxation Map (one assumption at a time, per Minimal Relaxation Rule):**

| Assumption removed/weakened | New variant | Cost |
|---|---|---|
| "local file is trustworthy at verify-time" | require an external witness — CI re-hashes the transcript segment at merge time and stores the hash outside the contributor's reach (e.g. in the PR's own CI log, which the contributor cannot edit after the fact) | needs real CI wiring, not a local script |
| "any substring match is sufficient" | require matching a specific, schema-located field (not raw substring across the whole message) + a minimum-entropy/length floor on the snippet | code-only fix, cheap |
| "execution proof ⇒ result is true" | explicitly split into two gates: `EXECUTION_VERIFIED` (this prototype's actual, narrower claim) and `RESULT_VERIFIED` (still requires the existing blind-adjudicator Layer 2 pattern, unchanged) | documentation + gate-naming fix, cheap |

## Gate

**STOP** on the claim as originally worded. **CONDITIONAL** on the narrowed
version: "under the assumption the local transcript has not been tampered
with post-hoc, this verifier catches reports whose claimed content is absent
from it" — worth pursuing further ONLY with an external witness (CI-side
re-hash) added, which was flagged by the routing hook as SECURITY-tier work
requiring the reviewer + security-audit path, not solo continuation.

**Not saved to null_results/** — the mechanism itself (transcript-grounded
verification over self-authored hash chains) survives narrowed; only the
overclaimed strong wording was killed. This stays in `experiments/` as an
active, narrowed direction pending the external-witness fix, not a dead end.

## What this experiment does NOT mean

1. Does not mean Gate 10 should be changed — nothing here is wired into
   `check_architecture.py`, by design (per the user's own explicit instruction
   not to deploy this yet).
2. Does not mean the two-layer (execution-proof + independent-judge) model
   from the earlier research is wrong — it means Layer 1's *local-only*
   version is too weak to trust alone; an external witness is required.
3. Does not mean the existing blind-adjudicator pattern (Layer 2, already
   dogfooded in the sci-code-audit pilot) needs any change — it was not
   touched by this experiment.

## Capture note (2026-11-03)

This folder existed only as untracked files and was committed unchanged (plus lint-only edits to the
scripts). Review of the capture found a limit in the recorded evidence that the original run did not state:

- `test3_truncated_tail_simulated` in `run_tests.py` uses an unmodified transcript and a snippet that never
  existed in it. It therefore exercises the same absent-substring path as test 2 and is not evidence that
  truncation is detected. A real truncation test needs a temporary transcript with a genuinely truncated
  result, a snippet present in the original tail, and an ACCEPT control on the original transcript.
- The recorded result (REJECT) stands as recorded; it supports only 'a never-present snippet is rejected'.
- `run_tests.py` reads a transcript at a fixed local path, so the tests cannot be re-run elsewhere.
