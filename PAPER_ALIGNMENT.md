# Paper Alignment

This file maps the claims of the companion paper to the corresponding repository evidence.

## What this repository supports

| Paper claim | Repository evidence | Status |
|---|---|---|
| Validation Theater exists as an AI failure mode | `docs/anti-hallucination.md` | DOCUMENTED |
| Synthetic evidence is not valid for hypothesis validation | `rules/integrity.md` (`[VERIFIED-SYNTHETIC]` vs `[VERIFIED-REAL]`) | IMPLEMENTED |
| Evidence markers enforce claim discipline | `rules/integrity.md`, `rules/audit-verification-gate.md` | IMPLEMENTED |
| Agent findings require independent tool verification | `rules/audit-verification-gate.md` | IMPLEMENTED |
| README metrics are checked against the filesystem | `.github/workflows/ci.yml` (Verify README metrics step) | CI-GATED |
| Doc counts (hooks, agents, skills) are drift-protected | `.github/workflows/ci.yml` (Verify doc counts step) | CI-GATED |
| Evaluator-Optimizer cycles are capped at 3 | `CLAUDE.md` (Evaluator-Optimizer Guard) | IMPLEMENTED |
| Skeptic agent receives context-blind review (no reasoning chain) | `rules/falsification-ladder.md` (Context Asymmetry Rule) | IMPLEMENTED |

## What this repository does NOT prove

- It does not prove the companion scientific case study independently.
- It does not guarantee zero hallucinations — it reduces and surfaces them.
- It does not validate claims made in repositories outside this one.
- It is scoped to Claude Code workflows; other AI systems require adaptation.
- Coverage (81%) does not mean 100% of hook behavior is tested.

## Reviewer path (minimal, ~15 min)

1. `docs/anti-hallucination.md` — the failure mode and evidence marker protocol
2. `rules/audit-verification-gate.md` — the verification gate for agent findings
3. `rules/integrity.md` — the evidence marker taxonomy
4. `.github/workflows/ci.yml` — the CI drift gates (lines 79–135)
5. `pytest tests/ -q` — run the test suite locally

## Cite as

See `CITATION.cff` for the BibTeX-compatible citation block.

Version archived for citation: `3.9.0` (2026-06-10).
Live repository metrics may differ from the archived version.
