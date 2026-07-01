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
five adequacy checks. `unknown` counts as `no`.

| Check | Passes when | Fails into |
|-------|-------------|------------|
| **Gameable?** | No degenerate variant can score well without solving the intent | a search that finds the exploit |
| **Real vs theater** | The oracle separates genuine wins from lucky/overfit ones | overfit variant crowned |
| **Negative control** | A known-BAD input exists that the oracle MUST reject | oracle that says yes to everything |
| **Reproducible** | Same variant → same verdict across re-run / seed | a noisy oracle ranks by luck |
| **Measures the intent** | The metric tracks the `intent_card` success_metric, not a proxy | optimizing the proxy, not the goal |

### Verdict

- **ADEQUATE** — proceed to the variant tournament.
- **WEAK** — proceed, but every downstream claim inherits the named blind spot
  and carries a `[WEAK]` marker. Document the blind spot; do not hide it.
- **INADEQUATE** — **STOP.** Do not run the tournament. Fix or replace the oracle
  first (add real data, add a negative control, add a second independent judge,
  switch from synthetic to `[VERIFIED-REAL]` data). Record the decision.

> Optimizing against an INADEQUATE oracle is worse than not optimizing at all:
> the search converts a bad measure into false confidence at scale.

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
  has_negative_control?     NO  — no known-hallucinating answer that MUST be caught.
  measures_the_intent?      WEAK — 50 self-authored pairs are not the real corpus.
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

---

**Status:** ACTIVE — component 2 of the Oracle-Aware Evolutionary Mode.
**Templates:** `templates/oracle_audit.yaml`
**Command:** `/evolve-solution` runs this gate automatically before the tournament.
