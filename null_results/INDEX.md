# null_results/INDEX.md — Falsified Experiments Registry

_Entries here mean: this claim was tested and FALSIFIED. Do NOT retry without a fundamentally different approach._
_Before starting any new experiment, grep this file for your topic._

## How to add an entry

On REJECT verdict in `decision.md`:
1. Copy filled `decision.md` to `null_results/<id>-<slug>.md`
2. Add one row to this table

## Index

| ID | Date | Slug | Verdict | Why falsified (10 words max) |
|----|------|------|---------|------------------------------|
| example | 2026-01-01 | example-claim | REJECT | baseline matched complex model, no added value |
| 20260715-sde-cc-fabricated-historical-corpus | 2026-07-15 | sde-cc-fabricated-historical-corpus | REJECT | 3/3 spot-checks failed, zero sources, benchmark unrun |
| 20260716-regex-composition-response-guard | 2026-07-16 | regex-composition-response-guard | REJECT | 0/0 on calibration, 6/8 held-out — regex can't classify context |
| 20260716-llm-judge-response-guard | 2026-07-16 | llm-judge-response-guard | REJECT | red-team: weak injectable model gating sole control on highest-value attacks |
