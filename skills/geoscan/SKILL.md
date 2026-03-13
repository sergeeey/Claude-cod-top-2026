---
name: geoscan
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-13]
  USE when working with satellite imagery, mineral prospecting, or geospatial analysis.
  Triggers: Sentinel, spectral, mineral, gold, satellite, lineament, AUC,
  prospecting, geoscan, NDVI, спутник, геологоразведка, индексы.
---

# GeoScan Gold Prospecting Skill

## Pipeline Overview
```
Sentinel-2 L2A → Spectral Indices → Feature Engineering →
Isolation Forest / DBSCAN → Lineament Detection →
Overlay (geology, faults, known deposits) → Priority Zones → Field Validation
```

## Spectral Indices (Sentinel-2 bands)
| Index | Formula | Что детектирует |
|-------|---------|-----------------|
| Iron Oxide | B04/B02 | Окисленное железо (gossan) |
| Clay Minerals | B11/B12 | Глинистые минералы (alteration) |
| Ferrous Iron | B12/B08 + B03/B04 | Двухвалентное железо |
| NDVI | (B08-B04)/(B08+B04) | Растительность (маскирование) |
| Moisture | (B8A-B11)/(B8A+B11) | Влажность почвы |
| Laterite | B04/B03 | Латеритная кора выветривания |

## Sentinel-2 Bands Reference
| Band | Wavelength (nm) | Resolution | Применение |
|------|----------------|------------|------------|
| B02 | 490 (Blue) | 10m | Базовый, iron oxide ratio |
| B03 | 560 (Green) | 10m | Ferrous minerals |
| B04 | 665 (Red) | 10m | Iron oxide, vegetation |
| B08 | 842 (NIR) | 10m | Vegetation, moisture |
| B8A | 865 (NIR narrow) | 20m | Moisture index |
| B11 | 1610 (SWIR-1) | 20m | Clay, carbonate |
| B12 | 2190 (SWIR-2) | 20m | Clay minerals, alteration |

## ML Parameters (текущие)
- **Isolation Forest:** contamination=0.05, n_estimators=200, random_state=42
- **DBSCAN:** eps=500m (в проекции UTM), min_samples=3
- **Feature scaling:** StandardScaler перед IF
- **AUC текущий:** 0.85 (Phase B)

## Приоритетные зоны (полевая валидация)
1. **Z99** — лучший (кварц, высокий anomaly score)
2. **Z218** — стабильный, вторичная кварцевая жила
3. **Z240** — компактный кластер
4. **Z289** — lineament intersection
5. **Z284** — clay alteration signature
6. **Z548** — удалённый, нужен доступ

## Ключевые файлы (E:/Geoscan Gold 2026/)
- `pipeline/` — основной ML pipeline
- `data/sentinel/` — Sentinel-2 тайлы
- `data/geology/` — геологические карты, разломы
- `results/priority_zones/` — приоритетные зоны
- `maps/interactive_map.html` — интерактивная карта

## Следующие шаги
- Urban mask (исключить застройку из anomaly detection)
- Red Edge bands (B05, B06, B07) для vegetation stress
- Temporal analysis (multi-date для сезонных артефактов)
- Увеличить positives с 19 до 30 для robust AUC
