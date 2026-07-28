# pearl_registry/INDEX.md — Unexpected Testable Insights

_Not a REJECT/ARCHIVE/PROMOTE verdict — this is a side-ledger for observations
that surfaced during an experiment but aren't about that experiment's own
claim. Protocol: `rules/falsification-ladder.md` § Pearl Registry._
_`hooks/research_health_loop.py` reads this file and flags entries whose
`next_check` has lapsed._

## Index

| Date | Source Experiment | Observation | Falsifiable Prediction | Impact | Trigger Condition | Next Check | Status |
|------|-------------------|-------------|------------------------|--------|--------------------|-----------|--------|
| 2026-07-28 | 20260728-osa-fl-protocol-vs-standard-analysis | Doubt-Driven Development's mandatory "steelman the opposing view" (Step 2) has no discriminator between steelmanning a plausible-but-contestable counter-argument and steelmanning one that is simply factually false — in a pilot case, it caused an agent applying the protocol to explicitly affirm a security claim ("bounded worst case") that an independent real red-team verdict calls FALSE, while a standard-analysis agent with no steelman obligation rejected the same claim cleanly. | If Step 2 is amended to require a quick soundness check before crediting a counter-argument, a re-run of the same Case 2 prompt (Relaxation Map V1 in `experiments/20260728-.../decision.md`) will score higher on anti-pattern-avoidance without the diagnostic content getting worse. | 6 | V1 re-run executed (see decision.md Relaxation Map) OR the next time DDD Step 2 is invoked on a security-relevant claim where the counter-argument's factual soundness hasn't been separately verified | On V1 re-run, whenever that's picked up | pending |
| 2026-07-28 | 20260728-osa-fl-protocol-vs-standard-analysis | Perelman's REPEAT-vs-REJECT threshold (Promotion Rule) can under-reject relative to a real expert verdict specifically when that real verdict's confidence was informed by outside corroboration (e.g. external reviews) the protocol-following agent didn't have access to — the Anti-Overfitting Gate's own caution against premature REJECT produced a REPEAT where the real, better-informed expert issued a clean REJECT. | If Arm B's prompt explicitly asks "would this evidence alone, with no outside corroboration, justify a REJECT this strong?" as a Promotion-Rule sub-question, a re-run of Case 1 (Relaxation Map V2) shifts the verdict from REPEAT toward REJECT without the diagnostic content changing. | 4 | V2 re-run executed (see decision.md Relaxation Map) | On V2 re-run, whenever that's picked up | pending |
