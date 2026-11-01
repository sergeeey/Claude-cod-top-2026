# EQR extraction rules (committed BEFORE `ach_quotient.py` is run on any real subject)

Authored 2026-10-01 after reading the *schemas* of the source tables (so the rule can be applied), and
BEFORE computing classes, `d_min` or the floor on any real subject. The matrices in `../data/` are hand-made
by applying exactly these rules; the tool is run on them only after this file and the data are committed.
Reading the source tables to design the rule is unavoidable; what the rule forbids is choosing cells after
seeing whether they merge hypotheses.

## Unit of analysis (lesson of 2026-09-24)

Variants of one object are ONE independent subject, not many.

| Subject | Independent units | Hypotheses (columns) | Probes (rows) |
|---|---|---|---|
| S1 `lakes_negative_controls` (Y-17, read-only) | 1 (one dataset family: the same lakes) | 6 early-warning-signal variants | 5 known-negative series |
| S2 `install_tournament` (this repo) | 1 | 3 variants (A, B, C) | 3 statements the document makes explicitly |

Total independent subjects = 2. Everything reported on them is **descriptive** (see `claim.md`).

## S1 — lakes TDA early-warning variants

Source: Y-17 `experiments/*lakes-tda-ews*/decision.md` evidence tables (read only; nothing copied into this repo
except the cell values below).

- **Probes:** the five series the source tables label `negative` (Windermere, Loch Leven, Paul chl, Paul pH,
  Paul doSat). The four positive series are NOT used: the source tables describe them with different,
  mutually inconsistent vocabularies ("no crossing" vs "null (no classical pair)" vs a numeric lead), and the
  same variant is described differently in different tables.
- **Cell:** `C` = the table flags the series as a **false positive** for that variant (by ANY mechanism, TDA or
  classical — the tables state "FP now via classical only" separately from "TDA crossing"); `I` = the table
  states explicitly that it is **not** a false positive; `NA` = not stated.
- **Variants and the one table each is read from:**
  - `V1`, `V1p` (IAAFT), from `...-iaaft-null-v1prime` columns "V1 (AR(1)) false positive?" / "V1' (IAAFT)…";
  - `V2p` (detrend + IAAFT), from `...-detrend-surrogate-v2prime` column "V2' (detrend+IAAFT) FP?";
  - `V1g` (AR1 + total persistence), from `...-total-persistence-v1g` column "V1g";
  - `H1i` (IAAFT + total persistence), from `...-total-persistence-iaaft-v1gprime` column "H-B3-1i";
  - `H1j` (AR1 + Wasserstein), from `...-diagram-distance-v1j` column "H-B3-1j".
- **Excluded, with reason:** `...-surrogate-null-v1` (the same variant as V1 — would double-count);
  `...-diagram-distance-iaaft-v1kprime` (no per-series table); `...-invariant-conjunction` (columns are
  "crosses?", not "false positive?"); `...-descriptive-v3`, `...-changepoint-v2`, `...-peaktau-*`,
  `...-crossvar-*`, `...-perseason-*`, `...-ph0-*` (different probes: floor FP rates, correlations);
  `may1972-*` (different data); `chernoff-*`, `remy-*`, `kauffman-*` (no shared probe set).
- **Data-quality note (not used in the matrix):** the tables disagree across experiments on the same variant
  and series (e.g. V1 on Peter chl: "no crossing" in the V1g table vs a TDA crossing at 270.0 in the
  surrogate-null-v1 table). A finding about the source, recorded here and not "resolved".

## S2 — install.sh variant tournament (`experiments/20260701-p1-hooks-reproducible-install/tournament.md`)

- **Hypotheses:** Variant A, Variant B, Variant C.
- **Probes (rows), only statements the document makes explicitly:**
  1. positive control: A "PASS"; B "Would pass the positive control"; C no statement → `NA`.
  2. negative control: A "PASS"; B "Would presumably pass the negative control TOO, but for the wrong reason"
     (a hedged **prediction**, recorded as `C` and flagged hedged); C no statement → `NA`.
  3. "hypothetical future case where install_minimal and install_rules diverge": B stated to be falsifiable
     there (`I`); A and C not stated for this case → `NA`.
- Mixed observed / predicted cells (A observed, B and C predicted or silent) — flagged; unit of analysis 1.

## Non-negotiables for both subjects
- `N/A` is a third symbol and never agreement; identical **full** vectors define a class.
- The floor (`ach_quotient.py floor`, row-wise shuffle, fixed seed) is computed for the same shape.
- A class that exists only because probes are constant (every variant gives the same cell) is not evidence
  of redundancy beyond chance — the floor reports exactly that, and it is reported as such.
