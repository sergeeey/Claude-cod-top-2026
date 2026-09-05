# cross-domain — anti-theater gate stuck-problem run

**Date:** 2026-09-05
**Object:** does `cross-domain` produce a genuine, testable, non-obvious
hypothesis for a real stuck problem this session just hit -- and does its
"propose, don't prove; skeptic/FL decide" division of labor actually hold up
when the hypothesis is handed to a context-asymmetric skeptic?

## Why this run exists

Real problem, not constructed for the benchmark: `check_architecture.py`
Gate 10 (the registry.yaml anti-theater check) had just rejected a first,
prose-only version of a `maturity_evidence` field earlier this same session
(see `run-2026-09-05-project-mode.md` in the sibling `boyko-project-radar`
benchmark). The gate checks that a citation resolves to a real FILE, but has
no way to check that the file's CONTENT is truthful -- that still requires
judgment from whoever writes the citation, which today is the same session
that makes the promotion decision. Standard software engineering tools (more
tests, more linting) do not address this: the problem is about credibility of
a non-reproducible historical claim, not code correctness.

## Protocol

Invoked `/cross-domain` with the real problem statement above, no prior
framing beyond a one-paragraph description of the object. Followed the
skill's own 7-step flow as written in `skills/extensions/cross-domain/
SKILL.md`, in a single pass (not the N≈10-pass self-consistency the skill's
Step 3 calls for -- see Limitation below).

## Result

**Feasibility:** scored 7/10 (GO) -- a real stuck problem, not solved by
"write another test," since the core issue is that only the report-writer can
judge report-truthfulness today.

**Baseline established:** 100% of the session's own 3 same-day promotions
(atomize/research-audit/boyko-project-radar, see the sibling benchmark file)
had zero independent verification -- same session wrote the sub-agent
prompts, ran them, and made the promotion call.

**Hidden structure named:** reframed from "code correctness" to "single-witness
testimony credibility for a non-replayable event" -- explicitly not the
industry-standard frame (code review / CI gates check reproducible behavior,
not historical claims).

**6 donor domains searched**, forced across non-tech categories: academic
peer review, forensic accounting (Benford's Law), military HUMINT
corroboration, biology (orthogonal-method confirmation), historiography
(source triangulation), cryptography (commitment schemes / pre-registration).

**Golden-zone filtering caught its own false positives, verified before
accepting them, not asserted from memory:** grepped this repo's own
`rules/falsification-ladder.md` and `rules/skeptic-triggers.md` before
crediting any bridge as novel. Two of the six "bridges" (peer-review context
asymmetry, Benford's-Law-style round-number suspicion) turned out to be
*already implemented* here (15/22 hits for "Context Asymmetry" in
falsification-ladder.md; skeptic-triggers.md's Trigger 4 "Round Numbers").
Commitment/pre-registration was also already covered under EstimandOps. These
were explicitly excluded from the golden zone rather than counted as new
insight -- the skill's anti-pseudo-insight discipline held under a check that
could have gone the other way (padding the result with rediscovered wheels).

**One genuine, not-yet-implemented golden-zone hypothesis survived:** a
"two-source rule with orthogonality" (HUMINT + biology) applied to Gate 10 --
require a second, structurally different verification event before
`maturity: dogfooded`, not just a second citation string.

## Handoff to skeptic (context-asymmetric, per Context Asymmetry Rule)

`Agent(skeptic)` was given ONLY the falsifiable claim + the real Gate 10 code
(`scripts/check_architecture.py`'s `gate_maturity_declared` function) -- no
access to this reasoning chain or session history, per
`rules/falsification-ladder.md`'s Context Asymmetry Rule.

**Verdict: FALSIFIED** (the proposed mechanism, not the diagnosis), with 3
concrete, code-grounded findings:

1. **Testimony regression** (HIGH confidence, follows directly from the code):
   a regex/string check for "mentions a second run" verifies that
   independence was *claimed*, not that it happened -- `target =
   evidence.split(" -- ", 1)[0]` only ever checks the FIRST citation target
   for file-existence; a second source can be asserted in prose with zero
   enforcement. This is the exact same single-witness problem, one meta-level
   up.
2. **Circular toy-test** (HIGH confidence, by construction): the proposed
   falsification metric ("% of next 5 promotions still single-source") reads
   the same `maturity_evidence` string the gate itself steers -- if all 5
   write "n=2, independent run confirmed," the metric shows "0% single-source"
   regardless of whether real corroboration occurred. Same shape as this
   repo's own Validation Theater Guard failure mode (a test that can't fail
   by construction).
3. **Disproportionate cost** (MEDIUM confidence): uniform application to every
   `dogfooded` skill ignores risk-tier -- a trivial read-only digest skill
   would face the same corroboration bar as a production-state-mutating one,
   predictably causing either permanent `wired` stagnation or ceremonial
   compliance text (regressing to point 1).

**Skeptic's surviving, narrower reformulation** (not self-graded as
confirmed -- recorded as the actual output of delegation, per the skill's
"propose, don't prove" division of labor): require ≥2 artifacts with
non-overlapping PROVENANCE METADATA (git commit author, or a hook-emitted
session-id + timestamp separated by ≥N hours) rather than a string mention,
with the provenance check performed by a hook that has no write access to
`maturity_evidence` itself. Skeptic's suggested cheapest next step: audit real
`git log` history first (~30-60 min) to check whether the 100% single-source
baseline even holds beyond this session's n=3, before building anything.

## Result vs the object question

Yes on both counts: the skill produced a genuine, non-obvious, testable
hypothesis (not a restatement of "add more review"), and correctly identified
two of its own six candidate bridges as already-adopted mechanisms rather than
padding the golden zone -- and the "propose, don't prove" split worked exactly
as designed: the skeptic found real, code-grounded holes in the *mechanism*
this skill proposed, which the skill itself explicitly does not self-judge.

## Limitations (stated, not glossed over)

- Single-pass generation, not the skill's own prescribed N≈10-pass
  self-consistency for Step 3 -- the "golden zone" filtering here relied on
  one-shot judgment plus a grep-verified exclusion check, not genuine
  multi-pass frequency counting. A real 10-pass run might surface additional
  or different bridges.
- n=1 domain (`check_architecture.py`'s Gate 10) -- no claim of generality to
  other stuck problems from this single run.
- The hypothesis was falsified in its proposed form; this benchmark evidences
  the SKILL's process (generation + honest exclusion + correct delegation),
  not that its output survived intact. No follow-up gate was implemented from
  this run -- the surviving reformulation is parked, not built, pending the
  cheap real-baseline audit skeptic itself recommended.

## Full agent transcript

The skeptic agent's full response and this session's full cross-domain
walkthrough exist in this session's own transcript. This file is the citable,
committed artifact per this repo's anti-theater convention
(`scripts/check_architecture.py` gate 10).
