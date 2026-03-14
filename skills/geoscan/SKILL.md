---
name: geoscan
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-13]
  USE when working with satellite imagery, mineral prospecting, or geospatial analysis.
  Triggers: Sentinel, spectral, mineral, gold, satellite, lineament, AUC,
  prospecting, geoscan, NDVI, geology, remote sensing, indices.
---

# GeoScan Gold Prospecting Skill

## Pipeline Overview
```
Sentinel-2 L2A → Spectral Indices → Feature Engineering →
Isolation Forest / DBSCAN → Lineament Detection →
Overlay (geology, faults, known deposits) → Priority Zones → Field Validation
```

## Spectral Indices (Sentinel-2 bands)
| Index | Formula | Detects |
|-------|---------|---------|
| Iron Oxide | B04/B02 | Oxidized iron (gossan) |
| Clay Minerals | B11/B12 | Clay minerals (alteration) |
| Ferrous Iron | B12/B08 + B03/B04 | Ferrous iron |
| NDVI | (B08-B04)/(B08+B04) | Vegetation (masking) |
| Moisture | (B8A-B11)/(B8A+B11) | Soil moisture |
| Laterite | B04/B03 | Laterite weathering crust |

## Sentinel-2 Bands Reference
| Band | Wavelength (nm) | Resolution | Use |
|------|----------------|------------|-----|
| B02 | 490 (Blue) | 10m | Baseline, iron oxide ratio |
| B03 | 560 (Green) | 10m | Ferrous minerals |
| B04 | 665 (Red) | 10m | Iron oxide, vegetation |
| B08 | 842 (NIR) | 10m | Vegetation, moisture |
| B8A | 865 (NIR narrow) | 20m | Moisture index |
| B11 | 1610 (SWIR-1) | 20m | Clay, carbonate |
| B12 | 2190 (SWIR-2) | 20m | Clay minerals, alteration |

## ML Parameters (current)
- **Isolation Forest:** contamination=0.05, n_estimators=200, random_state=42
- **DBSCAN:** eps=500m (in UTM projection), min_samples=3
- **Feature scaling:** StandardScaler before IF
- **Current AUC:** 0.85 (Phase B)

## Priority Zones (field validation)
1. **Z99** — best (quartz, high anomaly score)
2. **Z218** — stable, secondary quartz vein
3. **Z240** — compact cluster
4. **Z289** — lineament intersection
5. **Z284** — clay alteration signature
6. **Z548** — remote, access required

## Key Files (E:/Geoscan Gold 2026/)
- `pipeline/` — main ML pipeline
- `data/sentinel/` — Sentinel-2 tiles
- `data/geology/` — geological maps, faults
- `results/priority_zones/` — priority zones
- `maps/interactive_map.html` — interactive map

## Next Steps
- Urban mask (exclude built-up areas from anomaly detection)
- Red Edge bands (B05, B06, B07) for vegetation stress
- Temporal analysis (multi-date for seasonal artifacts)
- Increase positives from 19 to 30 for robust AUC
