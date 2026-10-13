# Oracle-Adequacy Gate

> Before you optimize against a judge, prove the judge is worth optimizing against.

## The problem this solves

An **oracle** is whatever decides a candidate solution is good: a test suite, a
metric, an LLM-judge, a benchmark, a human reviewer. Any search that improves a
solution — hand-tuning, evolutionary search, an agent loop — optimizes *hard*
against its oracle. That is fine when the oracle is adequate and catastrophic
when it is not, because the search will find the **cheapest way to satisfy the
oracle**, not the intent. This is Goodhart's law in operational form:

> When a measure becomes a target, it stops being a good measure.

Most "validation theater" in this repo's history is one inadequate oracle trusted
without audit. `F1 = 1.000` on a synthetic dataset is a *perfect score from a
worthless oracle* — the classifier memorized the answer key. The score is real;
the oracle is fake. (See [`hooks/validation_theater_guard.py`](../hooks/validation_theater_guard.py)
and [`rules/audit-verification-gate.md`](../rules/audit-verification-gate.md).)

The Oracle-Adequacy Gate makes the oracle a **first-class object that is audited
before it is trusted** — component 2 of the Oracle-Aware Core.

## Where it sits

```
Oracle-Aware Core (7 components)
  1. Intent              templates/intent_card.yaml
  2. Oracle Adequacy  <-- THIS GATE       templates/oracle_audit.yaml
  3. Falsification       templates/falsification_contract.yaml
  4. Variant Tournament  commands/evolve-solution.md
  5. Red-Team            skeptic / codex-skeptic
  6. Evidence Gate       integrity.md + promotion_gate_guard hook
  7. Null Result Ledger  null_results/ + reject_gate_guard / null_retroscan hooks
```

The gate runs **after** Intent (you cannot judge an oracle without knowing the
intent it should serve) and **before** the Variant Tournament (an inadequate
oracle makes the tournament worse than useless — it manufactures a confident
ranking of exploits).

## The gate

Fill [`templates/oracle_audit.yaml`](../templates/oracle_audit.yaml) and answer
six adequacy checks. `unknown` counts as `no`, never as `inconclusive` —
`inconclusive` is reserved for a check that could not execute at all (below).

| Check | Passes when | Fails into |
|-------|-------------|------------|
| **Gameable?** | No degenerate variant can score well without solving the intent | a search that finds the exploit |
| **Real vs theater** | The oracle separates genuine wins from lucky/overfit ones | overfit variant crowned |
| **Negative control (B)** | A known-BAD input exists that the oracle MUST reject | oracle that says yes to everything |
| **Positive control (G)** | A known-GOOD input exists that the oracle MUST accept | oracle that says no to everything, or was only ever tested against bad inputs |
| **Reproducible** | Same variant → same verdict across re-run / seed | a noisy oracle ranks by luck |
| **Measures the intent** | The metric tracks the `intent_card` success_metric, not a proxy | optimizing the proxy, not the goal |

### Two-sided qualification (Q = B·G)

Before this addition, an oracle could clear this gate on its negative control
alone — "it correctly rejects a known-bad input" — with no matching requirement
that it also correctly *accepts* a known-good one. A judge that rejects
everything, including good inputs, would pass `has_negative_control` and still
be worthless. The two checks are read together, not separately:

```
B = has_negative_control.answer   (correctly rejects known-bad)
G = has_positive_control.answer   (correctly accepts known-good)
Q = B AND G                       — qualifies only if BOTH sides hold
```

This is the same fail-closed shape `templates/falsification_contract.yaml`
already has for `positive_control`/`negative_control` (Component 3, one step
later, at the variant level) — it was simply missing one step earlier, at the
oracle-qualification level, where B alone used to be enough.
[`templates/oracle_audit.yaml`](../templates/oracle_audit.yaml)'s new
`two_sided_qualification` block makes the AND explicit instead of leaving it
implicit.

**External convergent validation, not the origin of this idea:** the identical
B·G construction — a generated verifier qualifies only if it (B) fails cleanly
on the known-bad state and (G) passes on the known-good one — appears
independently as the Base-to-Gold criterion `Q_x(b) = B_x(b)·G_x(b)` in
EXECCRITIC (arXiv:2609.09133, 2026), which trains a coding-agent test-writer
under exactly this admission rule. Cited because two unrelated designs landing
on the identical product-of-two-indicators shape is evidence the shape is
sound, not because this repo needed the citation to derive it — `has_negative_
control` already existed here; `has_positive_control` was always the missing
symmetric half.

### Operational failure → INCONCLUSIVE, never a verdict

A check that could not run at all — timeout, crashed sandbox, missing
dependency — is a different fact from one that ran and disagreed. Recording the
former as `no` (or `fail` in `falsification_contract.yaml`'s per-control
`result` field) launders an infrastructure problem into a verdict about the
oracle or the variant. This is `falsification-ladder.md` Step 2a's Substrate
Gate hard rule ("BLOCKED-INFRASTRUCTURE is never evidence against the claim"),
applied one level down — to a single control, not the whole run.

```
B = inconclusive, G = yes   -> Q = inconclusive   (NOT "no")
B = no,           G = yes   -> Q = no             (a real, executed failure)
```

`adequacy_verdict: INCONCLUSIVE` is therefore distinct from `INADEQUATE`:
`INADEQUATE` means the oracle was tested and failed; `INCONCLUSIVE` means it
could not be tested. Both stop the tournament, but only `INADEQUATE` may be
cited as a reason the oracle is bad — `INCONCLUSIVE` is a substrate problem to
fix and re-run, the same distinction EXECCRITIC's own `r(b,R;m)=0` draws
(an operationally invalid execution never becomes a behavioral PASS/FAIL).

### Verdict

- **ADEQUATE** — `Q=yes` and the other checks pass — proceed to the variant tournament.
- **WEAK** — proceed, but every downstream claim inherits the named blind spot
  and carries a `[WEAK]` marker. Document the blind spot; do not hide it.
- **INADEQUATE** — `Q=no` (B or G ran and failed). **STOP.** Do not run the
  tournament. Fix or replace the oracle first (add real data, add the missing
  control, add a second independent judge, switch from synthetic to
  `[VERIFIED-REAL]` data). Record the decision.
- **INCONCLUSIVE** — `Q=inconclusive` (B or G could not run at all). **STOP**,
  but fix the substrate/harness for that side, not the oracle's logic — this
  run may not be cited as evidence the oracle is inadequate.

> Optimizing against an INADEQUATE oracle is worse than not optimizing at all:
> the search converts a bad measure into false confidence at scale. Treating an
> INCONCLUSIVE run as if it were INADEQUATE converts a broken harness into a
> false verdict about the oracle.

## Data-provenance rule (inherited from integrity.md)

The fastest way an oracle becomes inadequate is synthetic data masquerading as
real. The gate forces `data_provenance` to be declared:

- `real`    → success claims may reach `[VERIFIED-REAL]`.
- `synthetic` → claims cap at `[VERIFIED-SYNTHETIC]`; **not** a validation of the
  intent, only that the code runs.
- `mixed`   → the real subset bounds the claim; state which part is which.

## Worked example (the trap, gated)

```
Intent:  cut RAG hallucination rate on the support corpus.
Oracle:  an LLM-judge scoring 50 hand-written Q/A pairs the author also wrote.
Audit:
  gameable?                 YES — a variant that always answers "I don't know"
                            scores high on a judge that rewards caution.
  has_negative_control (B)? NO  — no known-hallucinating answer that MUST be caught.
  has_positive_control (G)? YES — the 50 hand-written pairs are all answerable, so a
                            correct answer is at least accepted (this alone would
                            have hidden the real problem: B never got checked).
  measures_the_intent?      WEAK — 50 self-authored pairs are not the real corpus.
Q = B AND G = NO AND YES = NO.
Verdict: INADEQUATE -> STOP.
Fix:     score on 200 real production tickets + add 10 known-bad answers as a
         negative control + a second judge for disagreement. Re-audit.
```

Without the gate, an evolutionary loop would have "succeeded" by evolving a
variant that answers "I don't know" to everything — a perfect Goodhart win.

## Relationship to existing gates

| Existing | What it catches | What the Oracle-Adequacy Gate adds |
|----------|-----------------|------------------------------------|
| `validation_theater_guard.py` | perfect score + synthetic markers, after the fact | audits the oracle *before* the run, by design |
| `audit-verification-gate.md` | agent `[VERIFIED]` claims without tool evidence | asks whether the verifying tool itself is adequate |
| `promotion_gate_guard.py` | promotion without controls/baseline | a promoted claim is only as good as the oracle that judged it |

The gate does not replace these — it sits upstream of them, so the evidence they
check was produced by an oracle that earned trust.

**What this gate does NOT cover (2026-09-12):** it audits whether the ORACLE the
tournament repeatedly scores variants against is trustworthy. It does not
separate that reused oracle from a provably untouched, one-time-use final
check — after enough adaptive search even a good oracle degrades into training
signal (Goodhart's law). That separate check is `experiments/<id>/
sealed_holdout.yaml`, optional, enforced by `hooks/promotion_gate_guard.py`'s
6th condition — see `docs/experiment-dependency-graph.md`.

---

**Status:** ACTIVE — component 2 of the Oracle-Aware Evolutionary Mode.
**Templates:** `templates/oracle_audit.yaml`
**Command:** `/evolve-solution` runs this gate automatically before the tournament.
**Related:** `docs/experiment-dependency-graph.md` — the sealed-holdout gate this
one does not itself cover.
