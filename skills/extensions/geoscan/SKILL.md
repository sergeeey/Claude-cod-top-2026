---
name: geoscan
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-13]
  USE when working with satellite imagery, mineral prospecting, or geospatial analysis.
  Triggers: Sentinel, spectral, mineral, gold, satellite, lineament, AUC,
  prospecting, geoscan, NDVI, geology, remote sensing, indices.
paths: "**/*sentinel*,**/*raster*,**/*spectral*,**/*ndvi*,**/*.tif"
effort: max
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
- **Isolation Forest:** contamination=# Configure for your study area, n_estimators=200, random_state=42
- **DBSCAN:** eps=# Configure for your study area (in UTM projection), min_samples=# Configure for your study area
- **Feature scaling:** StandardScaler before IF
- **Current AUC:** # YOUR_AUC_SCORE

## Next Steps
- Urban mask (exclude built-up areas from anomaly detection)
- Red Edge bands (B05, B06, B07) for vegetation stress
- Temporal analysis (multi-date for seasonal artifacts)
- Increase positive samples for robust validation

## Gotchas
- Cloud cover >30% invalidates spectral indices — check scene metadata first
- Isolation Forest anomaly threshold varies by geology — calibrate per region
