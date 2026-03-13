---
name: archcode-genomics
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-13]
  USE when working with genomic data, variant analysis, or chromatin structure.
  Triggers: ClinVar, chromatin, variant, extrusion, loop, locus, HBB, SpliceAI,
  pathogenicity, genomics, ARCHCODE, structural variant, pearl.
---

# ARCHCODE Genomics Skill

## Контекст проекта
ARCHCODE — physics-based метод предсказания патогенности некодирующих вариантов через симуляцию хроматиновой петлевой экструзии. Выявляет "pearl variants" — варианты невидимые для sequence-based методов (VEP, CADD, SpliceAI).

## Ключевые данные
- **9 валидированных локусов:** HBB, HBA, BCL11A, CTCF-rich, GATA1, beta-globin LCR, SHH-ZRS, SOX9-KCNJ, MYC-TAD
- **30,318 ClinVar вариантов** проанализировано
- **27 pearl variants** обнаружено (патогенные, невидимые для VEP/SpliceAI)
- **Zenodo DOI:** 10.5281/zenodo.18867051
- **GitHub:** https://github.com/sergeeev/ARCHCODE

## Pearl Variant — определение
Вариант, который:
1. VEP = benign/modifier (не pathogenic)
2. SpliceAI delta = 0 (нет сплайсинг-эффекта)
3. MPRA enrichment = null (нет функциональных данных)
4. НО: нарушает 3D-структуру хроматина (CTCF binding, loop anchor, TAD boundary)

## Pipeline
```
ClinVar VCF → VEP annotation → SpliceAI filtering →
ARCHCODE simulation (loop extrusion) →
Structural impact scoring → Pearl detection
```

## Ключевые файлы (D:/ДНК/)
- `archcode_v2.8_manuscript.pdf` — основная рукопись
- `scripts/run_simulation.py` — запуск симуляции
- `data/clinvar_variants/` — входные данные
- `results/pearl_variants/` — обнаруженные pearl variants
- `figures/` — Figure 1-10 для рукописи

## Конкуренты (для Discussion секции)
- **ncVarPred-1D3D** (PMID 37669132) — sequence + 3D, но без ClinVar pearl detection
- **PRISMR** (PMID 29662163) — polymer modeling, но без clinical validation
- **Sei** — sequence-only, не видит structural blind spots

## MCP серверы для работы
Переключить на SCIENCE профиль: `switch-profile.ps1 science`
- ncbi-datasets: gene info, sequences
- uniprot: protein features, variants, domains
- pubmed-mcp: литературный поиск
