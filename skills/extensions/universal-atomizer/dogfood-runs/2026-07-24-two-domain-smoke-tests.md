# universal-atomizer — dogfood runs, 2026-07-24

Two runs against real, pre-existing objects in this repo, both in the same session
that authored the skill. This file exists so a maturity claim in `registry.yaml` cites
a real artifact, not the skill's own `SKILL.md` prose (`docs/skill-maturity-criteria.md`
explicitly names that pattern as evidence laundering).

## Honest limitation, stated up front

Both runs were **self-executed by the same agent that wrote the spec**, hand-following
`SKILL.md`'s own instructions rather than an independent `Skill(...)`/`Agent(...)`
invocation — because a skill created mid-session cannot be resolved by name via the
`Skill` tool in the same session (confirmed: `Unknown skill: universal-atomizer` on
both attempts, run 1 and run 2). This is weaker evidence than a blind/independent run
(e.g. `boyko-why-ladder`'s dogfood run, a genuinely separate blind agent invocation)
per `rules/falsification-ladder.md`'s Independent Verification Strength Ladder — "same
model, isolated context" would be Weak-Medium; this is closer to "same model, same
context" (author testing their own freshly-written spec), which the ladder does not
even list as a rung above Weak. What it IS real evidence of: the spec was actually
followed line-by-line against real, pre-existing, unmodified objects (not synthetic
fixtures built to pass), and both runs surfaced concrete, checkable structural gaps
that were fixed before being written up here — not a suspiciously clean first pass.

## Run 1 — research/benchmark report

**Object:** `benchmarks/strong-inference/run-2026-07-23-full.md` (~482 lines: claims,
one formula, a 10x3 results table, percentages, an explicit limitations section).
**Domain per SKILL.md's table:** hybrid (научная статья + software-repo artifact).

**Method:** hand-executed the 11-step process (INTAKE through OUTPUT), produced
sampled A-G registries (not exhaustive — ~45 atoms identified, representative rows
shown), checked all 6 gates.

**Gaps found and fixed in `SKILL.md` before this was written up** (checkable — each
maps to a specific, reproducible failure mode in the spec's own wording, not a vague
impression):
1. Atomicity Gate, applied literally, would demand one atom per data-table cell
   (30+ atoms for one 10x3 table) — added an explicit table-as-bulk-atom exception.
2. JSON-graph companion trigger was keyed to atom count (`>=15`), which fired on this
   object's ~45 atoms despite a mostly-linear graph (branching ~1.0-1.2) that gains
   nothing from JSON — changed the trigger to branching-factor density (`>=1.5`).
3. Domain-variant table forced a single row pick; this object is genuinely hybrid and
   needed fields from two rows — added explicit permission to combine.
4. Registry A's general Role taxonomy and Registry C's number-specific 4-way role
   (fitted/derived/measured/assumed) were both being filled for the same numeric atom,
   inconsistently — added a rule that numeric atoms' role lives only in Registry C.
5. `LIMITATION_SWEEP`'s keyword list only had hedge-words, missing this object's actual
   phrasing ("does NOT show/establish", "not claimed") — expanded the keyword list.

## Run 2 — security-relevant code

**Object:** `hooks/agent_tool_scope_guard.py` (167 lines: a `PreToolUse(Edit|Write)`
hook, no formulas, real invariants/preconditions in comments, a documented historical
failure the hook exists to fix).
**Domain per SKILL.md's table:** программный проект (hybrid — docstring carries a
research-style WHY narrative with a date and a reproduction claim).

Deliberately chosen to be maximally different from Run 1 (code vs. prose, zero
formulas, security assumptions instead of statistical results) to test whether Run 1's
fixes generalize or were overfit to one document shape.

**Positive finding (not a gap):** the type taxonomy (PROCEDURE/ALGORITHM/PARAMETER/
CONVENTION/RISK/DECISION) and the "программный проект" domain-variant fields covered
this object without any forcing — no new atom types were needed. The table-as-bulk-atom
exception from Run 1 correctly did NOT misfire on this object's enumerated fail-open
conditions (3 distinct, independently-testable branches) — confirming the exception's
"uniform-schema data table" wording is specific enough not to over-apply to enumerated
logical branches, which is a structurally different shape.

**Gaps found and fixed in `SKILL.md`:**
1. The source material asserts its own prior verification inline ("verified by
   tabulating all 12 live files", "confirmed... fetched directly twice") — this exact
   shape also appeared in Run 1 and was not addressed there; recurring on an unrelated
   domain confirmed it as systemic, not one-off. Added an explicit rule: such
   self-reported verification claims extract as ordinary `FACT_REPORTED`/`AUTHOR_STATED`
   and must not inflate an atom's Чёткость or substitute for the atomizer's own
   (absent, by design in EXTRACTION_ONLY) verification.
2. The Traceability Gate's "основание не указано" wording conflated two different
   situations: a claim genuinely ungrounded by its author, vs. a claim grounded in a
   real, named file that simply sits outside the locked Scope (`utils.py`, imported by
   this hook but out of this run's declared coverage). Split into two explicit,
   distinct statuses.

**Real finding about the object itself** (not about the skill — this is exactly the
kind of output the skill is supposed to produce): Registry D surfaced an assumption the
source never states — that the platform-supplied `agent_type` field is trustworthy /
not spoofable by the invoking agent, which the entire security guarantee of this hook
rests on. Not fixed here (out of this dogfood run's scope — it's a finding about
`hooks/agent_tool_scope_guard.py`, not about `universal-atomizer`), but recorded as
evidence the skill's Registry D does real work, not just on physics/statistics objects.

## Verdict against `docs/skill-maturity-criteria.md`'s `dogfooded` checklist

| Requirement | Met? |
|---|---|
| Real invocation against a checkable-outcome task | Partially — real objects, real checkable gaps found and fixed, but NOT an independent/blind invocation (see limitation above) |
| Citable artifact, not the skill's own `SKILL.md` | Yes — this file |
| Task that could have failed (not a rigged synthetic pass) | Yes — 7 total gaps found and fixed across 2 runs, not a clean first pass |
| Disclosed honestly, failures and all | Yes — including the same-agent-authorship limitation, not smoothed over |

**Recommendation, not a unilateral decision:** 3 of 4 criteria are cleanly met; the
"real invocation" criterion is met in the sense of "real object, real checkable
failure modes surfaced and fixed" but not in the stronger sense of independent/blind
execution that e.g. `boyko-why-ladder`'s dogfood run had. Whether that's enough to
clear `dogfooded` — or whether it should wait for a genuinely independent run (once the
`Skill` tool can resolve a same-session-created skill, or via a fresh session) — is left
as an explicit judgment call, following this repo's own precedent of not rounding a
partial-but-real result up to the stronger label (see `hypothesis-arbiter`'s
`dogfooded`-not-`benchmarked` call in this same criteria doc).
