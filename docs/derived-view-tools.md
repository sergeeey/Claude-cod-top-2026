# Derived-view tools — what exists, when to run it

Four read-only scripts compute a **derived view** of an artifact you already wrote. None is a gate, none
changes a verdict, none is called by a hook. They exist because a tool nobody can find is the same as a tool
that was never built, so this page is the one place that says what each is for and on which input to run it.

Status of all four (2026-10-01): **correct on their own tests, usefulness on real data NOT shown** —
experiment `20261001-epistemic-structure-layer` (parked): every real-data measurement was `NO_HEADROOM`
(artifacts of the right shape were too few or too easy), which is a stop-verdict, not evidence against them.
Treat output as a prompt to look, never as a verdict.

| Tool | Run it when | Input | What it tells you | Does NOT tell you |
|---|---|---|---|---|
| `scripts/ach_quotient.py` | ≥3 hypotheses are alive and you filled an `ach_matrix.md`-style table | the `## Matrix` section, or `--json` | hypotheses that no filled test separates (classes), tests that split nothing, `d_min`, the cheapest set of tests that separates all that can be separated | which hypothesis is true; `N/A` is never read as agreement |
| `scripts/claim_cutsets.py` | a claim has **alternative** support paths (OR), or `claim-decomposer` listed `BLOCKING_ATOMS` | `--logic "H = A & (B \| C)"` or `--decomposer <decomposer output file>` | smallest sets of failures that destroy the claim (cuts), single points of failure, nodes hidden under several "independent" paths | the logic itself: it does not read prose, you write the AND/OR. Pure AND gives kappa 1 everywhere and adds nothing |
| `scripts/verdict_invariance.py` | you want to know whether a reviewer/skeptic verdict moves under changes that carry no evidence (section order, an authority line) | `generate` a variant set, run your verifier on each, `compare` / `score` | which variants moved the verdict beyond run-to-run noise; a truncation control tells you if the instrument can see anything | whether the verdict is right. Costs real agent runs (~110-170k tokens each) |
| `scripts/eig_calculator.py --merge-equivalent` | two hypotheses have identical likelihood rows and you gave uniform priors | `--priors`, `--likelihoods` | class-level priors, and a warning that duplicates inflate a class's prior mass | — |

## How a session should find these

- `claim-decomposer` (Step 2) points to `claim_cutsets.py`.
- `hypothesis-arbiter`'s `references/ach_matrix.md` and `experiments/_template/ach_matrix.md` point to
  `ach_quotient.py` and `eig_calculator.py`.
- This page is the registry; a new derived-view tool is not "done" until it has a row here **and** a pointer
  in the skill or template that produces its input.

## Prospective check (from `experiments/20261001-epistemic-structure-layer/ledger.md`)

Nothing reads that ledger automatically. The triggers are counts of real occurrences, not dates:

| Tool | Check after | Keep if | Retire if |
|---|---|---|---|
| `ach_quotient.py` | the next 5 real hypothesis tables | >=1 has a non-trivial class beyond its shuffle floor | 0 of 5 |
| `claim_cutsets.py` | the next 3 `claim-decomposer` outputs with an OR structure | computed singleton cuts differ from the declared `BLOCKING_ATOMS` in >=1 | they agree in all 3, or no output has OR |
| `verdict_invariance.py` | the next 3 real checkpoints for a multi-PR chain | >=1 answer divergence full vs compressed (graded against git) | 0 of 3 diverge while the truncated control does |

A retired tool is deleted from `scripts/` and its row from this page; an unchecked one stays listed with its
trigger so the absence of a check is visible.

## Provenance

Method names are older than this repo: minimal cut sets (fault trees; Klamt & Gilles 2004), assumption-based
truth maintenance (de Kleer 1986), Analysis of Competing Hypotheses (Heuer 1999), metamorphic testing (Chen et
al. 1998), expected information gain (Lindley 1956). Details in each script's docstring.
