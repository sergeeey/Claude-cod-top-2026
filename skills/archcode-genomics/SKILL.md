---
name: archcode-genomics
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-13]
  USE when working with genomic data, variant analysis, or chromatin structure.
  Triggers: ClinVar, chromatin, variant, extrusion, loop, locus, HBB, SpliceAI,
  pathogenicity, genomics, ARCHCODE, structural variant, pearl.
---

# ARCHCODE Genomics Skill

## Project Context
ARCHCODE is a physics-based method for predicting pathogenicity of non-coding variants through simulation of chromatin loop extrusion. It detects "pearl variants" — variants invisible to sequence-based methods (VEP, CADD, SpliceAI).

## Key Data
- **9 validated loci:** HBB, HBA, BCL11A, CTCF-rich, GATA1, beta-globin LCR, SHH-ZRS, SOX9-KCNJ, MYC-TAD
- **30,318 ClinVar variants** analyzed
- **27 pearl variants** detected (pathogenic, invisible to VEP/SpliceAI)
- **Zenodo DOI:** 10.5281/zenodo.18867051
- **GitHub:** https://github.com/sergeeev/ARCHCODE

## Pearl Variant — Definition
A variant that:
1. VEP = benign/modifier (not pathogenic)
2. SpliceAI delta = 0 (no splicing effect)
3. MPRA enrichment = null (no functional data)
4. BUT: disrupts 3D chromatin structure (CTCF binding, loop anchor, TAD boundary)

## Pipeline
```
ClinVar VCF → VEP annotation → SpliceAI filtering →
ARCHCODE simulation (loop extrusion) →
Structural impact scoring → Pearl detection
```

## Key Files (D:/DNA/)
- `archcode_v2.8_manuscript.pdf` — main manuscript
- `scripts/run_simulation.py` — run simulation
- `data/clinvar_variants/` — input data
- `results/pearl_variants/` — detected pearl variants
- `figures/` — Figure 1-10 for manuscript

## Competitors (for Discussion section)
- **ncVarPred-1D3D** (PMID 37669132) — sequence + 3D, but without ClinVar pearl detection
- **PRISMR** (PMID 29662163) — polymer modeling, but without clinical validation
- **Sei** — sequence-only, does not see structural blind spots

## MCP Servers
Switch to SCIENCE profile: `switch-profile.ps1 science`
- ncbi-datasets: gene info, sequences
- uniprot: protein features, variants, domains
- pubmed-mcp: literature search
