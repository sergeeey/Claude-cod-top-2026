# boyko-leverage-map — registry-drift pattern, replication run

**Date:** 2026-09-05
**Object:** why does the "registry declared-vs-actual" drift pattern keep
recurring in this repo despite each instance being fixed with its own
point-fix gate?

## Honesty note up front (a real methodological miss, not glossed over)

This run was NOT checked against the skill's existing `maturity_evidence`
before starting. Doing so afterward showed the 2026-08-28 run on this same
skill found the **same pattern** ("registry declared-vs-actual drift, 5
independent instances") on the **same object** (this repo). This is exactly
the "check existing evidence before crediting something as new" discipline
this same session's own `cross-domain` run applied to its donor-domain
search (2 of 6 bridges were excluded as already-implemented) -- and this run
did not apply it to itself first. Recorded honestly as a replication, not
presented as a fresh discovery.

## What is genuinely new vs. genuinely replicated

**Replicated (same finding, ~8 days later):** the core pattern -- a
declarative field drifts from the real file/code it describes because
inevitability is added reactively, per-field, after drift is caught, not
built in when the field is created.

**New in this run:**
- 2 additional concrete instances not in the original 5: today's Gate 10
  anti-theater rejection (maturity_evidence citing no real file) and the
  `docs/skill-maturity-criteria.md` dogfooded-count drift (caught twice
  today, 7->10 then 10->12).
- Temporal stability: the same structural pattern recurring 8 days apart, on
  different specific fields, is stronger evidence of a real structural
  mechanism than a single-session finding -- one instance could be
  coincidence; two independent findings of the same abstract pattern,
  separated in time, raises confidence it's structural (per the skill's own
  Hard Rule 5: a pattern needs >=2 independent, time/place-separated
  instances of the same form).
- A full single-pass 10-step run (the original evidence was assembled across
  3 separate dated sessions for different steps -- 2026-08-28, 08-29, 08-30).
  This run completed Steps 0-10 in one pass on one clearly-stated object.

## Result (condensed; steps 2-10 full reasoning in this session's transcript)

**Pattern:** declarative field <-> reality drift, now 7 total named instances
across the two runs (hooks/registry.yaml `class`, agents frontmatter `name:`,
skills SKILL.md existence, maturity_evidence file citation, doc-count
staleness -- twice).

**Mechanism [INFERRED]:** cost asymmetry -- writing a declarative field costs
one line; writing its verifying gate costs real engineering (AST parsing,
edge cases, tests), so gates get deferred until an external audit forces the
issue.

**Leverage point (Meadows, highest identified):** not another point-fix gate
(low leverage, already tried 5+ times) but a meta-gate -- CI enforcement that
every new top-level declarative field in a registry/frontmatter must ship
with a paired verifying function, making the coupling structural rather than
a matter of individual diligence.

**Critical unknown, screened via the skill's own "would this change my next
action" test:** how many currently-undefended declarative fields exist right
now, in total, across registry.yaml/agents/*.md/docs/*.md. Answer changes
the next action materially (a handful -> keep patching individually; 10+ ->
build the meta-gate now) and is cheap to answer (~10-15 min grep audit) --
correctly kept as critical, not demoted to merely "interesting."

**Top-3 (ranked by practical significance, not novelty):**
1. Run the cheap grep audit (~10-15 min) to count undefended fields before
   deciding whether the meta-gate is worth building now.
2. If >=10 found: build the meta-gate (CI check that a new top-level YAML/
   frontmatter field requires a registered verifying function).
3. Lower urgency: audit whether `sync_doc_counts.py` covers ALL prose-count
   mentions in docs/, or only some -- today's drift was caught, but only
   because the count happened to be one `sync_doc_counts.py` already tracks.

## Result vs the object question

Partially yes, with the honest caveat above: the causal/systemic reasoning
(mechanism, leverage point, paradox, unknowns map) is real and adds temporal
replication value, but the headline pattern itself is not new -- this run's
primary contribution is confirming stability over time and adding 2 new
instances, not discovering the structure fresh.

## Limitation

Single evaluator across both runs (same session family, not independent
raters) -- replication here means "the same analytical process, run again
later," not "a different analyst reached the same conclusion independently."
