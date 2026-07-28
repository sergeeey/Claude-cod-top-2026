# claim.md — hypothesis-arbiter taxonomy pilot

## Falsifiable claim

Adding the 8-class generator taxonomy to `hypothesis-arbiter`'s SPAWN step
(Этап 1) causes the candidate hypothesis table to include an Artifact-class
explanation ("the observed signal is produced by tool/measurement output
formatting, not by an authored claim") on the `skeptic_auto_trigger.py`
T1-firing-rate mystery, where the unmodified SPAWN step does not.

## Counterfactual frame

In what world is this claim true? A world where an explicit taxonomy checklist
measurably widens the space of hypothesis CLASSES considered during generation,
independent of the generating model's own default tendency to reach first for
a Mechanistic explanation (which is what actually happened this session: my own
first, unaided hypothesis was "the wording matches all/passed prose" — a
Mechanistic guess that was WRONG).

In what world is it false? A world where a capable generator already considers
Artifact-class explanations by default whenever the symptom shape invites it
(e.g. "an automated tool's own formatting" is an obvious candidate once you see
`[100%]` in the masked context), making the explicit taxonomy redundant ceremony
— exactly the risk this session's own `null_results/20260728-osa-fl-protocol-
vs-standard-analysis.md` already found evidence for with a different, but
structurally similar, protocol addition.

## Kill condition

Both Arm A and Arm B produce an Artifact-class hypothesis → taxonomy addition
did no visible work on this case (does not by itself kill the whole idea, since
n=1, but it removes THIS case as supporting evidence and shifts the honest
verdict toward REPEAT/inconclusive rather than PROMOTE).

## Verifier

A fresh, context-asymmetric `Agent` call (blind grader) — not the same context
that ran either arm, not told which transcript is which arm, given the ground
truth mechanism separately and asked to judge presence/absence independently
per transcript.

## Rivals (per FL's own "Hypothesis Arena" discipline, the document itself asked for)

- H1 (this claim): taxonomy causes Artifact-class inclusion.
- H0: no difference — the generating model considers Artifact-class candidates
  regardless of an explicit checklist.
- HA (alternative mechanism): any observed difference is really about how each
  arm's PROMPT happened to be phrased (order effects, emphasis), not the
  taxonomy content itself.
- HC (confounder/artifact of THIS pilot): the grader itself defaults to
  reporting "present" under ambiguity — controlled for via the negative-control
  fake-table check in `estimand.md`'s Grading section.
